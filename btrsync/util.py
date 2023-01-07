#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Various general purpose utility classes and functions.
"""

import os
import shlex

from collections import deque
from collections import namedtuple
from collections import defaultdict


class FileDesc:
	"""
	Wrapper class for a file descriptor that closes it exactly once, either manually or upon object destruction.

	:param fd: file descriptor
	"""
	def __init__(self, fd):
		self.fd = fd
		self.closed = False

	def close(self):
		"""Ensure `fd` is closed; operation is idempotent and will call :func:`os.close` exactly once."""
		if not self.closed:
			os.close(self.fd)
			self.closed = True

	def __del__(self):
		self.close()


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

	def shellify(self):
		"""Return a properly shell-escaped command string form of `self`."""
		tok = [shlex.quote(self.prg)]
		tok.extend(shlex.quote(x) for x in self.args)
		return ' '.join(tok)

	def wrap(self, outer, *, shellfmt=False, endmark=None):
		"""
		Return a new :class:`.Cmd` instance that passes `self` as arguments to `outer`.

		:param outer: the outer command that receives `self` as arguments
		:param shellfmt: if :const:`True`, pass a shell-escaped form of `self` as a single last argument to `outer`;
		                 if :const:`False`, :attr:`.prg` along with :attr:`.args` are passed as individual arguments to `outer`
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
