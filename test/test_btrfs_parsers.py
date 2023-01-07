#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import unittest

from btrsync.btrfs import parse


class TestBaseParser(unittest.TestCase):
	def test_fromstdout(self):
		exp = ['a', 'b', '', 'prev line is empty', 'éäß©æëþüïñµíöóœøçșîțăâ']
		p = parse._BaseParser.from_stdout('\n'.join(exp).encode('utf-8'))
		self.assertEqual(p.lines, exp)


class TestListParse(unittest.TestCase):
	def test_empty(self):
		exp = ['irrelevant\tfirst\tline', '--']
		self.assertEqual(list(parse.List(exp)), [])

	def test_example(self):
		eout = b'''ID	gen	top level	path
--	---	---------	----
273	1696990	469		path1
305	1696990	469		path2
333	1687353	649		longer/path3
'''
		exp = [
			{'ID': '273', 'gen': '1696990', 'top level': '469', 'path': 'path1'},
			{'ID': '305', 'gen': '1696990', 'top level': '469', 'path': 'path2'},
			{'ID': '333', 'gen': '1687353', 'top level': '649', 'path': 'longer/path3'},
		]
		self.assertEqual(list(parse.List.from_stdout(eout)), exp)

	def test_bad(self):
		exp = ['first\tline', 'bad 2nd line', 'irrelevant 3rd line']
		self.assertRaises(ValueError, next, iter(parse.List(exp)))


class TestShowParse(unittest.TestCase):
	EXP = '''test_volume/path
		         key_1:	Value_1
		         key_2:	Value_2
		         key_3:	Value_3
		         multiline:
						bigval1
						bigval2
						bigval3
						bigval4
		         key_4:	Value_4
		         multi_2:
		         somvala
		         somvalx
'''.splitlines()

	def test_empty(self):
		p = parse.Show(self.EXP[:1])
		self.assertEqual(list(p), ['test_volume/path', {}])

	def test_example(self):
		p = list(parse.Show(self.EXP))
		self.assertEqual(p[0], 'test_volume/path')
		for k, v in p[1].items():
			if k.startswith('key_'):
				self.assertEqual(len(k), 6)
				self.assertEqual(k[-1], ':')
				self.assertEqual(v, f'Value_{k[-2]}')
			elif k == 'multiline:':
				self.assertEqual(len(v), 4)
				for i in range(4):
					self.assertEqual(v[i], f'bigval{i+1}')
			elif k == 'multi_2:':
				self.assertEqual(v, ['somvala', 'somvalx'])
			else:
				self.fail(f'Unexpected key value pair ({k}:{v})')



if __name__ == '__main__':
	unittest.main()
