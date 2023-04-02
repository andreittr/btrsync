#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import unittest

import os
import string
import itertools

from btrsync import util


class TestCmd(unittest.TestCase):
	CMDS = (
		('prg', 'prg', []),
		('prg arg', 'prg', ['arg']),
		('prg a -b c-', 'prg', ['a', '-b', 'c-']),
		('prg     spaced    \t-b c-', 'prg', ['spaced', '-b', 'c-']),
		('prg\\ with\\ space    a\\ _a \t-b c\\ q-\t', 'prg with space', ['a _a', '-b', 'c q-']),
		('prg\\|with\\|pipes    a\\ _\\|a \t-b c\\ \\|\\ q-\t', 'prg|with|pipes', ['a _|a', '-b', 'c | q-']),
		('"prg with quotes" a "-b quot" c\\ q-', 'prg with quotes', ['a', '-b quot', 'c q-']),
	)
	WRAPS = (
		util.Cmd('prg'),
		util.Cmd('prg', ['arg1']),
		util.Cmd('prg', ['arg1', 'arg2', 'arg3']),
	)

	def test_defaults(self):
		PROG = 'myprog'
		c = util.Cmd(PROG)
		self.assertEqual(c.prg, PROG)
		self.assertEqual(list(c.args), [])

	def test_from_cmdstr(self):
		for cmds, exprg, exargs in self.CMDS:
			with self.subTest(cmdstr=cmds):
				c = util.Cmd.from_cmdstr(cmds)
				self.assertEqual(c.prg, exprg)
				self.assertEqual(c.args, exargs)

	def test_seq(self):
		self.assertEqual(list(util.Cmd.seq([])), [])
		for c, (cs, exprg, exargs) in zip(util.Cmd.seq(x[0] for x in self.CMDS), self.CMDS):
			self.assertEqual(c.prg, exprg)
			self.assertEqual(c.args, exargs)

	def test_pipeline(self):
		self.assertEqual(list(util.Cmd.pipeline('')), [])
		cstr = [c[0] for c in self.CMDS]
		for join in ('|', ' |', '| ', ' | '):
			self.assertEqual(list(util.Cmd.pipeline(join.join(cstr))),
			                 list(util.Cmd.seq(cstr)))

	def test_shellify(self):
		for cmds, prg, args in self.CMDS:
			with self.subTest(prg=prg, args=args):
				c = util.Cmd.from_cmdstr(cmds)
				self.assertEqual(util.Cmd.from_cmdstr(c.shellify()), c)

	def test_pipe_arg(self):
		for _, prg, args in  self.CMDS:
			c = util.Cmd(prg, args)
			for w in self.WRAPS:
				p1 = c.pipe_arg([w])
				self.assertEqual(p1.prg, c.prg)
				self.assertEqual(p1.args[:-1], c.args)
				self.assertEqual(p1.args[-1], w.shellify())
				p3 = c.pipe_arg([w]*3)
				self.assertEqual(p3.prg, c.prg)
				self.assertEqual(p3.args[:-1], c.args)
				self.assertEqual(p3.args[-1], ' | '.join([w.shellify()]*3))

	def test_wrap(self):
		for cmds, _, _ in self.CMDS:
			c = util.Cmd.from_cmdstr(cmds)
			for w in self.WRAPS:
				for shell in (False, True):
					for mark in ('', ';', 'word', 'with spaces'):
						cw = c.wrap(w, shellfmt=shell, endmark=mark)
						with self.subTest(c=c, w=w, shell=shell, mark=mark):
							self.assertEqual(cw.prg, w.prg)
							self.assertEqual(cw.args[:len(w.args)], list(w.args))
							if shell:
								self.assertEqual(len(cw.args), len(w.args) + 1 + (1 if mark else 0))
								sc = util.Cmd.from_cmdstr(cw.args[len(w.args)])
								self.assertEqual(sc, c)
							else:
								self.assertEqual(cw.args[len(w.args)], c.prg)
								self.assertEqual(cw.args[len(w.args) + 1: -1 if mark else None], list(c.args))
							if mark:
									self.assertEqual(cw.args[-1], mark)


def _inttree(base=2, maxval=128):
	return lambda x: [x*base + i for i in range(base)] if x < maxval else []


class TestDFS(unittest.TestCase):
	def rec_dfs(self, chf, n):
		yield n
		for c in chf(n):
			yield from self.rec_dfs(chf, c)

	def test_nochild(self):
		self.assertEqual(list(util.dfs(lambda x: [], 'myitem')), ['myitem'])

	def test_manual(self):
		chf = _inttree(2, 8)
		exp = [1, 2, 4, 8, 9, 5, 10, 11, 3, 6, 12, 13, 7, 14, 15]
		auto_exp = list(self.rec_dfs(chf, 1))
		self.assertEqual(exp, auto_exp)
		self.assertEqual(list(util.dfs(chf, 1)), exp)

	def test_complete(self):
		MAXV = 128
		chf = _inttree(2, MAXV)
		res = list(util.dfs(chf, 1))
		self.assertEqual(len(set(res)), len(res))
		self.assertEqual(len(res), 2*MAXV - 1)

	def test_dfs(self):
		for base in range(2,6):
			for mp in range(3, 7):
				maxval = base**mp
				chf = _inttree(base, maxval)
				with self.subTest(base=base, maxval=maxval):
					self.assertEqual(list(util.dfs(chf, 1)), list(self.rec_dfs(chf, 1)))


