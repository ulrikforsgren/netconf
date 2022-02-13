# To run this program, the file ``ssh_host_key`` must exist with an SSH
# private key in it to use as a server host key. An SSH host certificate
# can optionally be provided in the file ``ssh_host_key-cert.pub``.

import asyncio, crypt, sys
import traceback
from typing import Optional
import time

import asyncssh

import async_netconf.base as base
import async_netconf.server as server
import async_netconf.util as util
import lxml.etree as etree

from async_netconf import nsmap_add, NSMAP, MAXSSHBUF

passwords = {'guest': '',                 # guest account with no password
             'user123': 'qV2iEadIGV2rw'   # password of 'secretpw'
            }

nsmap_add("sys", "urn:ietf:params:xml:ns:yang:ietf-system")
nsmap_add("ex", "http://example.com/example-serial?module=example-serial")
nsmap_add("r", "http://example.com/router")
nsmap_add("tailf", "http://tail-f.com/yang/common")
nsmap_add("ncwr", "urn:ietf:params:netconf:capability:writable-running:1.0")

class SystemServer(object):
    def __init__(self):
        #TODO: Fix self.server = server.NetconfSSHServer(auth, self, port, host_key, debug)
        self.server = SSHServer(self)

    def close():
        self.server.close()

    def nc_append_capabilities(self, capabilities):  # pylint: disable=W0613
        """The server should append any capabilities it supports to capabilities"""
        util.subelm(capabilities,
                    "capability").text = "urn:ietf:params:netconf:capability:xpath:1.0"
        util.subelm(capabilities, "capability").text = NSMAP["sys"]
        util.subelm(capabilities, "capability").text = NSMAP["ex"]
        util.subelm(capabilities, "capability").text = NSMAP["r"]
        util.subelm(capabilities, "capability").text = NSMAP["tailf"]
        util.subelm(capabilities, "capability").text = NSMAP["ncwr"]

    def _add_config (self, data):
        sysc = util.subelm(data, "sys:system")

        # System Identification
        sysc.append(util.leaf_elm("sys:hostname", socket.gethostname()))

        # System Clock
        clockc = util.subelm(sysc, "sys:clock")
        tzname = time.tzname[time.localtime().tm_isdst]
        clockc.append(util.leaf_elm("sys:timezone-utc-offset", int(time.timezone / 100)))

    def rpc_get(self, session, rpc, filter_or_none):  # pylint: disable=W0613
        """Passed the filter element or None if not present"""
        data = util.elm("nc:data")

        #
        # Config Data
        #

        self._add_config(data)

        #
        # State Data
        #
        sysd = util.subelm(data, "sys:system-state")

        # System Identification
        platc = util.subelm(sysd, "sys:platform")
        platc.append(util.leaf_elm("sys:os-name", platform.system()))
        platc.append(util.leaf_elm("sys:os-release", platform.release()))
        platc.append(util.leaf_elm("sys:os-version", platform.version()))
        platc.append(util.leaf_elm("sys:machine", platform.machine()))

        # System Clock
        clockc = util.subelm(sysd, "sys:clock")
        now = datetime.datetime.now()
        clockc.append(util.leaf_elm("sys:current-datetime", date_time_string(now)))

        if os.path.exists("/proc/uptime"):
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            boottime = time.time() - uptime_seconds
            boottime = datetime.datetime.fromtimestamp(boottime)
            clockc.append(util.leaf_elm("sys:boot-datetime", date_time_string(boottime)))

        return util.filter_results(rpc, data, filter_or_none, self.server.debug)

    def rpc_get_config(self, session, rpc, source_elm, filter_or_none):  # pylint: disable=W0613
        """Passed the source element"""
        data = util.elm("nc:data")
        #
        # Config Data
        #
        #self._add_config(data)
        router = etree.parse('router.xml')
        data.append(router.getroot())
        return data
        return util.filter_results(rpc, data, filter_or_none)

    def rpc_edit_config(self, session, rpc, source_elm, filter_or_none):  # pylint: disable=W0613
        print("rpc", etree.tostring(rpc, pretty_print=True).decode('utf-8'))
        print("source_elm", etree.tostring(source_elm, pretty_print=True).decode('utf-8'))
        print("filter", etree.tostring(filter_or_none, pretty_print=True).decode('utf-8'))
        return etree.Element("ok")

    def rpc_system_restart(self, session, rpc, *params):
        raise error.AccessDeniedAppError(rpc)

    def rpc_system_shutdown(self, session, rpc, *params):
        raise error.AccessDeniedAppError(rpc)

class SSHServer:
    def __init__(self, methods):
        self.sid = 0
        self.server_methods = methods
    def _allocate_session_id(self):
        self.sid+=1
        return self.sid
    def unlock_target_any(self, session):
        pass

system_server = SystemServer()
ssh_server = SSHServer(system_server)


#TODO: Async - Move handle_client into SSHServer...
async def handle_client(process: asyncssh.SSHServerProcess) -> None:
    print("handle_client")
    # channel/stream, server/NetconfSSHServer, unused_extra_args, debug
    session = server.NetconfServerSession(process, ssh_server, None, True)
    await session._open_session(True)

    try:
        await session._read_message_thread()
        print("Connection broken")
    except Exception as e:
        print("Connection broken")
        print(type(e))
        traceback.print_tb(e.__traceback__)
    process.exit(0)

# TODO: Async - Merge with NetconfSSHServer?
class MySSHServer(asyncssh.SSHServer):
    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        print('SSH connection received from %s.' %
                  conn.get_extra_info('peername')[0])

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc:
            print('SSH connection error: ' + str(exc), file=sys.stderr)
            traceback.print_tb(exc.__traceback__)
        else:
            print('SSH connection closed.')

    def begin_auth(self, username: str) -> bool:
        # If the user's password is the empty string, no auth is required
        return passwords.get(username) != ''

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        pw = passwords.get(username, '*')
        return crypt.crypt(password, pw) == pw

async def start_server() -> None:
    start = time.monotonic()
    n = 1
    for port in range(0, n):
        await asyncssh.create_server(MySSHServer, '', 10000+port,
                                     server_host_keys=['ssh_host_key'],
                                     process_factory=handle_client)

    elapsed = time.monotonic()-start
    print("Servers started!")
    print(f"Listening on {n} ports.")
    print(f"Startup in {elapsed} seconds.")
    await asyncio.sleep(300)

try:
    asyncio.run(start_server())
except (OSError, asyncssh.Error) as exc:
    print(exc)
    sys.exit('Error starting server: ' + str(exc))
