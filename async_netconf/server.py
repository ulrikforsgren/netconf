# -*- coding: utf-8 eval: (yapf-mode 1) -*-
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
import io
import logging
import os
import sys
import traceback
from typing import Optional
from lxml import etree
import asyncssh

from async_netconf import base
import netconf.error as ncerror
from async_netconf import NSMAP
from async_netconf import qmap
from async_netconf import util

if sys.platform == 'win32' and sys.version_info < (3, 5):
    import backports.socketpair  # pylint: disable=E0401,W0611

logger = logging.getLogger(__name__)

try:
    import pam
    have_pam = True
except ImportError:
    have_pam = False



class NetconfServerSession(base.NetconfSession):
    """Netconf Server-side session with a client.

    This object will be passed to a the server RPC methods.
    """
    handled_rpc_methods = set(["close-session", "lock", "kill-session", "unlock"])

    def __init__(self, stream, server, unused_extra_args, debug):
        self.server = server
        #print("NetconfServerSession.__init__")
        sid = self.server._allocate_session_id()
        if debug:
            logger.debug("NetconfServerSession: Creating session-id %s", str(sid))
        super().__init__(stream, debug, sid)

        self.methods = server.server_methods

        if self.debug:
            logger.debug("%s: Client session-id %s created", str(self), str(sid))

    def __del__(self):
        self.close()
        super(NetconfServerSession, self).__del__()

    def __str__(self):
        return "NetconfServerSession(sid:{})".format(self.session_id)

    def close(self):
        """Close the servers side of the session."""
        # XXX should be invoking a method in self.methods?
        if self.debug:
            logger.debug("%s: Closing.", str(self))

        # Cleanup any locks
        locked = self.server.unlock_target_any(self)
        method = getattr(self.methods, "rpc_unlock", None)
        if method is not None:
            try:
                # Let the user know.
                for target in locked:
                    method(self, None, target)
            except Exception as ex:
                if self.debug:
                    logger.debug("%s: Ignoring exception in rpc_unlock during close: %s", str(self),
                                 str(ex))
        try:
            super(NetconfServerSession, self).close()
        except EOFError:
            if self.debug:
                logger.debug("%s: EOF error while closing", str(self))

        if self.debug:
            logger.debug("%s: Closed.", str(self))

    # ----------------
    # Internal Methods
    # ----------------

    def _send_rpc_reply(self, rpc_reply, origmsg):
        """Send an rpc-reply to the client. This is should normally not be called
        externally the return value from the rpc_* methods will be returned
        using this method.
        """
        reply = etree.Element(qmap('nc') + "rpc-reply", attrib=origmsg.attrib, nsmap=origmsg.nsmap)
        try:
            rpc_reply.getchildren  # pylint: disable=W0104
            reply.append(rpc_reply)
        except AttributeError:
            reply.extend(rpc_reply)
        ucode = etree.tostring(reply, pretty_print=True)
        if self.debug:
            logger.debug("%s: Sending RPC-Reply: %s", str(self), str(ucode))
        self.send_message(ucode)

    def _rpc_not_implemented(self, unused_session, rpc, *unused_params):
        if self.debug:
            msg_id = rpc.get(qmap("nc") + 'message-id')
            logger.debug("%s: Not Impl msg-id: %s", str(self), msg_id)
        raise ncerror.OperationNotSupportedProtoError(rpc)

    def _send_rpc_reply_error(self, error):
        #TODO: Need to look over the API bytes vs. str boundary
        self.send_message(error.get_reply_msg().encode('utf-8'))

    def _reader_exits(self):
        if self.debug:
            logger.debug("%s: Reader thread exited.", str(self))
        return

    def _reader_handle_message(self, msg):
        #if not self.session_open:
        #    return

        # Any error with XML encoding here is going to cause a session close
        # Technically we should be able to return malformed message I think.
        try:
            tree = etree.parse(io.BytesIO(msg.lstrip()))
            if not tree:
                raise ncerror.SessionError(msg, "Invalid XML from client.")
        except etree.XMLSyntaxError:
            logger.warning("Closing session due to malformed message")
            raise ncerror.SessionError(msg, "Invalid XML from client.")

        rpcs = tree.xpath("/nc:rpc", namespaces=NSMAP)
        if not rpcs:
            raise ncerror.SessionError(msg, "No rpc found")

        for rpc in rpcs:
            try:
                msg_id = rpc.get(qmap("nc") + 'message-id')
                if self.debug:
                    logger.debug("%s: Received rpc message-id: %s", str(self), msg_id)
            except (TypeError, ValueError):
                raise ncerror.SessionError(msg, "No valid message-id attribute found")

            try:
                # Get the first child of rpc as the method name
                rpc_method = rpc.getchildren()
                if len(rpc_method) != 1:
                    if self.debug:
                        logger.debug("%s: Bad Msg: msg-id: %s", str(self), msg_id)
                    raise ncerror.MalformedMessageRPCError(rpc)
                rpc_method = rpc_method[0]

                rpcname = rpc_method.tag.replace(qmap('nc'), "")
                params = rpc_method.getchildren()
                paramslen = len(params)
                lock_target = None

                if self.debug:
                    logger.debug("%s: RPC: %s: paramslen: %s", str(self), rpcname, str(paramslen))

                if rpcname == "close-session":
                    # XXX should be RPC-unlocking if need be
                    if self.debug:
                        logger.debug("%s: Received close-session msg-id: %s", str(self), msg_id)
                    sel._send_rpc_reply(etree.Element("ok"), rpc)
                    self.close()
                    # XXX should we also call the user method if it exists?
                    return
                elif rpcname == "kill-session":
                    # XXX we are supposed to cleanly abort anything underway
                    if self.debug:
                        logger.debug("%s: Received kill-session msg-id: %s", str(self), msg_id)
                    self._send_rpc_reply(etree.Element("ok"), rpc)
                    self.close()
                    # XXX should we also call the user method if it exists?
                    return
                elif rpcname == "get":
                    # Validate GET parameters

                    if paramslen > 1:
                        # XXX need to specify all elements not known
                        raise ncerror.MalformedMessageRPCError(rpc)
                    if params and not util.filter_tag_match(params[0], "nc:filter"):
                        raise ncerror.UnknownElementProtoError(rpc, params[0])
                    if not params:
                        params = [None]
                elif rpcname == "get-config":
                    # Validate GET-CONFIG parameters

                    if paramslen > 2:
                        # XXX Should be ncerror.UnknownElementProtoError? for each?
                        raise ncerror.MalformedMessageRPCError(rpc)
                    source_param = rpc_method.find("nc:source", namespaces=NSMAP)
                    if source_param is None:
                        raise ncerror.MissingElementProtoError(rpc, util.qname("nc:source"))
                    filter_param = None
                    if paramslen == 2:
                        filter_param = rpc_method.find("nc:filter", namespaces=NSMAP)
                        if filter_param is None:
                            unknown_elm = params[0] if params[0] != source_param else params[1]
                            raise ncerror.UnknownElementProtoError(rpc, unknown_elm)
                    params = [source_param, filter_param]
                elif rpcname == "lock" or rpcname == "unlock":
                    if paramslen != 1:
                        raise ncerror.MalformedMessageRPCError(rpc)
                    target_param = rpc_method.find("nc:target", namespaces=NSMAP)
                    if target_param is None:
                        raise ncerror.MissingElementProtoError(rpc, util.qname("nc:target"))
                    elms = target_param.getchildren()
                    if len(elms) != 1:
                        raise ncerror.MissingElementProtoError(rpc, util.qname("nc:target"))
                    lock_target = elms[0].tag.replace(qmap('nc'), "")
                    if lock_target not in ["running", "candidate"]:
                        raise ncerror.BadElementProtoError(rpc, util.qname("nc:target"))
                    params = [lock_target]

                    if rpcname == "lock":
                        logger.error("%s: Lock Target: %s", str(self), lock_target)
                        # Try and obtain the lock.
                        locksid = self.server.lock_target(self, lock_target)
                        if locksid:
                            raise ncerror.LockDeniedProtoError(rpc, locksid)
                    elif rpcname == "unlock":
                        logger.error("%s: Unlock Target: %s", str(self), lock_target)
                        # Make sure we have the lock.
                        locksid = self.server.is_target_locked(lock_target)
                        if locksid != self.session_id:
                            # An odd error to return
                            raise ncerror.LockDeniedProtoError(rpc, locksid)

                #------------------
                # Call the method.
                #------------------

                try:
                    # Handle any namespaces or prefixes in the tag, other than
                    # "nc" which was removed above. Of course, this does not handle
                    # namespace collisions, but that seems reasonable for now.
                    rpcname = rpcname.rpartition("}")[-1]
                    method_name = "rpc_" + rpcname.replace('-', '_')
                    method = getattr(self.methods, method_name, None)

                    if method is None:
                        if rpcname in self.handled_rpc_methods:
                            self._send_rpc_reply(etree.Element("ok"), rpc)
                            method = None
                        else:
                            method = self._rpc_not_implemented

                    if method is not None:
                        if self.debug:
                            logger.debug("%s: Calling method: %s", str(self), method_name)
                        reply = method(self, rpc, *params)
                        self._send_rpc_reply(reply, rpc)
                except Exception:
                    # If user raised error unlock if this was lock
                    if rpcname == "lock" and lock_target:
                        self.server.unlock_target(self, lock_target)
                    raise

                # If this was unlock and we're OK, release the lock.
                if rpcname == "unlock":
                    self.server.unlock_target(self, lock_target)

            except ncerror.MalformedMessageRPCError as msgerr:
                if self.new_framing:
                    if self.debug:
                        logger.debug("%s: MalformedMessageRPCError: %s", str(self), str(msgerr))
                    self.send_message(msgerr.get_reply_msg())
                else:
                    # If we are 1.0 we have to simply close the connection
                    # as we are not allowed to send this error
                    logger.warning("Closing 1.0 session due to malformed message")
                    raise ncerror.SessionError(msg, "Malformed message")
            except ncerror.RPCServerError as error:
                if self.debug:
                    logger.debug("%s: RPCServerError: %s", str(self), str(error))
                self._send_rpc_reply_error(error)
            except EOFError:
                if self.debug:
                    logger.debug("%s: Got EOF in reader_handle_message", str(self))
                error = ncerror.RPCSvrException(rpc, EOFError("EOF"))
                self._send_rpc_reply_error(error)
            except Exception as exception:
                if self.debug:
                    logger.debug("%s: Got unexpected exception in reader_handle_message: %s",
                                 str(self), str(exception))
                error = ncerror.RPCSvrException(rpc, exception)
                self._send_rpc_reply_error(error)


