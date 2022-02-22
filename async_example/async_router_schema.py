#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

# This is an async example showing a writable runnable without persistence.
# The json-schema is found in router.json and the initial configuation is
# read from router.xml.
# The schema is compiled from the router.yang used in the examples delivered
# with Cisco NSO.

import asyncio
import json
import os
import sys
import time

import asyncssh
import lxml.etree as etree

cdir = os.path.dirname(sys.argv[0])
if cdir != '.':
    os.chdir(cdir)
sys.path.append(os.path.dirname(os.getcwd()))

import async_netconf.base as base
import async_netconf.server as server
import async_netconf.util as util
from async_netconf import nsmap_add, NSMAP, MAXSSHBUF
from netconf_merge import merge_tree, MergeError


passwords = {'guest': 'guest',          # guest account with no password
             'admin': 'admin'   # password of 'secretpw'
            }

nsmap_add("r", "http://example.com/router")
nsmap_add("ncwr", "urn:ietf:params:netconf:capability:writable-running:1.0")

class SystemServer(object):
    def __init__(self, port, host_key, schema, debug=False):
        self.server = server.NetconfSSHServer(passwords, self, port, host_key, debug)
        self.schema = schema
        router = etree.parse('router.xml')
        self.cdb = router.getroot()

    async def listen(self):
        await self.server.listen()

    def close(self):
        self.server.close()

    def nc_append_capabilities(self, capabilities):  # pylint: disable=W0613
        """The server should append any capabilities it supports to capabilities"""
        util.subelm(capabilities,
                    "capability").text = "urn:ietf:params:netconf:capability:xpath:1.0"
        util.subelm(capabilities, "capability").text = NSMAP["r"]
        util.subelm(capabilities, "capability").text = NSMAP["ncwr"]

    def rpc_get(self, session, rpc, filter_or_none):  # pylint: disable=W0613
        """Passed the filter element or None if not present"""
        data = util.elm("nc:data")
        data.append(self.cdb)
        return util.filter_results(rpc, data, filter_or_none, self.server.debug)

    def rpc_get_config(self, session, rpc, source_elm, filter_or_none):  # pylint: disable=W0613
        """Passed the source element"""
        data = util.elm("nc:data")
        data.append(self.cdb)
        return data
        #TODO: Fix filtering
        #return util.filter_results(rpc, data, filter_or_none)

    def rpc_edit_config(self, session, rpc, source_elm, filter_or_none):  # pylint: disable=W0613
        print(etree.tostring(rpc, pretty_print=True).decode('utf-8'))
        ec = rpc.find('edit-config', rpc.nsmap)
        config = ec.find('config', rpc.nsmap)
        sys = config.find('{http://example.com/router}sys')
        merge_tree(self.cdb, sys, self.schema)
        return etree.Element("ok")


async def start_servers(n, start_port, schema_file) -> None:
    schema_file = json.loads(open(schema_file).read())
    tree = schema_file['tree']
    schema = tree['router:sys'][1] # container sub elems
    servers = []
    start = time.monotonic()

    for port in range(0, n):
        server = SystemServer(start_port+port, 'ssh_host_key', schema)
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
        asyncio.run(start_servers(n, start_port, 'router.json'))
    except (OSError, asyncssh.Error) as exc:
        print(exc)
        sys.exit('Error starting server: ' + str(exc))

def main():
    main_servers(1, 30000)

if __name__ == '__main__':
    main()
