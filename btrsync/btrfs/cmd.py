#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Programmatically generate ``btrfs`` subcommand invocations.
"""

import itertools

from .. import util


def list(path, *, list_all=False, readonly=False, fields='pcguqR'):
	"""
	Generate a ``btrfs subvolume list`` command.

	:param path: the target path to list
	:param list_all: if :const:`True`, list all subvolumes in the filesystem (btrfs option ``-a``),
	                 otherwise only direct descendants of `path` (btrfs option ``-o``)
	:param readonly: if :const:`True`, list only readonly subvolumes (btrfs option ``-r``)
	:param fields: flags selecting the subvolume fields to print (see ``btrfs-subvolume(8)``); default is all supported
	:returns: :class:`btrsync.util.Cmd` instance of the desired btrfs list command
	:raises ValueError: if unsupported fields are supplied
	"""
	FIELDS = 'pcguqR'
	for f in fields:
		if f not in FIELDS:
			raise ValueError(f"Unknown field `{f}'; allowed fields are: {', '.join(FIELDS)}")
	args = ['subvolume', 'list', '-t']
	args.append('-a' if list_all else '-o')
	if readonly:
		args.append('-r')
	if fields:
		args.append('-' + fields)
	args.append(path)
	return util.Cmd('btrfs', args)


def send(*paths, parent=None, clones=[], keep_compressed=False):
	"""
	Generate a ``btrfs send`` command.

	:param paths: the target paths to send
	:param parent: path of the parent volume for incremental sends (btrfs-send option ``-p``)
	:param clones: sequence of paths of clone subvolumes (btrfs-send option ``-c``)
	:param keep_compressed: if :const:`True` instruct btrfs-send to output compressed blocks unchanged (btrfs-send option ``--compressed-data``)
	:returns: :class:`btrsync.util.Cmd` instance of the desired btrfs send command
	:raises ValueError: if no paths are given
	"""
	if not paths:
		raise ValueError('Must specify at least one path to send')
	args = ['send']
	if keep_compressed:
		args.append('--compressed-data')
	if parent is not None:
		args.extend(('-p', parent))
	if clones:
		args.extend(itertools.chain.from_iterable(('-c', cl) for cl in clones))
	args.extend(paths)
	return util.Cmd('btrfs', args)


def receive(path, *, force_decompress=False):
	"""
	Generate a ``btrfs receive`` command.

	:param path: the path to receive into
	:param force_decompress: if :const:`True`, force the decompression of any compressed blocks in the stream (btrfs-receive option ``--force-decompress``)
	:returns: :class:`btrsync.util.Cmd` instance of the desired btrfs receive command
	"""
	args = ['receive']
	if force_decompress:
		args.append('--force-decompress')
	args.append(path)
	return util.Cmd('btrfs', args)


def show(path, *, uuid=None, rootid=None):
	"""
	Generate a ``btrfs subvolume show`` command.

	:param path: path of the target subvolume or filesystem
	:param uuid: show information about subvolume with specified UUID; cannot be used together with `rootid`
	:param rootid: show information about subvolume with specified root ID; cannot be used together with `uuid`
	:returns: :class:`btrsync.util.Cmd` instance of the desired btrfs show command
	:raises ValueError: if both `uuid` and `rootid` are specified
	"""
	if uuid is not None and rootid is not None:
		raise ValueError("At most one of `uuid' and `rootid' may be specified")
	args = ['subvolume', 'show']
	if uuid is not None:
		args.extend(('-u', uuid))
	elif rootid is not None:
		args.extend(('-r', rootid))
	args.append(path)
	return util.Cmd('btrfs', args)
