#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import re
import string
import itertools
import unittest

from btrsync.btrfs import cmd


def _hasflag(f, args):
	r = re.compile(f'-[^-]*{f}.*')
	return any(r.match(a) is not None for a in args)

class TestList(unittest.TestCase):
	def _sanity(self, c, path):
		self.assertEqual(c.prg, 'btrfs')
		self.assertEqual(c.args[0], 'subvolume')
		self.assertEqual(c.args[1], 'list')
		self.assertEqual(c.args[-1], path)
		self.assertTrue(_hasflag('t', c.args))
		self.assertTrue(_hasflag('a', c.args) ^ _hasflag('o', c.args))

	def test_def(self):
		c = cmd.list('test')
		self._sanity(c, 'test')

	def test_flags(self):
		FIELDS = 'pcguqR'
		for i in range(len(FIELDS) + 1):
			for case in itertools.combinations(FIELDS, i):
				case = ''.join(case)
				with self.subTest(case=case):
					c = cmd.list('test', list_all=False, readonly=False, fields=case)
					self._sanity(c, 'test')
					self.assertFalse(_hasflag('r', c.args))
					self.assertTrue(_hasflag('o', c.args))
					for f in FIELDS:
						self.assertEqual(_hasflag(f, c.args), f in case)
					c = cmd.list('test', list_all=False, readonly=True, fields=case)
					self._sanity(c, 'test')
					self.assertTrue(_hasflag('r', c.args))
					self.assertTrue(_hasflag('o', c.args))
					for f in FIELDS:
						self.assertEqual(_hasflag(f, c.args), f in case)
					c = cmd.list('test', list_all=True, readonly=False, fields=case)
					self._sanity(c, 'test')
					self.assertFalse(_hasflag('r', c.args))
					self.assertTrue(_hasflag('a', c.args))
					for f in FIELDS:
						self.assertEqual(_hasflag(f, c.args), f in case)
					c = cmd.list('test', list_all=True, readonly=True, fields=case)
					self._sanity(c, 'test')
					self.assertTrue(_hasflag('r', c.args))
					self.assertTrue(_hasflag('a', c.args))
					for f in FIELDS:
						self.assertEqual(_hasflag(f, c.args), f in case)
		valid_fields = FIELDS + 'aro'
		for f in string.ascii_letters:
			if f not in valid_fields:
				self.assertRaises(ValueError, cmd.list, 'test', fields=f)


class TestSend(unittest.TestCase):
	PATHS = ('test', 'test/path', '/abcde')

	def _sanity(self, c, paths):
		self.assertEqual(c.prg, 'btrfs')
		self.assertEqual(c.args[0], 'send')
		self.assertEqual(c.args[-len(paths):], list(paths))

	def _check_clones(self, c, clones):
		a = c.args[:]
		for cl in clones:
			self.assertIn('-c', a)
			ci = a.index('-c')
			self.assertEqual(a[ci+1], cl)
			a = a[ci+2:]

	def test_def(self):
		self.assertRaises(ValueError, cmd.send)
		c = cmd.send('test')
		self._sanity(c, ['test'])

	def test_deep(self):
		COMPRESS_FLAG = '--compressed-data'
		for i in range(1, len(self.PATHS) + 1):
			for case in itertools.combinations(self.PATHS, i):
				with self.subTest(case=case):
					c = cmd.send(*case, parent=None, clones=None, keep_compressed=False)
					self._sanity(c, case)
					self.assertFalse(_hasflag('p', c.args))
					self.assertFalse(_hasflag('c', c.args))
					self.assertNotIn(COMPRESS_FLAG, c.args)

					c = cmd.send(*case, parent=None, clones=None, keep_compressed=True)
					self._sanity(c, case)
					self.assertFalse(_hasflag('p', c.args))
					self.assertFalse(_hasflag('c', c.args))
					self.assertIn(COMPRESS_FLAG, c.args)

					c = cmd.send(*case, parent=None, clones=['a', 'b'], keep_compressed=False)
					self._sanity(c, case)
					self.assertFalse(_hasflag('p', c.args))
					self._check_clones(c, ['a', 'b'])
					self.assertNotIn(COMPRESS_FLAG, c.args)

					c = cmd.send(*case, parent=None, clones=['a', 'b'], keep_compressed=True)
					self._sanity(c, case)
					self.assertFalse(_hasflag('p', c.args))
					self._check_clones(c, ['a', 'b'])
					self.assertIn(COMPRESS_FLAG, c.args)

					c = cmd.send(*case, parent='testpar', clones=None, keep_compressed=False)
					self._sanity(c, case)
					self.assertIn('-p', c.args)
					pi = c.args.index('-p')
					self.assertEqual(c.args[pi+1], 'testpar')
					self.assertFalse(_hasflag('c', c.args))
					self.assertNotIn(COMPRESS_FLAG, c.args)

					c = cmd.send(*case, parent='testpar', clones=None, keep_compressed=True)
					self._sanity(c, case)
					self.assertIn('-p', c.args)
					pi = c.args.index('-p')
					self.assertEqual(c.args[pi+1], 'testpar')
					self.assertFalse(_hasflag('c', c.args))
					self.assertIn(COMPRESS_FLAG, c.args)

					c = cmd.send(*case, parent='testpar', clones=['a', 'b'], keep_compressed=False)
					self._sanity(c, case)
					self.assertIn('-p', c.args)
					pi = c.args.index('-p')
					self.assertEqual(c.args[pi+1], 'testpar')
					self._check_clones(c, ['a', 'b'])
					self.assertNotIn(COMPRESS_FLAG, c.args)

					c = cmd.send(*case, parent='testpar', clones=['a', 'b'], keep_compressed=True)
					self._sanity(c, case)
					self.assertIn('-p', c.args)
					pi = c.args.index('-p')
					self.assertEqual(c.args[pi+1], 'testpar')
					self._check_clones(c, ['a', 'b'])
					self.assertIn(COMPRESS_FLAG, c.args)



class TestReceive(unittest.TestCase):
	def test_def(self):
		c = cmd.receive('testpath')
		self.assertEqual(c.prg, 'btrfs')
		self.assertEqual(c.args[0], 'receive')
		self.assertEqual(c.args[-1], 'testpath')

	def test_decompress(self):
		c = cmd.receive('testpath', force_decompress=True)
		self.assertEqual(c.prg, 'btrfs')
		self.assertEqual(c.args[0], 'receive')
		self.assertEqual(c.args[1], '--force-decompress')
		self.assertEqual(c.args[-1], 'testpath')


class TestShow(unittest.TestCase):
	def test_def(self):
		c = cmd.show('testpath')
		self.assertEqual(c.prg, 'btrfs')
		self.assertEqual(c.args[0], 'subvolume')
		self.assertEqual(c.args[1], 'show')
		self.assertEqual(c.args[-1], 'testpath')

	def test_ids(self):
		self.assertRaises(ValueError, cmd.show, 'test', uuid='', rootid='')
		c = cmd.show('test', uuid='myuuid')
		self.assertIn('-u', c.args)
		self.assertEqual(c.args[c.args.index('-u') + 1], 'myuuid')
		c = cmd.show('test', rootid='123')
		self.assertIn('-r', c.args)
		self.assertEqual(c.args[c.args.index('-r') + 1], '123')


if __name__ == '__main__':
	unittest.main()
