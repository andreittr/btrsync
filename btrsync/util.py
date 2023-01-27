#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Various general purpose utility classes and functions.
"""

import io
import os
import abc
import shlex
import asyncio
import itertools

from collections import deque
from collections import namedtuple
from collections import defaultdict


class Flow(abc.ABC):
	"""
	Abstract base class for a flow of bytes that can be exposed through different interfaces.

	Flows are set up to expose a specific interface with one of the ``connect_*`` methods.
	Subsequently, running the coroutine returned by :meth:`pump` handles I/O and any necessary processing.
	A tally of transmitted bytes can be found in :attr:`count` if :attr:`stats` is :const:`True`.
	"""
	def __init__(self):
		self._stats = False
		self._count = None
		self._pump = None

	@property
	def stats(self):
		"""If :const:`True`, :attr:`count` will tally bytes transmitted."""
		return self._stats
	@stats.setter
	def stats(self, val):
		self._stats = bool(val)

	@property
	def count(self):
		"""Total bytes transmitted if :attr:`stats` is :const:`True`, :const:`None` otherwise."""
		return self._count

	def pump(self):
		"""
		Return a coroutine that handles data flow when run.

		:raises ValueError: if called before one of the ``connect_*`` methods
		"""
		if self._pump is None:
			raise ValueError('pump called before connect_*')
		else:
			return self._pump

	@abc.abstractmethod
	def connect_fd(self):
		"""
		Expose flow as a raw file descriptor.

		:returns: a file-like object backed by a file descriptor
		"""

	@abc.abstractmethod
	def connect_pipe(self):
		"""
		Expose flow as a UNIX pipe.

		:returns: a file-like object backed by the read end of a UNIX pipe
		"""

	@abc.abstractmethod
	def connect_to_fd(self, f):
		"""Direct flow to file-like object `f` that provides a file descriptor."""


def _splice(r, w, n):
	"""Fallback for :func:`os.splice`."""
	d = os.read(r, n)
	if d:
		os.write(w, d)
	return len(d)


class _FdFlow(Flow):
	"""
	Base class for flow sourced from a file descriptor.

	:param f: file-like object backed by a file descriptor
	"""
	def __init__(self, f):
		super().__init__()
		self._f = f

	@staticmethod
	async def _nop():
		pass

	def _splice(self, r, w, n):
		try:
			return self._spl(r, w, n)
		except AttributeError:
			try:
				r = os.splice(r, w, n)
				self._spl = os.splice
			except (AttributeError, OSError):
				r = _splice(r, w, n)
				self._spl = _splice
			return r

	async def _pipe_pump(self, r, w):
		"""Byte pump reading from `r` into `w` and tallying the byte count into :attr:`count`."""
		def fdpump(r, w):
			NBYTES = 2**20
			c = 0
			while True:
				n = self._splice(r, w, NBYTES)
				if not n:
					break
				c += n
				self._count = c
		try:
			await asyncio.to_thread(fdpump, r.fileno(), w.fileno())
		finally:
			r.close()
			w.close()

	def connect_to_fd(self, f):
		self._pump = self._pipe_pump(self._f, f)
		self._count = 0


class PipeFlow(_FdFlow):
	"""
	Flow sourced from the read end of a UNIX pipe.

	:param f: file-like object backed by a file descriptor of the read end of the pipe
	"""
	def connect_fd(self):
		return self.connect_pipe()

	def connect_pipe(self):
		if self.stats:
			r, w = map(io.FileIO, os.pipe(), ('r', 'w'))
			self._pump = self._pipe_pump(self._f, w)
			self._count = 0
			return r
		else:
			self._pump = self._nop()
			return self._f


class FileFlow(_FdFlow):
	"""
	Flow sourced from a locally opened file.

	:param f: file-like object backed by a file descriptor
	"""
	def connect_fd(self):
		if self.stats:
			return self.connect_pipe()
		else:
			self._pump = self._nop()
			return self._f

	def connect_pipe(self):
		r, w = map(io.FileIO, os.pipe(), ('r', 'w'))
		self._pump = self._pipe_pump(self._f, w)
		self._count = 0
		return r


class Cmd(namedtuple('Cmd', ['prg', 'args'], defaults=((),))):
	"""Convenience class for parsing shell commands to and from a ``(program, arguments)`` representation."""
	@classmethod
	def from_cmdstr(cls, cmd):
		"""Parse a shell command string into a :class:`.Cmd` representation."""
		s = shlex.shlex(cmd, posix=True)
		s.whitespace_split = True
		prg, *args = s
		return cls(prg, args)

	@classmethod
	def seq(cls, seq):
		"""Parse a sequence of shell command strings into :class:`.Cmd` representations."""
		return (cls.from_cmdstr(c) for c in seq)

	@classmethod
	def pipeline(cls, pipe):
		s = shlex.shlex(pipe, posix=True, punctuation_chars=' ')
		return (cls.from_cmdstr(' '.join(toks))
			for toks in itertools.takewhile(bool,
				([shlex.quote(tok)
					for tok in itertools.takewhile(lambda x: x != '|', s)]
				for _ in itertools.count())
			)
		)

	def shellify(self):
		"""Return a properly shell-escaped command string form of `self`."""
		tok = [shlex.quote(self.prg)]
		tok.extend(shlex.quote(x) for x in self.args)
		return ' '.join(tok)

	def pipe_arg(self, pipe):
		"""
		Return a new :class:`.Cmd` with a shell pipeline as last argument.

		:param pipe: sequence of :class:`.Cmd` that form the pipeline
		:returns: the new :class:`.Cmd` instance
		"""
		args = list(self.args)
		args.append(' | '.join(cmd.shellify() for cmd in pipe))
		return type(self)(self.prg, args)

	def wrap(self, outer, *, shellfmt=False, endmark=None):
		"""
		Return a new :class:`.Cmd` that passes `self` as arguments to `outer`.

		:param outer: the outer command that receives `self` as arguments
		:param shellfmt: if :const:`True`, pass a shell-escaped form of `self` as a single last argument to `outer`;
		                 if :const:`False`, :attr:`prg` along with :attr:`args` are passed as individual arguments to `outer`
		:param endmark: if not :const:`None`, append `endmark` as final argument to `outer`, after `self`
		:returns: the new wrapped :class:`.Cmd` instance
		"""
		args = list(outer.args) + ([self.shellify()] if shellfmt else [self.prg] + list(self.args))
		if endmark:
			args.append(endmark)
		return type(self)(outer.prg, args)


def dfs(childf, node):
	"""
	Generic depth-first search iterator over `node` using `childf` to determine child nodes.

	:param childf: function such that ``childf(node)`` returns a sequence of child nodes
	:param node: the starting node for depth-first search
	"""
	stk = [node]
	while stk:
		n = stk.pop()
		stk.extend(reversed(childf(n)))
		yield n

def bfs(childf, *nodes, maxdepth=None, depth_markers=False):
	"""
	Generic breadth-first search iterator over `nodes` using `childf` to determine child nodes.

	:param childf: function such that ``childf(node)`` returns a sequence of child nodes
	:param nodes: the starting set of nodes for breadth-first search
	:param maxdepth: if not :const:`None`, stop after returning nodes at this depth (`nodes` are at depth 0)
	:param depth_markers: if :const:`True`, return a :const:`None` as marker after exhausting all nodes at a particular depth
	"""
	q = deque(nodes)
	q.append(None)
	depth = 0
	while q:
		if maxdepth is not None and depth > maxdepth:
			break
		n = q.popleft()
		if n is None:
			if q:
				q.append(None)
			depth += 1
			if depth_markers:
				yield None
		else:
			q.extend(childf(n))
			yield n


def index(seq, *keys):
	"""
	Index sequence `seq` with a series of `keys`.

	:param seq: the sequence to process
	:param keys: a sequence of functions that take an element from `seq` and return a unique index value
	:returns: a list of dicts indexed by each key in `keys`, with values elements from `seq`
	:raises ValueError: if two elements of `seq` index to the same value for any of the `keys`
	"""
	rv = [{} for _ in keys]
	for el in seq:
		for i, key in enumerate(keys):
			k = key(el)
			if k in rv[i]:
				raise ValueError(f'Duplicate index {k}')
			else:
				rv[i][k] = el
	return rv

def group(seq, *keys):
	"""
	Group items in sequence `seq` by `keys`.

	:param seq: the sequence to process
	:param keys: a sequence of functions that take an element from `seq` and return a group index
	:returns: a list of dicts indexed by each key in `keys`, with values lists of elements from `seq` that share a group index
	"""
	rv = [defaultdict(list) for _ in keys]
	for el in seq:
		for i, key in enumerate(keys):
			rv[i][key(el)].append(el)
	return rv


def path_merge(a, b, *, root='/', path=os.path):
	"""
	Join paths `a` and `b` after removing the longest prefix of `b` that is also a suffix of `a`.

	:param a: the left-hand path to be merged
	:param b: the right-hand path to be merged
	:param root: the root directory for `a` beyond which one cannot go further up
	:param path: the path module to use (e.g. :mod:`os.path`, :mod:`posixpath`, etc.)
	:returns: the merged path
	"""
	head = a
	tail = ''
	while head and head != root:
		head, base = path.split(head)
		tail = path.join(base, tail) if tail else base
		if path.commonpath((tail, b)) == tail:
			return path.join(head, b)
	else:
		return path.join(a, b)

def is_subpath(p, *, path=os.path):
	"""
	Determine whether `p` is a subpath, i.e., `p` is relative and does not go above its parent directory.

	:param p: the path to examine
	:param path: the path module to use (e.g. :mod:`os.path`, :mod:`posixpath`, etc.)
	:returns: boolean whether `p` is a subpath
	"""
	return not(path.isabs(p) or path.normpath(p).startswith('..'))