class NetconfMethods(object):
    """This is an abstract class that is used to document the server methods
    functionality.

    The base server code will return not-implemented if the method is not found
    in the methods object, so feel free to use duck-typing here (i.e., no need to
    inherit). Create a class that implements the rpc_* methods you handle and pass
    that to `NetconfSSHServer` init.
    """
    def nc_append_capabilities(self, capabilities):  # pylint: disable=W0613
        """This method should append any capabilities it supports to capabilities

        :param capabilities: The element to append capability elements to.
        :type capabilities: `lxml.Element`
        :return: None
        """
        return

    def rpc_get(self, session, rpc, filter_or_none):  # pylint: disable=W0613
        """Passed the filter element or None if not present

        :param session: The server session with the client.
        :type session: `NetconfServerSession`
        :param rpc: The topmost element in the received message.
        :type rpc: `lxml.Element`
        :param filter_or_none: The filter element if present.
        :type filter_or_none: `lxml.Element` or None
        :return: `lxml.Element` of "nc:data" type containing the requested state.
        :raises: `error.RPCServerError` which will be used to construct an XML error response.
        """
        raise ncerror.OperationNotSupportedProtoError(rpc)

    def rpc_get_config(self, session, rpc, source_elm, filter_or_none):  # pylint: disable=W0613
        """The client has requested the config state (config: true). The function is
        passed the source element and the filter element or None if not present

        :param session: The server session with the client.
        :type session: `NetconfServerSession`
        :param rpc: The topmost element in the received message.
        :type rpc: `lxml.Element`
        :param source_elm: The source element indicating where the config should be drawn from.
        :type source_elm: `lxml.Element`
        :param filter_or_none: The filter element if present.
        :type filter_or_none: `lxml.Element` or None
        :return: `lxml.Element` of "nc:data" type containing the requested state.
        :raises: `error.RPCServerError` which will be used to construct an XML error response.
        """
        raise ncerror.OperationNotSupportedProtoError(rpc)

    def rpc_lock(self, session, rpc, target):
        """Lock the given target datastore.

        The server tracks the lock automatically which can be checked using the
        server `is_locked` method. This function is called after the lock is
        granted.

        This server code can only verify if a lock has been granted or not,
        it cannot actually verify all the lock available conditions set forth
        in RFC6241. If any of the following can be true the user must also check
        this by implementing this function:

        RFC6241:

            A lock MUST NOT be granted if any of the following conditions is
            true:

            * A lock is already held by any NETCONF session or another
              entity. ** The server checks for other sessions but cannot check
              if another entity (e.g., CLI) has been granted the lock.
            * The target configuration is <candidate>, it has already been
              modified, and these changes have not been committed or rolled
              back. ** The server code cannot check this.
            * The target configuration is <running>, and another NETCONF
              session has an ongoing confirmed commit (Section 8.4). ** The server
              code cannot check this.

        Implement this method and if the lock should not be granted raise the following
        error (or anything else appropriate).

            raise netconf.error.LockDeniedProtoError(rpc, <session-id-holding-lock>)

        :param session: The server session with the client.
        :type session: `NetconfServerSession`
        :param rpc: The topmost element in the received message.
        :type rpc: `lxml.Element`
        :param target: The tag name of the target child element indicating
                       which config datastore should be locked.
        :type target_elm: str
        :return: None
        :raises: `error.RPCServerError` which will be used to construct an
                 XML error response. The lock will be released if an error
                 is raised.
        """
        del rpc, session, target  # avoid unused errors from pylint
        return

    def rpc_unlock(self, session, rpc, target):
        """Unlock the given target datastore.

        If this method raises an error the server code will *not* release
        the lock.

        :param session: The server session with the client.
        :type session: `NetconfServerSession`
        :param rpc: The topmost element in the received message or None if the
                    session is being closed and this is notification of lock release.
                    In this latter case any exception raised will be ignored.
        :type rpc: `lxml.Element` or None
        :param target: The tag name of the target child element indicating
                       which config datastore should be locked.
        :type target_elm: str
        :return: None
        :raises: `error.RPCServerError` which will be used to construct an
                 XML error response. The lock will be not be released if an
                 error is raised.
        """
        del rpc, session, target  # avoid unused errors from pylint
        return

    #-----------------------------------------------------------------------
    # Override these definitions if you also would like to do more than the
    # default actions.
    #-----------------------------------------------------------------------

    def rpc_close_session(self, session, rpc, *unused_params):
        pass

    def rpc_kill_session(self, session, rpc, *unused_params):
        pass

    #---------------------------------------------------------------------------
    # These definitions will change to include required parameters like get and
    # get-config
    #---------------------------------------------------------------------------

    def rpc_copy_config(self, unused_session, rpc, *unused_params):
        """XXX API subject to change -- unfinished"""
        raise ncerror.OperationNotSupportedProtoError(rpc)

    def rpc_delete_config(self, unused_session, rpc, *unused_params):
        """XXX API subject to change -- unfinished"""
        raise ncerror.OperationNotSupportedProtoError(rpc)

    def rpc_edit_config(self, unused_session, rpc, *unused_params):
        """XXX API subject to change -- unfinished"""
        raise ncerror.OperationNotSupportedProtoError(rpc)


