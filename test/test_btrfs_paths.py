#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import unittest

from btrsync import btrfs


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
