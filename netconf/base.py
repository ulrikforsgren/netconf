# -*- coding: utf-8 -*-#
#
# February 19 2015, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2015, Deutsche Telekom AG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import absolute_import, division, unicode_literals, print_function, nested_scopes
import logging
import io
import threading
import traceback
from lxml import etree
from lxml.builder import E

from netconf import NSMAP, MAXSSHBUF
from netconf.error import ChannelClosed, FramingError, SessionError
from netconf.util import elm

logger = logging.getLogger(__name__)

NC_BASE_10 = "urn:ietf:params:netconf:base:1.0"
NC_BASE_11 = "urn:ietf:params:netconf:base:1.1"
XML_HEADER = """<?xml version="1.0" encoding="UTF-8"?>"""


def chunkit (msg, maxsend):
    sz = len(msg)
    left = 0
    for unused in range(0, sz // maxsend):
        right = left + maxsend
        chunk = msg[left:right]
        # msg = buffer(msg, left, right)
        left = right
        yield chunk
    # msg = buffer(msg, left)
    msg = msg[left:]
    yield msg


class NetconfTransportMixin (object):
    def connect (self):
        raise NotImplementedError()

    def close (self):
        raise NotImplementedError()


class NetconfPacketTransport (object):
    def send_pdu (self, content, new_framing):
        raise NotImplementedError()

    def receive_pdu (self, new_framing):
        raise NotImplementedError()


class NetconfFramingTransport (NetconfPacketTransport):
    """Packetize an ssh stream into netconf PDUs -- doesn't need to be SSH specific"""
    def __init__ (self, stream, max_chunk, debug):
        # XXX we have 2 channels defined one here and one in the connect/accept class
        self.stream = stream
        self.max_chunk = max_chunk
        self.debug = debug
        self.rbuffer = b""

    def __del__ (self):
        self.close()

    def close (self):
        stream = self.stream
        if stream is not None:
            self.stream = None
            logger.debug("Closing netconf socket stream %s", str(self.stream))
            stream.close()

    def is_active (self):
        return self.stream.is_active()

    def receive_pdu (self, new_framing):
        assert self.stream is not None
        if new_framing:
            return self._receive_11()
        else:
            return self._receive_10()

    def send_pdu (self, msg, new_framing):
        assert self.stream is not None
        # Apparently ssh has a bug that requires minimum of 64 bytes?
        # This may not be sufficient to fix this.
        if new_framing:
            msg = "\n#{}\n{}\n##\n".format(len(msg), msg)
        else:
            msg += "]]>]]>"
        for chunk in chunkit(msg, self.max_chunk - 64):
            self.stream.sendall(chunk)

    def _receive_10 (self):
        searchfrom = 0
        while True:
            eomidx = self.rbuffer.find(b"]]>]]>", searchfrom)
            if eomidx != -1:
                break
            searchfrom = max(0, len(self.rbuffer) - 5)
            buf = self.stream.recv(self.max_chunk)
            self.rbuffer += buf

        msg = self.rbuffer[:eomidx]
        self.rbuffer = self.rbuffer[eomidx + 6:]
        return msg.decode('utf-8')

    def _receive_chunk (self):
        blen = len(self.rbuffer)
        while blen < 4:
            buf = self.stream.recv(self.max_chunk)
            self.rbuffer += buf
            blen = len(self.rbuffer)
            if self.stream is None:
                raise ChannelClosed(self)

        if self.rbuffer[:2] != b"\n#":
            raise FramingError(self.rbuffer)
        self.rbuffer = self.rbuffer[2:]

        # Get chunk length or termination indicator
        idx = -1
        searchfrom = 0
        while True:
            idx = self.rbuffer.find(b"\n", searchfrom)
            if 12 > idx > 0:
                break
            if idx > 12 or len(self.rbuffer) > 12:
                raise FramingError(self.rbuffer)
            searchfrom = len(self.rbuffer)
            self.rbuffer += self.stream.recv(self.max_chunk)

        # Check for last chunk.
        if self.rbuffer[0:2] == b"#\n":
            self.rbuffer = self.rbuffer[2:]
            return None

        lenstr = self.rbuffer[:idx]
        self.rbuffer = bytes(self.rbuffer[idx + 1:])

        try:
            chunklen = int(lenstr)
            if not (4294967295 >= chunklen > 0):
                raise FramingError("Unacceptable chunk length: {}".format(chunklen))
        except ValueError:
            raise FramingError("Frame length not integer: {}".format(lenstr.encode('utf-8')))

        while True:
            blen = len(self.rbuffer)
            if blen >= chunklen:
                chunk = self.rbuffer[:chunklen]
                self.rbuffer = self.rbuffer[chunklen:]
                return chunk
            self.rbuffer += self.stream.recv(self.max_chunk)

    def _iter_receive_chunks (self):
        assert self.stream is not None
        chunk = self._receive_chunk()
        while chunk:
            yield chunk
            chunk = self._receive_chunk()

    def _receive_11 (self):
        assert self.stream is not None
        data = b"".join([x for x in self._iter_receive_chunks()])
        return data.decode('utf-8')


class NetconfSession (object):
    """Netconf Protocol Server and Client"""
    def __init__ (self, stream, debug, session_id, max_chunk=MAXSSHBUF):
        self.debug = debug
        self.pkt_stream = NetconfFramingTransport(stream, max_chunk, debug)
        self.new_framing = False
        self.capabilities = set()
        self.reader_thread = None
        self.msglock = threading.Lock()
        self.cv = threading.Condition(self.msglock)
        self.session_id = session_id
        self.session_open = False

    def __del__ (self):
        if hasattr(self, "session_open"):
            self.close()

    def is_active (self):
        return self.pkt_stream and self.pkt_stream.is_active()

    def __str__ (self):
        return "NetconfSession(sid:{})".format(self.session_id)

    def send_message (self, msg):
        self.pkt_stream.send_pdu(XML_HEADER + msg, self.new_framing)

    def receive_message (self):
        return self.pkt_stream.receive_pdu(self.new_framing)

    def send_hello (self, caplist, session_id=None):
        msg = elm("hello", attrib={'xmlns': NSMAP['nc']})
        caps = E.capabilities(*[E.capability(x) for x in caplist])
        if session_id is not None:
            assert hasattr(self, "methods")
            self.methods.nc_append_capabilities(caps)       # pylint: disable=E1101
        msg.append(caps)

        with self.msglock:
            if self.debug:
                logger.debug("%s: Sending HELLO", str(self))
            if session_id is not None:
                msg.append(E("session-id", str(session_id)))
            msg = etree.tostring(msg)
            self.send_message(msg.decode('utf-8'))

    def close (self):
        if self.debug:
            logger.debug("%s: Closing.", str(self))

        if self.session_open:
            with self.cv:
                self.session_open = False
                self.session_id = None

                # XXX the locking and dealing with the exit of this thread needs improvement
                if self.reader_thread:
                    self.reader_thread.keep_running = False
                self.reader_thread = None

        if self.pkt_stream is not None:
            if self.debug:
                logger.debug("%s: Closing transport.", str(self))

            pkt_stream = self.pkt_stream
            self.pkt_stream = None
            pkt_stream.close()

    def _open_session (self, is_server):
        assert is_server or self.session_id is None

        # The transport should be connected at this point.
        try:
            # Send hello message.
            self.send_hello((NC_BASE_10, NC_BASE_11), self.session_id)

            # Get reply
            reply = self.receive_message()
            if self.debug:
                logger.debug("Received HELLO")

            # Parse reply
            tree = etree.parse(io.BytesIO(reply.encode('utf-8')))
            root = tree.getroot()
            caps = root.xpath("//nc:hello/nc:capabilities/nc:capability",
                              namespaces=NSMAP)

            # Store capabilities
            for cap in caps:
                self.capabilities.add(cap.text)

            if NC_BASE_11 in self.capabilities:
                self.new_framing = True
            elif NC_BASE_10 not in self.capabilities:
                raise SessionError("Server doesn't implement 1.0 or 1.1 of netconf")

            # Get session ID.
            try:
                session_id = root.xpath("//nc:hello/nc:session-id", namespaces=NSMAP)[0].text
                # If we are a server it is a failure to receive a session id.
                if is_server:
                    raise SessionError("Client sent a session-id")
                self.session_id = int(session_id)
            except (KeyError, IndexError, AttributeError):
                if not is_server:
                    raise SessionError("Server didn't supply session-id")
            except ValueError:
                raise SessionError("Server supplied non integer session-id: {}", session_id)

            self.session_open = True

            # Create reader thread.
            self.reader_thread = threading.Thread(target=self._read_message_thread)
            self.reader_thread.daemon = True
            self.reader_thread.keep_running = True
            self.reader_thread.start()

            if self.debug:
                logger.debug("%s: Opened", str(self))

        except Exception:
            self.close()
            raise

    def _handle_message (self, msg):
        raise NotImplementedError("_handle_message")

    def _read_message_thread (self):
        # XXX the locking and dealing with the exit of this thread needs improvement
        if self.debug:
            logger.debug("Starting reader thread.")
        reader_thread = self.reader_thread
        reader_thread.keep_running = True
        try:
            while reader_thread.keep_running and self.pkt_stream:
                # XXX this hangs
                # with self.cv:
                assert self.pkt_stream is not None
                msg = self.receive_message()
                if not reader_thread.keep_running:
                    break
                # XXX might we get None for message here if we got an EOF?

                with self.cv:
                    # with self.msglock: # this causes hangs
                    if True:
                        self._handle_message(msg)
                    self.cv.notify_all()
            if self.debug:
                logger.debug("Exiting reader thread")
        except AttributeError as error:
            # Should we close the session cleanly or just disconnect?
            if "'NoneType' object has no attribute 'recv'" in str(error):
                logger.error("%s: Session channel cleared (open: %s): %s: %s",
                             str(self),
                             str(self.session_open),
                             str(error),
                             traceback.format_exc())
            else:
                logger.error("Unexpected exception in reader thread [disconnecting+exiting]: %s: %s",
                             str(error),
                             traceback.format_exc())
        except ChannelClosed as error:
            # Should we close the session cleanly or just disconnect?
            if self.debug:
                logger.error("%s: Session channel closed [session_open == %s]: %s: %s",
                            selftr(self),
                             str(self.session_open),
                             str(error),
                             traceback.format_exc())
            else:
                logger.error("%s: Session channel closed [session_open == %s]: %s",
                            str(self),
                            str(self.session_open),
                            str(error))
        except SessionError as error:
            # Should we close the session cleanly or just disconnect?
            logger.error("%s Session error [closing session]: %s", str(self), str(error))

            # If we are a server we should be sending error messages
            self.close()
            with self.cv:
                self.cv.notify_all()
        except Exception as error:
            if reader_thread.keep_running:
                logger.error("Unexpected exception in reader thread [disconnecting+exiting]: %s: %s",
                             str(error),
                             traceback.format_exc())
                self.close()
            else:
                # XXX might want to catch errors due to disconnect and not re-raise
                logger.error("Exception in reader thread [exiting]: %s: %s", str(error), traceback.format_exc())
            with self.cv:
                self.cv.notify_all()

__author__ = 'Christian Hopps'
__date__ = 'December 23 2014'
__version__ = '1.0'
__docformat__ = "restructuredtext en"