class SSHServerSession(asyncssh.SSHServerSession):
    def __init__(self, server):
        #print("SSHServerSession")
        self.server = server
    def connection_made(self, chan):
        self.session = NetconfServerSession(chan, self.server, None, True)
    def subsystem_requested(self, subsystem):
        return subsystem == 'netconf'
    def data_received(self, data, datatype):
        self.session.data_received(data, datatype)
    def eof_received(self):
        print("EOF")
        self._chan.exit(0)
        return False

# New instance for each connection
class MySSHServer(asyncssh.SSHServer):
    def __init__(self, server, server_ctl, server_methods):
        self.server = server
        self.server_ctl = server_ctl
        self.server_methods = server_methods
        #print(type(self), "__init__")
        super().__init__()

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        print('SSH connection received from %s.' %
                  conn.get_extra_info('peername')[0])

    def connection_lost(self, exc: Optional[Exception]) -> None:
        #print(type(self), "connection_lost")
        if exc:
            # TODO: Handle these exception at the proper place...
            if isinstance(exc, ConnectionResetError):
                pass
                print('SSH connection reset.')
            elif isinstance(exc, asyncssh.misc.ConnectionLost):
                pass
                print('SSH connection lost.')
            elif isinstance(exc, BrokenPipeError):
                pass
                print('Broken Pipe.')
            else:
                print('SSH connection error: ' + str(exc), file=sys.stderr)
                print("Exception", type(exc))
                traceback.print_tb(exc.__traceback__)
        else:
            print('SSH connection closed.')

    def begin_auth(self, username: str) -> bool:
        # If the user's password is the empty string, no auth is required
        return self.server_ctl.get(username) != ''

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        pw = self.server_ctl.get(username, '*')
        return password == pw
        return crypt.crypt(password, pw) == pw

    def session_requested(self):
        return SSHServerSession(self.server)


