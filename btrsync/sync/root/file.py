#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Btrfs roots implemented using local file I/O.
"""

import os
import posixpath
import uuid

from . import BtrfsRoot
from . import _exec

from ... import util
from ... import btrfs


class _FileRoot(BtrfsRoot):
	@staticmethod
	async def _nop():
		pass

	@classmethod
	async def get_root(cls, path, **kwargs):
		"""No-op; call constructor with `path`."""
		return cls(path, **kwargs), '.'

	@classmethod
	async def is_root(cls, path):
		"""No-op; return :const:`True`."""
		return True

	@property
	def name(self):
		return self.rootpath


class FileRecvRoot(_FileRoot, _exec.ExecBtrfsRoot):
	"""
	Btrfs root that saves the send stream to a local file in :meth:`receive`.

	Calling :meth:`send` will raise :exc:`NotImplementedError`.
	Other methods are delegated to `subroot`, if supplied, or return no-op defaults.

	:param rootpath: directory to save the send streams into;
		if :const:`None` will not save any files and `dump_pipe` must be supplied
	:param subroot: if supplied, delegate :meth:`list` and :meth:`show` to this root
	:param create_recvpath: if :const:`True`, ensure the `path` passed to :meth:`receive` exists
	:param namer: function that takes the send stream metadata and returns a file name, if :const:`None` use default
	:param dump_pipe: a sequence of commands to run in a pipeline and pass the send stream through before saving
	:param ext: extension to append to saved file names
	"""
	def __init__(self, rootpath, *, subroot=None, create_recvpath=False,
	             namer=None, dump_pipe=[], ext=''):
		if rootpath is None and not dump_pipe:
			raise ValueError('dump_pipe required for rootpath==None')
		self.rootpath = rootpath
		self.subroot = subroot
		self.create_recvpath = create_recvpath
		self.namer = namer
		self.dump_pipe = dump_pipe
		self.ext = ext
		self._args = ('rootpath',)
		self._kwargs = ('subroot', 'create_recvpath', 'namer', 'dump_pipe', 'ext')
		if namer is not None:
			self._namer = namer

	@staticmethod
	def _namer(meta):
		try:
			vols = meta['volumes']
		except KeyError:
			vols = ['btrsync-dump']
		fn = posixpath.basename(vols[0])
		if len(vols) > 1:
			fn += '_et-al'
		return fn + '.btrfs_stream'

	async def list(self, *args, **kwargs):
		if self.subroot is not None:
			return await self.subroot.list(*args, **kwargs)
		else:
			return ()

	async def show(self, *args, **kwargs):
		if self.subroot is not None:
			return await self.subroot.show(*args, **kwargs)
		else:
			return self.rootpath, {}

	async def send(self, *args, **kwargs):
		"""Not implemented; raises :exc:`NotImplementedError`."""
		raise NotImplementedError('send() called in receive-only root')

	@staticmethod
	async def _runclose(coro, f):
		try:
			await coro
		finally:
			f.close()

	async def receive(self, flow, path='.', *, meta={}):
		if self.rootpath is None:
			pin = flow.connect_fd()
			return self._run_checked(*util.Cmd.pipeline(self.dump_pipe), stdin=pin, stdout=None)
		else:
			fn = self._namer(meta) + self.ext
			odir = os.path.join(self.rootpath, path)
			if self.create_recvpath:
				os.makedirs(odir, exist_ok=True)
			ofile = open(os.path.join(odir, fn), 'wb', buffering=0)
			if self.dump_pipe:
				pin = flow.connect_fd()
				return self._runclose(
					self._run_checked(*util.Cmd.pipeline(self.dump_pipe), stdin=pin, stdout=ofile),
					ofile
				)
			else:
				flow.connect_to_fd(ofile)
				return self._nop()


class FileSendRoot(_FileRoot):
	"""
	Read-only btrfs root implemented using local file I/O.

	Calling :meth:`receive` will raise :exc:`NotImplementedError`.

	:param rootpath: path to the target input file
	"""
	def __init__(self, rootpath):
		self.rootpath = rootpath
		self._args = ('rootpath',)

	async def list(self):
		"""No-op; return a single volume with path `rootpath` and a random uuid."""
		return [btrfs.Vol(path=self.rootpath, uuid=str(uuid.uuid4()), received_uuid=None)]

	async def show(self, path='.'):
		"""No-op; return `rootpath` and empty properties."""
		return self.rootpath, {}

	async def send(self, *paths, parent=None, clones=[]):
		if len(paths) > 1 or paths[0] != self.rootpath:
			raise ValueError(f'Cannot send path other than {self.rootpath}')
		return util.FileFlow(open(self.rootpath, 'rb', buffering=0)), self._nop()

	async def receive(self, flow, path='.', *, meta={}):
		"""Not implemented; raises :exc:`NotImplementedError`."""
		raise NotImplementedError('receive() called in read-only root')


def FileRoot(*, sudo=None):
	"""Return an appropriate btrfs root class sourced from file I/O."""
	return FileSendRoot

def DumpRoot(*, sudo=None):
	"""Return an appropriate btrfs root class for dumping to a local file."""
	return FileRecvRoot
