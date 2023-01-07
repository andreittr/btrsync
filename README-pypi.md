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

## Usage
### Command-line
Run the main command-line interface with
```
python -m btrsync.cli [OPTIONS] SOURCE [SOURCE ...] DESTINATION
```
(replace `python` with `python3` if your system's `python` defaults to Python 2)

Alternatively, you can directly run
```
btrsync [OPTIONS] SOURCE [SOURCE ...] DESTINATION
```

`SOURCE` arguments are interpreted as follows:
- Arguments ending in `/` denote directories and match all subvolumes contained therein
- Arguments containing shell wildcards match as expected
- Non-directory arguments with no wildcards match subvolumes verbatim

`DESTINATION` must reside on a btrfs filesystem.

Additionally, both `SOURCE` and `DESTINATION` arguments may:
- be rsync-like SSH locations (i.e., in `user@host:path` form)
- be full URLs, with `file://` and `ssh://` as accepted schemas

The location syntax is similar on purpose to that of [rsync](https://rsync.samba.org/) and [scp](https://man.openbsd.org/scp.1), and principle of least surprise applies.

#### Examples
A minimal example:
```
btrsync /snapshots/ /mnt/drive/backup
```
will transfer all read-only subvolumes below `/snapshots/` to `/mnt/drive/backup` after asking confirmation.

A more involved case, fetching specific subvolumes from a remote machine:
```
btrsync -svp 'user@host:snaps/dev*' devsnaps/
```
will transfer subvolumes that match `snaps/dev*` from the SSH remote host `host`, logged in as `user`, to the local directory `devsnaps/` after asking confirmation; in addition:
- `-s` execute `btrfs` commands using `sudo`
- `-v` print verbose information during transfer
- `-p` periodically report progress

Non-interactive invocation, useful e.g., in scripts:
```
btrsync -yq --incremental-only /snapshots/ ssh://user@backup.example.com:1234/snaps/
```
will transfer subvolumes under local directory `/snapshots/` to the SSH host `backup.example.com`, connected as `user` to port `1234`, saving them under the remote path `/snaps/`; in addition:
- `-y` proceed without asking for confirmation
- `-q` do not print output, except for errors
- `--incremental-only` skip any transfers that cannot be done incrementally

The help option provides further details:
```
btrsync --help
```

## API

See the [API Reference](https://btrsync.readthedocs.io/en/latest/api.html) section of the documentation.
