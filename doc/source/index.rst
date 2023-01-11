.. Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
..
.. SPDX-License-Identifier: CC-BY-SA-4.0

.. btrsync documentation master file, created by
   sphinx-quickstart on Wed Dec 28 01:03:35 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

``btrsync`` Documentation
=========================

``btrsync`` is a tool for replicating btrfs subvolumes, handling Copy-on-Write (COW) relationships and incremental transfers automatically.

Why btrsync?
------------
`btrfs <https://btrfs.wiki.kernel.org>`_ is a modern Linux Copy-on-Write (COW) filesystem supporting powerful features such as snapshotting and incremental serialization.
This makes it easy to efficiently replicate related snapshots from one filesystem to another by transferring only the differences between them.

What is not easy, however, is manually identifying and tracking these relationships in order to fully leverage the features of btrfs.
Built-in tools provide the necessary mechanisms, but the heavy lifting is left to the user.

This is where **btrsync** comes in.

True to its name, btrsync is "rsync, but for btrfs", reducing the complex task of comparing and replicating snapshots down to a one-liner:

.. code-block:: shell

   btrsync SOURCE DESTINATION

Features
^^^^^^^^

- Handles subvolume discovery and incremental transfers automatically
- Supports local and remote machines (through SSH)
- Intuitive CLI inspired by familiar tools like `rsync <https://rsync.samba.org/>`_ and `scp <https://man.openbsd.org/scp.1>`_


Installation
------------
btrsync requires Python 3.9 or later.

The easiest way to install is from `PyPI <https://pypi.org/project/btrsync/>`_ via ``pip``:

.. code-block:: shell

   pip install btrsync

(replace ``pip`` with ``pip3`` if your system's ``pip`` defaults to Python 2)

Alternatively, you can check out the latest source at `GitHub <https://github.com/andreittr/btrsync>`_.

Usage
-----

For running ``btrsync`` as a command-line utility see :ref:`cli-usage`.

For importing btrsync directly into your Python programs see :ref:`api`.

Contributing
------------

For bug reports and feature proposals use the `GitHub Issues page <https://github.com/andreittr/btrsync/issues>`_.

You can also support this project by `buying me a coffee <https://www.buymeacoffee.com/andrei.ttr>`_.

Contents
========

.. toctree::
   :maxdepth: 5
   :titlesonly:

   cli-usage
   api


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
