# NETCONF Client/Server Libraries

This project provides two Python implementations of NETCONF protocol:

1. `netconf` - A synchronous implementation using Paramiko for SSH
2. `async_netconf` - An asynchronous implementation using asyncssh

Both implementations provide client and server functionality following the NETCONF protocol.

## Installation

This package uses modern Python packaging with `pyproject.toml`. You'll need Python 3.7 or higher.

### From PyPI (not available yet)

```bash
# Install the synchronous version
pip install netconf

# Install with async support
pip install "netconf[async]"
```

### From source

```bash
# Clone the repository
git clone https://github.com/choppsv1/netconf.git
cd netconf

# Install in development mode with all dependencies
pip install -e ".[dev,async]"
```

### Development Dependencies

For development, install with the `dev` extra:

```bash
pip install -e ".[dev]"
```

This includes:
- Testing tools (pytest, pytest-cov, pytest-asyncio)
- Linting (pylint, yapf)
- Build tools (setuptools-scm, twine, wheel)

## Features

### Synchronous (netconf)

- Complete NETCONF 1.0 and 1.1 protocol support
- SSH transport via Paramiko
- Server and client implementations
- Thread-safe design
- XML-based RPCs and notifications

### Asynchronous (async_netconf)

- Asyncio-based implementation
- SSH transport via asyncssh
- High-performance server and client
- Non-blocking I/O operations
- Compatible with Python's asyncio ecosystem

## Command Line Tools

Both packages provide command-line clients:

```bash
# Synchronous client
netconf-client [options] <host> [<port>]

# Asynchronous client
async-netconf-client [options] <host> [<port>]
```

## Examples

### Synchronous Client

```python
from netconf.client import SSHClient

with SSHClient("hostname") as client:
    # Get running config
    result = client.get_config()
    print(result)
```

### Asynchronous Client

```python
import asyncio
from async_netconf.client import SSHClient

async def main():
    async with SSHClient("hostname") as client:
        # Get running config
        result = await client.get_config()
        print(result)


asyncio.run(main())
```

## Documentation

For detailed documentation, please refer to: http://netconf.readthedocs.io/

## Development

To set up a development environment:

```bash
git clone https://github.com/choppsv1/netconf.git
cd netconf
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## Package Structure

### netconf (Synchronous)

- `__main__` - Netconf CLI client utility
- `base` - Shared netconf support classes
- `error` - Netconf error classes
- `client` - Netconf client implementation
- `server` - Netconf server implementation
- `util` - Utility functions

### async_netconf (Asynchronous)

- `__main__` - Asynchronous netconf CLI client
- `base` - Async netconf support classes
- `error` - Async netconf error classes
- `client` - Async netconf client implementation
- `server` - Async netconf server implementation
- `util` - Async utility functions
- `simple_client` - Simplified async client interface

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
