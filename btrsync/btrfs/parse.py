#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Parsers for the output of ``btrfs`` subcommands.
"""


def _tabsplit(line): return (x.strip() for x in line.split('\t') if x)
def _valid(v): return None if v == '-' else v


class _BaseParser:
	"""Generic line-oriented parser base class; does not actually parse anything."""
	def __init__(self, lines):
		self.lines = lines

	@classmethod
	def from_stdout(cls, out):
		"""Construct parser from raw command output (UTF-8 encoded bytes)."""
		return cls(out.decode('utf-8').splitlines())


class List(_BaseParser):
	"""Parse the `lines` of output of ``btrfs subvolume list -t ...`` into an iterable of :class:`dict` instances describing subvolumes."""
	def __iter__(self):
		it = iter(self.lines)
		hdrs = list(_tabsplit(next(it)))
		line = next(it)
		if not line.startswith('-'):
			raise ValueError(f"Expected separator on line 2, got `{line}'")
		yield from (dict(zip(hdrs, (_valid(v) for v in _tabsplit(line)))) for line in it)


class Show(_BaseParser):
	"""Parse the `lines` of output of ``btrfs subvolume show ...`` into an iterable containing the filesystem path and a :class:`dict` of properties."""
	def __iter__(self):
		it = iter(self.lines)
		path = next(it)
		yield path

		stats = {}
		ml = None
		for line in it:
			k, *v = _tabsplit(line)
			if not v:
				if ml is None:
					mlk = k
					ml = []
				else:
					ml.append(k)
			else:
				if ml is not None:
					stats[mlk] = ml
					ml = None
				stats[k] = _valid(' '.join(v))
		if ml is not None:
			stats[mlk] = ml
		yield stats
