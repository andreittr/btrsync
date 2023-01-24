#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Data structures and functions manipulating btrfs subvolumes.
"""

import posixpath
import pathlib

from collections import defaultdict

from .. import util


FSTREE = '<FS_TREE>'
"""Path of the btrfs filesystem root, as printed by ``btrfs-progs``."""


class Vol(dict):
	"""
	Helper class for manipulating btrfs subvolumes.

	Subvolumes are dicts of (property: value) pairs.
	The properties exposed are those provided by ``btrfs subvolume list``
	with the addition of computed COW parent and successors.
	"""
	_P = '_cowpreq'
	_S = '_cowsucc'

	def __init__(self, *args, parent=None, succs=[], **kwargs):
		super().__init__(*args, **kwargs)
		self.parent = parent
		self.succs.extend(succs)

	@property
	def parent(self):
		"""COW parent of this subvolume, or :const:`None` if self-standing."""
		return self[self._P]
	@parent.setter
	def parent(self, v):
		self[self._P] = v

	@property
	def succs(self):
		"""Volumes for which this subvolume is a COW parent."""
		try:
			return self[self._S]
		except KeyError:
			self[self._S] = []
			return self[self._S]


class COWTree:
	"""
	Build a hierarchy of btrfs subvolumes based on snapshotting (COW) parentage.

	:param subvols: the sequence of subvolumes (:class:`dict` instances keyed by subvolume properties) to process
	:param check: a function that takes a subvolume as argument and returns a boolean whether to consider it for parentage; by default accept all
	"""
	def __init__(self, subvols, check=None):
		def _finish(vol):
			if vol['_check']:
				pq = vol.parent
				if pq is None:
					self._roots.append(vol)
				else:
					pq.succs.append(vol)

		def _handle_preq(pq):
			for vol in preq_waitlist[pq['uuid']]:
				vol.parent = pq.parent
				_handle_preq(vol)
				_finish(vol)
			del preq_waitlist[pq['uuid']]

		def _handle_sibtree(vol, *sibs, maxdepth=0):
			for sib in util.bfs(lambda v: reversed(v['_chld']), *reversed(sibs), maxdepth=maxdepth):
				if sib['_check']:
					vol.parent = sib
					return True
			return False

		def _handle_par(vol, par):
			r = True
			if not _handle_sibtree(vol, par, maxdepth=1):
				try:
					vol.parent = par.parent
				except KeyError:
					r = False
			par['_chld'].append(vol)
			return r

		def _handle_parwait(par):
			uid = par['uuid']
			for orph in parent_waitlist[uid]:
				if _handle_par(orph, par):
					_handle_preq(orph)
					_finish(orph)
				else:
					preq_waitlist[uid].append(orph)
			del parent_waitlist[uid]

		parent_waitlist = defaultdict(list)
		preq_waitlist = defaultdict(list)

		self.vols = {}
		self._roots = []

		_check = (lambda v: True) if check is None else check

		for volume in subvols:
			vol = Vol(volume)
			vol['_check'] = _check(vol)
			vol['_chld'] = []

			puid = vol['parent_uuid']
			if puid is None:
				vol.parent = None
				_finish(vol)
			elif puid in self.vols:
				if _handle_par(vol, self.vols[puid]):
					_handle_preq(vol)
					_finish(vol)
				else:
					preq_waitlist[puid].append(vol)
			else:
				parent_waitlist[puid].append(vol)
			self.vols[vol['uuid']] = vol
			_handle_parwait(vol)

		for par, orphans in parent_waitlist.items():
			sibs = []
			for vol in orphans:
				if not _handle_sibtree(vol, *sibs, maxdepth=0):
					vol.parent = None
				sibs.append(vol)
				_handle_preq(vol)
				_finish(vol)
		assert(not preq_waitlist)

	@property
	def roots(self):
		"""Roots of the computed COW hierarchy."""
		return self._roots

	@staticmethod
	def dfs(node):
		"""Iterate, in a depth-first search, over `node` and its COW descendants."""
		return util.dfs(lambda v: v.succs, node)

	@staticmethod
	def bfs(*nodes, **kwargs):
		"""Iterate, in a breadth-first search, over `nodes` and their COW descendants."""
		return util.bfs(lambda v: v.succs, *nodes, **kwargs)

	@staticmethod
	def ancestors(node):
		"""Iterate over the COW ancestors of `node`, including itself."""
		while node is not None:
			yield node
			node = node.parent

	@staticmethod
	def diff(aroots, broots, akeys, bkeys):
		"""
		Perform a diff operation over two sets of COW hierarchies, identifying common subvolumes based on custom key functions.

		Two subvolumes are considered identical if any non-None results of their key functions match.

		:param aroots: the first sequence of COW hierarchies to compare
		:param broots: the second sequence of COW hierarchies to compare
		:param akeys: the sequence of key functions to apply to `aroots`
		:param bkeys: the sequence of key functions to apply to `broots`
		:returns: tuple of dicts (`coma`, `comb`), indexing, by subvolume uuid, the elements of `aroots` and `broots` respectively,
		          which have corresponding identical subvolumes in the other set
		"""
		coma = defaultdict(list)
		comb = defaultdict(list)
		agrp = util.group(COWTree.bfs(*aroots), *akeys)
		bgrp = util.group(COWTree.bfs(*broots), *bkeys)
		for ag in agrp:
			for ak in ag:
				if ak is not None:
					for bg in bgrp:
						if ak in bg:
							for avol in ag[ak]:
								coma[avol['uuid']].extend(bg[ak])
							for bvol in bg[ak]:
								comb[bvol['uuid']].extend(ag[ak])
		return coma, comb


def abspaths(vols, rootpath):
	"""
	Process a sequence of btrfs volumes, making all relative paths absolute; absolute paths are left unchanged.

	:param vols: the sequence of btrfs subvolumes to process
	:param rootpath: the absolute path that subvolume paths are relative to
	:returns: iterator over the modified subvolumes
	:raises ValueError: if `rootpath` is not absolute (does not start with :data:`.FSTREE`)
	"""
	if not rootpath.startswith(FSTREE):
		raise ValueError(f'Root path must start with {FSTREE}')
	for v in vols:
		vp = v['path']
		if vp.startswith(FSTREE):
			yield v
		else:
			nv = v.copy()
			nv['path'] = util.path_merge(rootpath, vp, root=FSTREE, path=posixpath)
			yield nv

def relpaths(vols, rootpath):
	"""
	Process a sequence of btrfs volumes, making all paths below a chosen root relative to that root; other paths are left unchanged.

	:param vols: the sequence of btrfs subvolumes to process
	:param rootpath: the absolute path that subvolume paths are to be made relative to
	:returns: iterator over the modified subvolumes
	:raises ValueError: if `rootpath` is not absolute (does not start with :data:`.FSTREE`)
	"""
	if not rootpath.startswith(FSTREE):
		raise ValueError(f'Root path must start with {FSTREE}')
	relparts = pathlib.PurePosixPath(rootpath).parts[1:]
	relrootpath = posixpath.join(*relparts) if relparts else ''
	for v in vols:
		vp = v['path']
		if vp.startswith(rootpath):
			nv = v.copy()
			nv['path'] = posixpath.relpath(vp, rootpath)
			yield nv
		elif relrootpath and not vp.startswith(FSTREE):
			nv = v.copy()
			nv['path'] = posixpath.relpath(vp, relrootpath)
			yield nv
		else:
			yield v


from . import cmd, parse
