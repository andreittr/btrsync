#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Generic interface to a btrfs filesystem.
"""

import abc


class BtrfsError(Exception):
	"""Exception class encapsulating btrfs-specific errors."""
	def __str__(self):
		if self.args:
			*ctx, err = self.args
			s = f'"{", ".join(ctx)}"' if ctx else 'BTRFS operation'
			return f'{s} failed:\n\t{err}'
		else:
			return super().__str__()


class BtrfsRoot(abc.ABC):
	"""Abstract base class for implementing btrfs roots."""
	_args = ()
	_kwargs = ()

	def _reprargs(self):
		return ', '.join((', '.join(f'{repr(getattr(self, arg))}' for arg in self._args),
		                  ', '.join(f'{arg}={repr(getattr(self, arg))}' for arg in self._kwargs)))

	def __repr__(self):
		return f'{type(self).__name__}({self._reprargs()})'

	@classmethod
	@abc.abstractmethod
	async def get_root(cls, path, **kwargs):
		"""
		Determine the subvolume root containing `path` and return a btrfs root instance anchored there.

		:param path: the path to examine
		:param kwargs: keyword arguments passed on to the btrfs root constructor
		:returns: a tuple ``(root, relpath)`` containing the requested btrfs root instance
		          along with the component of `path` relative to the root path
		:raises BtrfsError: if the operation fails
		"""

	@classmethod
	@abc.abstractmethod
	async def is_root(cls, path):
		"""Return whether `path` points to a btrfs subvolume root or not."""

	@property
	@abc.abstractmethod
	def name(self):
		"""Human-readable name identifying this root and the location it refers to."""

	@abc.abstractmethod
	async def list(self):
		"""List available subvolumes within this root, as a sequence of COW hierarchy roots."""

	@abc.abstractmethod
	async def show(self, path='.'):
		"""Return detailed information about the subvolume pointed to by `path`."""

	@abc.abstractmethod
	async def send(self, *paths, parent=None, clones=[]):
		"""
		Set up a send operation of `paths` with parent `parent` and clones `clones`.

		:param paths: the paths of the subvolumes to send
		:param parent: if not :const:`None`, the path of the parent subvolume to use for incremental send
		:param clones: sequence of paths of clone subvolumes
		:returns: a tuple ``(flow, send_coro)`` containing the send :class:`btrsync.util.Flow`
			and a coroutine that finalizes the send operation when run
		"""

	@abc.abstractmethod
	async def receive(self, flow, path='.', *, meta={}):
		"""
		Perform a receive operation into `path` using the send stream provided by `flow`.

		:param flow: a :class:`btrsync.util.Flow` containing the btrfs send stream
		:param path: the relative path to receive into
		:param meta: (optional) additional metadata about the send stream
		:returns: a coroutine that finalizes the receive operation when run
		"""


from . import local, ssh, file
