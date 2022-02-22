
A Netconf Client/Server Library
===============================

*NOTE!* This a fork of netconf to try to add asyncio support.

The modules with asyncio support are found in directory async_netconf and the
examples in async_example. This to easily see what is changed fro the paramiko
based implementation.

Current features:
- SSH via asyncssh.
- Server support.
- Writable datastore (netconf_merge module + json schema).
- Massive parallelism: Start of 10000 devices in less than a minute. Memory
  usage depends wheather config is stored or not.

TODO asyncio support:

- Create tests for server
- Look into client, the current implementation for server uses the data_received
  callback, which doesn't need a reader "thread". Check wich approach i better.
- Implement more authentication options, "compatible" with the paramiko
  implementation.
- Create tests for netconf_merge.py

This package supports creating both netconf clients and servers. It also
provides a CLI netconf client utility. An example server is included under
the `example` subdirectory.

Documentation is available at: http://netconf.readthedocs.io/

The following modules are present:

- ``__main__`` - Netconf CLI client utility.
- ``base`` - Shared netconf support classes.
- ``error`` - Netconf error classes.
- ``client`` - Netconf client classes.
- ``server`` - Netconf server classes.
- ``util`` - Netconf utility functions.


master branch status:

.. image:: https://travis-ci.org/choppsv1/netconf.svg?branch=master
   :target: https://travis-ci.org/choppsv1/netconf?branch=master

.. image:: https://coveralls.io/repos/choppsv1/netconf/badge.svg?branch=master&service=github
   :target: https://coveralls.io/github/choppsv1/netconf?branch=master

.. image:: https://readthedocs.org/projects/netconf/badge/?version=latest
   :target: http://netconf.readthedocs.io/en/latest/
