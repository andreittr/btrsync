<!--
Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>

SPDX-License-Identifier: CC-BY-SA-4.0
-->

# btrsync

Replicate btrfs subvolumes, handling Copy-on-Write (COW) relationships and incremental transfers automatically.

Documentation is on [Read the Docs](https://btrsync.readthedocs.io).
Code repository and issue tracker are on [GitHub](https://github.com/andreittr/btrsync).

## Background
[btrfs](https://btrfs.wiki.kernel.org) is a modern Linux Copy-on-Write (COW) filesystem supporting powerful features such as snapshotting and incremental serialization.
This makes it easy to efficiently replicate related snapshots from one filesystem to another by transferring only the differences between them.

What is not easy, however, is manually identifying and tracking these relationships in order to fully leverage the features of btrfs.
Built-in tools provide the necessary mechanisms, but the heavy lifting is left to the user.

This is where **btrsync** comes in.

True to its name, btrsync is "rsync, but for btrfs", reducing the complex task of comparing and replicating snapshots down to a one-liner:
```
btrsync SOURCE DESTINATION
```

### Features
- Handles subvolume discovery and incremental transfers automatically
- Supports local and remote machines (through SSH)
- Intuitive CLI inspired by familiar tools like [rsync](https://rsync.samba.org/) and [scp](https://man.openbsd.org/scp.1)

## Install
btrsync requires Python 3.9 or later.

The easiest way to install is from [PyPI](https://pypi.org/project/btrsync/) via `pip`:
```
pip install btrsync
```
(replace `pip` with `pip3` if your system's `pip` defaults to Python 2)

Alternatively you can install from a locally built wheel (requires [build](https://github.com/pypa/build) and [pip](https://pip.pypa.io/)):
```
make && make install
```
This will run the unit tests, build the documentation and a local wheel, then install it with `pip`.

## Usage
### Command-line
See the [CLI Usage](https://btrsync.readthedocs.io/en/latest/cli-usage.html) section of the documentation for general guidance and examples.

The help option provides information about command-line options:
```
btrsync --help
```

### Library
You can also `import btrsync` directly in your Python programs, see the [API Reference](https://btrsync.readthedocs.io/en/latest/api.html).
The implementation of the [btrsync CLI](btrsync/cli.py) provides an extensive example on how to use the API.

## API

See the [API Reference](https://btrsync.readthedocs.io/en/latest/api.html) section of the documentation.

## Development
Running `make` with no arguments will:
1. Run the unit tests and (if passing) produce coverage information under `htmlcov/`
1. Build the HTML documentation under `doc/build/html/`
1. Build a Python source distribution (sdist) and wheel under `dist/`

### Running Tests
Unit tests use the Python standard library [unittest](https://docs.python.org/3/library/unittest.html) module.
Coverage measurements require [Coverage.py](https://github.com/nedbat/coveragepy).
- `make test` runs all unit tests
- `make cov` runs all unit tests while collecting coverage information
- `make htmlcov` creates a HTML coverage report under `htmlcov/`, running the coverage measurements as needed

### Building Documentation
Building the documentation requires [Sphinx](https://www.sphinx-doc.org).
- `make doc` builds the default HTML documentation
- `make -C doc/` lists more formats to build the documentation in (e.g., plain text, epub)

### Build & Install Distributables
Building the source distribution (sdist) and wheel requires [build](https://github.com/pypa/build).
Installation requires [pip](https://pip.pypa.io/).
- `make dist` builds both source distribution and wheel under `dist/`
- `make install` installs the built wheel with `pip` (forcefully replacing any previously installed version)

### Cleanup
- `make cleanpy` removes Python compiled bytecode files (`__pycache__`)
- `make cleancov` removes collected coverage information and generated coverage report under `htmlcov/`
- `make cleandist` removes the distribution packages under `dist/`
- `make cleandoc` removes built documentation from `doc/build/`
- `make cleandocgen` removes auto-generated API reference pages from the documentation source
- `make clean` runs all of the above

## Contributing

For bug reports and feature proposals use the [GitHub Issues page](https://github.com/andreittr/btrsync/issues).

You can also support this project by [buying me a coffee](https://www.buymeacoffee.com/andrei.ttr).

## License
Copyright © 2023 Andrei Tatar.

Code and tests licensed [GPL-3.0-or-later](LICENSES/GPL-3.0-or-later.txt).

Documentation (including this document) licensed [CC-BY-SA-4.0](LICENSES/CC-BY-SA-4.0.txt).

Trivial miscellanea (Makefiles, .gitignores) licensed [CC0-1.0](LICENSES/CC0-1.0.txt).

This project is compliant with the [REUSE](https://reuse.software) specifications.
