
A Netconf Client/Server Library
===============================

*NOTE!* This a working branch to add asyncio support. See async_router.py as an
example of an initial example. The modules with async support are found in
directory async_netconf.

TODO:

- Merge and use NetconfSSHServer
- Merge and use SSHUserPassController
- Merge and use NetconfServerSession
- Create tests for server
- Look into client

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
