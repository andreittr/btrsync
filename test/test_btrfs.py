#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import unittest

from btrsync import btrfs


class TestVol(unittest.TestCase):
	VKEYS = {btrfs.Vol._P, btrfs.Vol._S}

	def test_def(self):
		v = btrfs.Vol()
		for k in v:
			if k not in self.VKEYS:
				self.fail(f'Unexpected key {k}')
		self.assertIsNone(v.parent)
		self.assertEqual(v.succs, [])
		v.parent = 42
		v.succs.extend((1, 2, 3))
		self.assertEqual(v.parent, 42)
		self.assertEqual(v.succs, [1, 2, 3])

	def test_example(self):
		d = {'path': 'my/path', 'uuid': 1337}
		v = btrfs.Vol(d, parent=42, succs=[4, 5, 6])
		for k in d:
			self.assertEqual(v[k], d[k])
		for k in v:
			if k not in self.VKEYS:
				if k in d:
					self.assertEqual(v[k], d[k])
				else:
					self.fail(f'Unexpected key {k}')
		self.assertEqual(v.parent, 42)
		self.assertEqual(v.succs, [4, 5, 6])


class TestAbsPaths(unittest.TestCase):
	def test_bad(self):
		it = btrfs.abspaths([], 'bad/relative/rootpath')
		self.assertRaises(ValueError, next, it)
		it = btrfs.abspaths([], '/bad/path/nofstree')
		self.assertRaises(ValueError, next, it)

	def test_example(self):
		inp = ['testvol/dirpath', '<FS_TREE>/testvol/abs/sub', '<FS_TREE>/abs']
		exp = ['<FS_TREE>/testvol/dirpath', '<FS_TREE>/testvol/abs/sub', '<FS_TREE>/abs']
		invols = ({'path': p} for p in inp)
		exvols = ({'path': p} for p in exp)
		for t, e in zip(btrfs.abspaths(invols, '<FS_TREE>/testvol'), exvols):
			self.assertEqual(t, e)


class TestRelPaths(unittest.TestCase):
	def test_bad(self):
		it = btrfs.relpaths([], 'bad/relative/rootpath')
		self.assertRaises(ValueError, next, it)
		it = btrfs.relpaths([], '/bad/path/nofstree')
		self.assertRaises(ValueError, next, it)

	def test_example(self):
		inp = ['testvol/dirpath', '<FS_TREE>/testvol/abs/sub', '<FS_TREE>/abs']
		exp = ['dirpath', 'abs/sub', '<FS_TREE>/abs']
		invols = ({'path': p} for p in inp)
		exvols = ({'path': p} for p in exp)
		for t, e in zip(btrfs.relpaths(invols, '<FS_TREE>/testvol'), exvols):
			self.assertEqual(t, e)


if __name__ == '__main__':
	unittest.main()
