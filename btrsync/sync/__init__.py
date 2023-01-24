#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Btrfs subvolume synchronization.
"""

import asyncio
import posixpath
import itertools

from .. import btrfs
from .. import util


class BtrSync:
	"""
	Base class containing logic to sync btrfs subvolumes from a source root to a destination root.

	:param src: source btrfs root (:class:`btrsync.sync.root.BtrfsRoot`-like instance)
	:param dst: destination btrfs root (:class:`btrsync.sync.root.BtrfsRoot`-like instance)
	:param srckeys: key functions to be applied to the subvolumes of `src`, if :const:`None` use default key functions
	:param dstkeys: key functions to be applied to the subvolumes of `dst`, if :const:`None` use default key functions

	Key functions take a subvolume as argument and return a value that is then used for equality testing.
	Two subvolumes are considered equal if any of their key values compare equal and are not :const:`None`.
	The default key functions return the UUID and received UUID of subvolumes.
	"""
	DEFAULT_KEYS = (lambda v: v['uuid'], lambda v: v['received_uuid'])
	def __init__(self, src, dst, *, srckeys=None, dstkeys=None):
		self.src = src
		self.dst = dst
		self.srckeys = srckeys if srckeys is not None else self.DEFAULT_KEYS
		self.dstkeys = dstkeys if dstkeys is not None else self.DEFAULT_KEYS

	@staticmethod
	def volgroups(roots):
		"""Iterate over `roots` and their descendants in groups of COW-independent volumes."""
		g = []
		for vol in btrfs.COWTree.bfs(*roots, depth_markers=True):
			if vol is None:
				yield g
				g = []
			else:
				g.append(vol)

	@staticmethod
	def target(vol):
		"""Return :const:`True` if `vol` is to be considered for sync."""
		return True

	def parent(self, vol):
		"""Return the COW parent of `vol` to be used as basis for incremental send, or :const:`None` if unavailable."""
		for par in btrfs.COWTree.ancestors(vol):
			if par['uuid'] in self.diff[0]:
				return par
		return None

	@staticmethod
	def check(vol, parent):
		"""Return :const:`True` if the sync of `vol` with COW parent `parent` should proceed."""
		return True

	@staticmethod
	def stop(vols):
		"""Called after `vols` have been synced; return :const:`True` if sync should immediately stop."""
		return False

	async def _refresh(self, trans):
		"""Update the internal diff between source and destination roots."""
		self.srcroots, self.dstroots = await trans.try_gather(self.src.list(), self.dst.list())
		self.diff = btrfs.COWTree.diff(self.srcroots, self.dstroots, self.srckeys, self.dstkeys)

	async def sync(self, trans, *, batch=False, parallel=False, transfer_existing=False,
	               volgroups=None, target=None, parent=None, check=None, stop=None):
		"""
		Perform synchronization of subvolumes.

		Returns whether the sync was successful and all error handling is delegated to `trans`.

		:param trans: :class:`.Transfer`-like object to perform the actual send/receive operations
		:param batch: if :const:`True`, batch together multiple volumes into a single transfer
		:param parallel: if :const:`True`, run independent transfers in parallel
		:param transfer_existing: if :const:`True`, consider for transfer volumes that already exist on the destination
		:param volgroups: override for :meth:`.volgroups`
		:param target: override for :meth:`.target`
		:param parent: override for :meth:`.parent`
		:param check: override for :meth:`.check`
		:param stop: override for :meth:`.stop`
		:returns: :const:`True` if sync successful, :const:`False` if errors occured
		"""
		volgroups = self.volgroups if volgroups is None else volgroups
		target = self.target if target is None else target
		parent = self.parent if parent is None else parent
		check = self.check if check is None else check
		stop = self.stop if stop is None else stop

		def tf(vols, par):
			async def f(a):
				r = await a
				return (vols, r)
			return f(trans.transf(vols, par, self.src, self.dst))

		def mark(vols):
			for v in vols:
				self.diff[0][v['uuid']].append(None)

		await self._refresh(trans)
		finish = False
		erred = False
		for volgr in volgroups(self.srcroots):
			targets = [vol for vol in volgr if target(vol) and (transfer_existing or vol['uuid'] not in self.diff[0])]
			parents = (parent(vol) for vol in targets)
			cand = (pair for pair in zip(targets, parents) if check(*pair))
			if batch:
				packs = (
					([x[0] for x in vps], vps[0][1])
					for _, vps in util.group(
						cand,
						lambda x: (x[1]['uuid'] if x[1] is not None else None, posixpath.dirname(x[0]))
					)[0].items()
				)
			else:
				packs = (([x[0]], x[1]) for x in cand)
			transfers = (tf(vols, par) for vols, par in packs)
			transeq = asyncio.as_completed(transfers) if parallel else transfers
			for transop in transeq:
				try:
					vols, res = await transop
				except asyncio.CancelledError:
					erred = True
					if parallel:
						continue
					else:
						break
				mark(vols)
				if stop(vols):
					finish = True
					if not parallel:
						break
			if finish or erred:
				break
		return not erred


class Transfer:
	"""
	Base class implementing a transfer as required by :meth:`.BtrSync.sync`.

	:param recvpath: the path that transfers are received into
	:param replicate_dirs: if :const:`True` adapt `recvpath` to recreate the sent volumes' directory structure
	"""
	def __init__(self, *, recvpath='.', replicate_dirs=False):
		self.recvbase = recvpath
		self.replicate_dirs = replicate_dirs

	def err(self, e, *args):
		"""Called on encountering an exception `e`; expected to log the error and return successfully."""
		pass

	async def report(self, vols, par, src, dst):
		"""Called at the start of a transfer of volumes `vols` with parent `par` from `src` to `dst`."""
		pass

	async def report_done(self, vols, par, src, dst):
		"""Called when the transfer of volumes `vols` with parent `par` from `src` to `dst` has finished."""
		pass

	async def try_await(self, aw):
		"""
		Try awaiting awaitable `aw`, converting any exceptions to :exc:`asyncio.CancelledError`.

		Exceptions raised by `aw` will be logged by :meth:`.err`.
		"""
		try:
			return await aw
		except BaseException as e:
			self.err(e)
			raise asyncio.CancelledError() from e

	async def _collect(self, *tasks):
		erred = False
		for t in tasks:
			try:
				await asyncio.wait_for(t, timeout=0)
			except TimeoutError:
				pass
			except BaseException as e:
				self.err(e)
				erred = True
		if erred:
			raise asyncio.CancelledError()

	async def try_gather(self, *coroutines):
		"""
		Try running and waiting for all `coroutines`, canceling all upon error.

		Exceptions raised by the tasks will be logged by :meth:`err`.

		:raises asyncio.CancelledError: if any tasks raise an exception
		"""
		tasks = map(asyncio.create_task, coroutines)
		try:
			return await asyncio.gather(*tasks)
		except BaseException as e:
			self.err(e)
			try:
				await self._collect(*tasks)
			except asyncio.CancelledError:
				pass
			raise asyncio.CancelledError() from e

	@staticmethod
	def _sendpaths(vols, par):
		volpaths = [v['path'] for v in vols]
		parent = par['path'] if par is not None else None
		meta = {'volumes': volpaths}
		if parent is not None:
			meta['parent'] = parent
		return volpaths, parent, meta

	def _recvpath(self, volpaths):
		if self.replicate_dirs:
			voldir = posixpath.dirname(volpaths[0])
			for vp in volpaths[1:]:
				assert(posixpath.dirname(vp) == voldir)
			return posixpath.join(self.recvbase, voldir)
		else:
			return self.recvbase

	async def transf(self, vols, par, src, dst):
		"""
		Minimal quiet transfer function, as expected by :meth:`.BtrSync.sync`.

		:param vols: the subvolumes to transfer
		:param par: the parent subvolume to use for an incremental transfer
		:param src: the source btrfs root
		:param dst: the destination btrfs root
		:raises asyncio.CancelledError: if any error has occured, after logging it with :meth:`.err`
		"""
		args = (vols, par, src, dst)
		await self.try_await(self.report(*args))
		volpaths, parent, meta = self._sendpaths(vols, par)
		flow, scoro = await self.try_await(src.send(*volpaths, parent=parent))
		dcoro = await self.try_await(dst.receive(flow, self._recvpath(volpaths), meta=meta))
		await self.try_gather(scoro, dcoro, flow.pump())
		await self.try_await(self.report_done(*args))


class ProgressTransfer(Transfer):
	"""
	Transfer class providing a mechanism for logging transfer progress.

	:param period: time, in seconds, between progress reporting events
	:param prog_seq: sequence to be cycled through to indicate activity
	:param kwargs: additional keyword arguments to pass to the superclass :class:`.Transfer`'s constructor
	"""
	def __init__(self, *, period=1, prog_seq=[], **kwargs):
		super().__init__(**kwargs)
		self.period = period
		self.prog_seq = prog_seq

	async def report_progress(self, total, prev, seq):
		"""
		Called on every progress reporting event.

		:param total: currrent total bytes transferred
		:param prev: value of `total` from previous call
		:param seq: sequence to indicate activity
		"""

	async def progress(self, flow, seq):
		"""Implement progress reporting every `period` seconds."""
		cnt, prev = flow.count, 0
		while True:
			await self.report_progress(cnt, prev, seq)
			await asyncio.sleep(self.period)
			cnt, prev = flow.count, cnt

	async def transf(self, vols, par, src, dst):
		"""
		Progress reporting transfer function, as expected by `.BtrSync.sync`.

		:param vols: the subvolumes to transfer
		:param par: the parent subvolume to use for an incremental transfer
		:param src: the source btrfs root
		:param dst: the destination btrfs root
		:raises asyncio.CancelledError: if any error has occurred, after logging it with :meth:`.err`
		"""
		args = (vols, par, src, dst)
		seq = itertools.cycle(self.prog_seq)
		volpaths, parent, meta = self._sendpaths(vols, par)
		await self.try_await(self.report(*args))
		flow, scoro = await self.try_await(src.send(*volpaths, parent=parent))
		flow.stats = True
		dcoro = await self.try_await(dst.receive(flow, self._recvpath(volpaths), meta=meta))
		prog = asyncio.create_task(self.progress(flow, seq))
		try:
			await self.try_gather(scoro, dcoro, flow.pump())
		finally:
			await self._collect(prog)
		await self.try_await(self.report_done(*args))


from . import root


def default_root(protocol):
	"""
	Get the default btrfs root used to handle `protocol`.

	:param protocol: btrfs protocol to use; valid values are ``'local'`` and ``'ssh'``
	:returns: appropriate :class:`btrsync.sync.root.BtrfsRoot` subclass factory for `protocol`
	:raises ValueError: if protocol is unknown
	"""
	if protocol == 'local':
		return root.local.LocalRoot
	elif protocol == 'ssh':
		return root.ssh.SSHRoot
	else:
		raise ValueError('Unknown protocol', protocol)
