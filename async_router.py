#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

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

"""
TODO:
 - Consolidate handle_client into NetconfSSHServer or NetconfSession
 - Fix locking
 - Cleanup keep_running
 - Use argParse
"""

passwords = {'guest': 'guest',          # guest account with no password
             'admin': 'admin'   # password of 'secretpw'
            }

nsmap_add("sys", "urn:ietf:params:xml:ns:yang:ietf-system")
nsmap_add("ex", "http://example.com/example-serial?module=example-serial")
nsmap_add("r", "http://example.com/router")
nsmap_add("tailf", "http://tail-f.com/yang/common")
nsmap_add("ncwr", "urn:ietf:params:netconf:capability:writable-running:1.0")

class SystemServer(object):
    def __init__(self, port, host_key, debug=False):
        self.server = server.NetconfSSHServer(passwords, self, port, host_key, debug)

    async def listen(self):
        await self.server.listen()

    def close(self):
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
        #TODO: Fix filtering
        return util.filter_results(rpc, data, filter_or_none)

    def rpc_edit_config(self, session, rpc, source_elm, filter_or_none):  # pylint: disable=W0613
        #print("rpc", etree.tostring(rpc, pretty_print=True).decode('utf-8'))
        #print("source_elm", etree.tostring(source_elm, pretty_print=True).decode('utf-8'))
        #print("filter", etree.tostring(filter_or_none, pretty_print=True).decode('utf-8'))
        return etree.Element("ok")

    def rpc_system_restart(self, session, rpc, *params):
        raise error.AccessDeniedAppError(rpc)

    def rpc_system_shutdown(self, session, rpc, *params):
        raise error.AccessDeniedAppError(rpc)


async def start_servers(n, start_port) -> None:
    servers = []
    start = time.monotonic()

    for port in range(0, n):
        server = SystemServer(start_port+port, 'ssh_host_key')
        servers.append(server)
        await server.listen()

    elapsed = time.monotonic()-start
    print("Servers started!")
    print(f"Listening on {n} ports: {start_port}-{start_port+n-1}")
    print(f"Startup in {elapsed} seconds.")
    print()
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("Closing!")
        for server in servers:
            server.close()

def main_servers(n, start_port):
    try:
        asyncio.run(start_servers(n, start_port))
    except (OSError, asyncssh.Error) as exc:
        print(exc)
        sys.exit('Error starting server: ' + str(exc))

def main():
    main_servers(1, 30000)

if __name__ == '__main__':
    main()