class NetconfSSHServer:
    """A netconf server.

    :param server_ctl: The object used for authenticating connections to the server.
    :type server_ctl: `ssh.ServerInterface`
    :param server_methods: An object which implements servers the rpc_* methods.
    :param port: The port to bind the server to.
    :param host_key: The file containing the host key.
    :param debug: True to enable debug logging.
    """
    def __init__(self, server_ctl=None, server_methods=None, port=830, host_key=None, debug=False):
        self.server_ctl = server_ctl
        self.server_methods = server_methods if server_methods is not None else NetconfMethods()
        self.port = port
        self.host_key = host_key
        self.debug = debug
        self.session_id = 1
#        self.session_locks_lock = threading.Lock()
        self.session_locks = {
            "running": 0,
            "candidate": 0,
        }

    def __del__(self):
        logger.error("Deleting %s", str(self))

    def serv_factory(self):
        return MySSHServer(self, self.server_ctl, self.server_methods)

    async def listen(self):
        options = asyncssh.SSHServerConnectionOptions(
                            line_editor=False,
                            allow_scp=False,
                            allow_pty=False
                            )

        await asyncssh.listen('', self.port, reuse_port=True,
                            options= options,
                            server_factory=self.serv_factory,
                            server_host_keys=self.host_key,
                            encoding=None) # Enables bytes mode

    def _allocate_session_id(self):
        #TODO: Async - with self.lock:
        sid = self.session_id
        self.session_id += 1
        return sid

    def __str__(self):
        return "NetconfSSHServer(port={})".format(self.port)

    def unlock_target_any(self, session):
        """Unlock any targets locked by this session.

        Returns list of targets that this session had locked."""
        locked = []
        #TODO: Async - with self.lock:
        #    with self.session_locks_lock:
        sid = session.session_id
        for target in self.session_locks:
            if self.session_locks[target] == sid:
                self.session_locks[target] = 0
                locked.append(target)
        return locked

    def unlock_target(self, session, target):
        """Unlock the given target."""
        #TODO: Async - with self.lock:
            #with self.session_locks_lock:
        if self.session_locks[target] == session.session_id:
            self.session_locks[target] = 0
            return True
        return False

    def lock_target(self, session, target):
        """Try to obtain target lock.
        Return 0 on success or the session ID of the lock holder.
        """
        #with self.lock:
        #    with self.session_locks_lock:
        if self.session_locks[target]:
            return self.session_locks[target]
        self.session_locks[target] = session.session_id
        return 0

    def is_target_locked(self, target):
        """Returns the sesions ID who owns the lock or 0 if not locked."""
        #TODO: Async -with self.lock:
        #    with self.session_locks_lock:
        if target not in self.session_locks:
            return None
        return self.session_locks[target]


__author__ = 'Christian Hopps'
__date__ = 'February 19 2015'
__version__ = '1.0'
__docformat__ = "restructuredtext en"
