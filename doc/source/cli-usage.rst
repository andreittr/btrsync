.. Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
..
.. SPDX-License-Identifier: CC-BY-SA-4.0

.. _cli-usage:

CLI Usage
=========

Run the main command-line interface with

.. code-block:: shell

   python -m btrsync.cli [OPTIONS] SOURCE [SOURCE ...] DESTINATION

(replace ``python`` with ``python3`` if your system's ``python`` defaults to Python 2)

Alternatively, if you installed via ``pip``, you can directly run

.. code-block:: shell
   
   btrsync [OPTIONS] SOURCE [SOURCE ...] DESTINATION

``SOURCE`` arguments are interpreted as follows:

- arguments ending in ``/`` denote directories and match all subvolumes contained therein
- arguments containing shell wildcards match as expected
- arguments with no wildcards and not ending in ``/``:
	- if pointing to a subvolume, matches that subvolume verbatim
	- if pointing to a regular file, reads the btrfs send stream from file

``DESTINATION`` must reside on a btrfs filesystem.

In addition, both ``SOURCE`` and ``DESTINATION`` arguments may:

- be rsync-like SSH locations (i.e., in ``user@host:path`` form)
- be full URLs, with ``file://`` and ``ssh://`` as accepted schemas

The location syntax is similar on purpose to that of `rsync <https://rsync.samba.org>`_ and `scp <https://man.openbsd.org/scp.1>`_, and principle of least surprise applies.

Alternatively, btrsync will use ``DESTINATION`` for comparing subvolumes while not actually performing any receive operations for the following options:

- ``-o`` / ``--output-dir`` will save the send streams as files in a local directory.
- ``-O`` / ``--output-pipe`` option will pass the send stream through a shell pipeline. If ``-o`` is also supplied, the stream is then saved to a file, otherwise it is dumped to stdout.

Examples
--------

A minimal example:

.. code-block:: shell

   btrsync /snapshots/ /mnt/drive/backup

will transfer all read-only subvolumes below ``/snapshots/`` to ``/mnt/drive/backup`` after asking confirmation.

A more involved case, fetching specific subvolumes from a remote machine:

.. code-block:: shell

   btrsync -svp 'user@host:snaps/dev*' devsnaps/

will transfer subvolumes that match ``snaps/dev*`` from the SSH remote host ``host``, logged in as ``user``, to the local directory ``devsnaps/`` after asking confirmation; in addition:

- ``-s`` execute ``btrfs`` commands using ``sudo``
- ``-v`` print verbose information during transfer
- ``-p`` periodically report progress

Non-interactive invocation, useful e.g., in scripts:

.. code-block:: shell

   btrsync -yq --incremental-only /snapshots/ ssh://user@backup.example.com:1234/snaps/

will transfer subvolumes under local directory ``/snapshots/`` to the SSH host ``backup.example.com``, connected as ``user`` to port ``1234``, saving them under the remote path ``/snaps/``; in addition:

- ``-y`` proceed without asking for confirmation
- ``-q`` do not print output, except for errors
- ``--incremental-only`` skip any transfers that cannot be done incrementally

The help option provides further details:

.. code-block:: shell

   btrsync --help
