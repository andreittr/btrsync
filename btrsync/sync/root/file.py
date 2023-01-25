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

from ... import util
from ... import btrfs


class _FileRoot(BtrfsRoot):
	@staticmethod
	async def _nop():
		pass

	@classmethod
	async def get_root(cls, path, **kwargs):
		return cls(path, **kwargs), '.'

	@classmethod
	async def is_root(cls, path):
		return True

	@property
	def name(self):
		return self.rootpath


class FileRecvRoot(_FileRoot):
	"""
	Btrfs root that saves the send stream to a local file in :meth:`receive`.

	Calling :meth:`send` will raise :exc:`NotImplementedError`.
	Other methods are delegated to `subroot`, if supplied, or return no-op defaults.

	:param rootpath: directory to save the send streams into
	:param subroot: if supplied, delegate :meth:`list` and :meth:`show` to this root
	:param create_recvpath: if :const:`True`, ensure the `path` passed to :meth:`receive` exists
	"""
	def __init__(self, rootpath, *, subroot=None, create_recvpath=False):
		self.rootpath = rootpath
		self.subroot = subroot
		self.create_recvpath = create_recvpath
		self._args = ('rootpath',)
		self._kwargs = ('subroot', 'create_recvpath')

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

	async def receive(self, flow, path='.', *, meta={}):
		try:
			vols = meta['volumes']
		except KeyError:
			vols = ['btrsync-dump']
		fn = posixpath.basename(vols[0])
		if len(vols) > 1:
			fn += '_et-al'
		fn += '.btrfs_stream'
		odir = os.path.join(self.rootpath, path)
		if self.create_recvpath:
			os.makedirs(odir, exist_ok=True)
		flow.connect_to_fd(open(os.path.join(odir, fn), 'wb', buffering=0))
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
		return [btrfs.Vol(path=self.rootpath, uuid=str(uuid.uuid4()), received_uuid=None)]

	async def show(self, path='.'):
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