class TestBFS(unittest.TestCase):
	def test_empty(self):
		self.assertEqual(list(util.bfs(lambda x: errorasdf)), [])

	def test_nochild(self):
		self.assertEqual(list(util.bfs(lambda x: [], 'myitem')), ['myitem'])

	def test_roots(self):
		roots = ['root_' + str(i) for i in range(8)]
		self.assertEqual(list(util.bfs(lambda x: [], *roots)), roots)

	def test_manual(self):
		chf = _inttree(2, 8)
		exp = list(range(1,16))
		self.assertEqual(list(util.bfs(chf, 1)), exp)

	def test_complete(self):
		MAXV = 128
		chf = _inttree(2, MAXV)
		res = list(util.bfs(chf, 1))
		self.assertEqual(len(set(res)), len(res))
		self.assertEqual(len(res), 2*MAXV - 1)

	def test_bfs(self):
		for base in range(2,6):
			for mp in range(3, 7):
				maxval = base**mp
				chf = _inttree(base, maxval)
				with self.subTest(base=base, maxval=maxval):
					self.assertEqual(list(util.bfs(chf, *range(1, base))), list(range(1, base*maxval)))

	def test_maxdepth(self):
		chf = _inttree(2, 1024)
		for depth in range(8):
			with self.subTest(depth=depth):
				self.assertEqual(list(util.bfs(chf, 1, maxdepth=depth)), list(range(1, 2**(depth+1))))

	def test_depthmarkers(self):
		chf = _inttree(2, 1024)
		bfs = util.bfs(chf, 1, depth_markers=True)
		for i in range(11):
			l = list(itertools.islice(bfs, 2**i))
			self.assertNotIn(None, l)
			self.assertIsNone(next(bfs))
		self.assertEqual(len(list(bfs)), 0)


class TestIndex(unittest.TestCase):
	def test_complete(self):
		key = lambda x: x[0]
		l = list(enumerate(string.ascii_lowercase))
		self.assertEqual(util.index([], key), [{}])
		self.assertEqual(util.index(l[:1], key), [{0: (0, 'a')}])
		d = util.index(l, key)[0]
		self.assertEqual(set(d.keys()), set(key(x) for x in l))
		self.assertEqual([d[key(x)] for x in l], l)

	def test_duplicate(self):
		key = lambda x: x[0]
		l = ['abacus', 'bootleg', 'cube', 'carrot']
		self.assertEqual(set(util.index(l[:-1], key)[0].keys()), {'a','b','c'})
		self.assertRaises(ValueError, util.index, l, key)


class TestGroup(unittest.TestCase):
	def test_complete(self):
		BASE = 10
		key = lambda x: x % BASE
		l = list(range(100))
		self.assertEqual(util.group([], key), [{}])
		self.assertEqual(util.group(l[:1], key), [{0: [0]}])
		g = util.group(l, key)[0]
		self.assertEqual(len(g), BASE)
		self.assertEqual(sum(len(g[k]) for k in g), len(l))
		for k in range(BASE):
			exp = [x for x in l if x % BASE == k]
			self.assertEqual(g[k], exp)


class TestPathMerge(unittest.TestCase):
	DIRS = list(string.ascii_lowercase)

	def test_empty(self):
		v = os.path.join(*self.DIRS)
		self.assertEqual(util.path_merge('', ''), '')
		self.assertEqual(util.path_merge(v, ''), os.path.join(v, ''))
		self.assertEqual(util.path_merge('', v), v)

	def test_disjoint(self):
		for i in range(len(self.DIRS)):
			a, b = os.path.join('', *self.DIRS[:i]), os.path.join('', *self.DIRS[i:])
			with self.subTest(a=a, b=b):
				self.assertEqual(util.path_merge(a, b), os.path.join(a,b))

	def test_identical(self):
		for i in range(len(self.DIRS)):
			v = os.path.join('', *self.DIRS[:i])
			with self.subTest(v=v):
				self.assertEqual(util.path_merge(v, v), v)

	def test_overlap(self):
		b = os.path.join(*self.DIRS)
		for i in range(1, len(self.DIRS)):
			a = os.path.join('', *self.DIRS[:i])
			with self.subTest(a=a):
				self.assertEqual(util.path_merge(a, b), b)

	def test_custroot(self):
		a = '//myroot/asd'
		b = os.path.join('myroot/asd', *self.DIRS)
		self.assertNotEqual(util.path_merge(a, b), os.path.join(a, b))
		self.assertEqual(util.path_merge(a, b, root='//myroot'), os.path.join(a, b))


class TestIsSubpath(unittest.TestCase):
	def test_abs(self):
		self.assertFalse(util.is_subpath('/'))
		self.assertFalse(util.is_subpath('/abs/path'))
		self.assertFalse(util.is_subpath('//abs/path'))
		self.assertFalse(util.is_subpath('/abs/../path'))
		self.assertFalse(util.is_subpath('/abs/../../path'))

	def test_rel(self):
		self.assertTrue(util.is_subpath(''))
		self.assertTrue(util.is_subpath('.'))
		self.assertTrue(util.is_subpath('rel/path'))
		self.assertTrue(util.is_subpath('rel/../path'))
		self.assertTrue(util.is_subpath('rel/../path/..'))
		self.assertTrue(util.is_subpath('./rel/../path'))

		self.assertFalse(util.is_subpath('./../rel/path'))
		self.assertFalse(util.is_subpath('../rel/../path'))
		self.assertFalse(util.is_subpath('rel/../../path'))
		self.assertFalse(util.is_subpath('rel/../path/../..'))


if __name__ == '__main__':
	unittest.main()
