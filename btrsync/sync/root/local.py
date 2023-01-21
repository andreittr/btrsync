#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Btrfs roots implemented using locally executed ``btrfs`` commands.
"""

import os
import asyncio
import posixpath

from . import BtrfsError, BtrfsRoot

from ... import util
from ... import btrfs
from ... import cmdex


SUDO = util.Cmd('sudo')


class LocalBtrfsRoot(BtrfsRoot):
	"""
	Btrfs root implemented using local execution of ``btrfs`` commands, anchored at `rootpath`.

	:param rootpath: path to the target subvolume root
	:param scope: determines the scope of accessible subvolumes:
		``'all'`` includes all subvolumes reachable from `rootpath`,
		``'strict'`` includes only subvolumes directly contained in `rootpath`, and
		``'isolated'`` behaves like ``'strict'``, but also excludes other subvolumes from computing parentage
	:param readonly: if :const:`True`, list only readonly subvolumes
	:param create_recvpath: if :const:`True`, ensure the `path` passed to :meth:`.receive` exists
	:raises ValueError: for an invalid value of `scope`
	"""
	_SCOPES = ('all', 'strict', 'isolated')
	def __init__(self, rootpath, *, scope='all', readonly=True, create_recvpath=False):
		self.localroot = rootpath
		if scope not in self._SCOPES:
			raise ValueError(f"`scope' must be one of {self._SCOPES}")
		self.scope = scope
		self.readonly = readonly
		self.create_recvpath = create_recvpath
		self._args = ('localroot',)
		self._kwargs = ('scope', 'readonly', 'create_recvpath')
		self._isolated = scope == 'isolated'
		self._strict = scope != 'all'
		self._fsroot = None

	def _reprargs(self):
		return ', '.join((', '.join(f'{repr(getattr(self, arg))}' for arg in self._args),
		                  ', '.join(f'{arg}={repr(getattr(self, arg))}' for arg in self._kwargs)))

	def __repr__(self):
		return f'{type(self).__name__}({self._reprargs()})'

	@staticmethod
	def wrapcmds(cmds):
		"""Return `cmds` unchanged; override to customize executed commands."""
		yield from cmds

	@classmethod
	async def _run(cls, *cmds, **kwargs):
		return (await cmdex.ex_out(*cls.wrapcmds(cmds), **kwargs))[-1]

	@classmethod
	async def _run_checked(cls, *cmds, msg='', **kwargs):
		ret, (stdout, stderr) = await cls._run(*cmds, **kwargs)
		if ret != 0:
			raise BtrfsError(': '.join((stderr.decode('utf-8').rstrip(), msg)))
		return ret, (stdout, stderr)

	@classmethod
	async def is_root(cls, path):
		ret, (stdout, stderr) = await cls._run(btrfs.cmd.show(path), stdin=cmdex.DEVNULL)
		err = stderr.decode('utf-8')
		if ret != 0:
			if 'Not a Btrfs subvolume' in err or 'No such file or directory' in err:
				return False
			else:
				raise BtrfsError(': '.join((err.rstrip(), path)))
		else:
			return True

	@classmethod
	async def get_root(cls, path, **kwargs):
		rpath = path
		while rpath != '/' and not await cls.is_root(rpath):
			rpath = os.path.dirname(rpath)
		if rpath == '/' and not await cls.is_root(rpath):
			raise BtrfsError('Cannot find root')
		return cls(rpath, **kwargs), os.path.relpath(path, rpath)

	def _localpath(self, path):
		if not util.is_subpath(path):
			raise ValueError('Path must be relative and cannot escape its base directory')
		return os.path.join(self.localroot, path)

	async def _chk(self):
		if self._fsroot is None:
			ret, (stdout, stderr) = await self._run_checked(
				btrfs.cmd.show(self.localroot), msg=self.localroot, stdin=cmdex.DEVNULL
			)
			rp, stats = btrfs.parse.Show.from_stdout(stdout)
			self._fsroot = posixpath.join(btrfs.FSTREE, '' if rp == '/' else rp)

	async def list(self):
		await self._chk()
		alcmd = btrfs.cmd.list(self.localroot, list_all=not self._isolated, readonly=False, fields='uqR')
		rocmd = btrfs.cmd.list(self.localroot, list_all=not self._strict, readonly=self.readonly, fields='u')

		ret, (stdout, stderr) = await self._run_checked(rocmd, msg=self.localroot, stdin=cmdex.DEVNULL)
		rvs = util.index(btrfs.parse.List.from_stdout(stdout), lambda v: v['uuid'])[0]
		ret, (stdout, stderr) = await self._run_checked(alcmd, msg=self.localroot, stdin=cmdex.DEVNULL)
		allvols = btrfs.relpaths(btrfs.parse.List.from_stdout(stdout), self._fsroot)

		ct = btrfs.COWTree(allvols, lambda v: v['uuid'] in rvs and not v['path'].startswith(btrfs.FSTREE))
		return ct.roots

	async def show(self, path='.'):
		tpath = self._localpath(path)
		await self._chk()
		ret, (stdout, stderr) = await self._run_checked(btrfs.cmd.show(tpath), msg=tpath, stdin=cmdex.DEVNULL)
		return btrfs.parse.Show.from_stdout(stdout)

	async def send(self, *paths, parent=None, clones=[]):
		tpaths = (self._localpath(p) for p in paths)
		if parent is not None:
			parent = self._localpath(parent)
		clones = (self._localpath(c) for c in clones)
		await self._chk()
		r, w = map(util.FileDesc, os.pipe())
		return util.PipeFlow(r), self._dosend(w, btrfs.cmd.send(*tpaths, parent=parent, clones=clones))

	async def _dosend(self, fildes, cmd):
		try:
			await self._run_checked(cmd, msg=cmd.shellify(), stdin=cmdex.DEVNULL, stdout=fildes.fd)
		finally:
			fildes.close()

	async def receive(self, flow, path='.'):
		tpath = self._localpath(path)
		await self._chk()
		return self._dorecv(tpath, flow.connect_pipe())

	async def _dorecv(self, tpath, fildes):
		if self.create_recvpath:
			await self._run_checked(util.Cmd('mkdir', ['-p', tpath]), msg=tpath)
		fildes.closed = True
		await self._run_checked(btrfs.cmd.receive(tpath), msg=tpath, stdin=fildes.fd)


def LocalRoot(*, sudo=False):
	"""
	Return an appropriate btrfs root class for accessing local btrfs filesystems.

	:param sudo: if :const:`True`, use ``sudo`` to execute ``btrfs`` commands
	"""
	if sudo:
		class SudoLocalRoot(LocalBtrfsRoot):
			@staticmethod
			def wrapcmds(cmds):
				yield from (c.wrap(SUDO) for c in cmds)

			def __repr__(self):
				return f'LocalRoot(sudo=True)({self._reprargs()})'
		return SudoLocalRoot
	else:
		return LocalBtrfsRoot
