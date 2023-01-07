#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import itertools

from btrsync import cli


class TestBaseMatch(unittest.TestCase):
	ABS = ('/', '/*', '/path', '/path/', '/path/*')
	ALL = ('', '*')
	PA = ('pa*',)
	PATH = ('path', 'p?th', 'p[!b]th', 'p[abc]?h')
	EX_ALL = ('p', 'p/', 'ptt/a/b/c')
	EX_PA = ('pa', 'pat', 'pas', 'pabs')
	EX_PATH = ('path/', 'path/a', 'path/a/b/c')
	def test_excl(self):
		u = cli.BaseMatch()
		u.exclude('*')
		for ex in itertools.chain(self.EX_PATH, self.EX_PA, self.EX_ALL):
			with self.subTest(case='*', ex=ex):
				self.assertFalse(u.match(ex))
		for case in self.PA:
			u = cli.UnderGlob('*')
			u.exclude(case)
			for ex in itertools.chain(self.EX_PATH, self.EX_PA):
				with self.subTest(case=case, ex=ex):
					self.assertFalse(u.match(ex))
			for ex in self.EX_ALL:
				with self.subTest(case=case, ex=ex):
					self.assertTrue(u.match(ex))
		for case in self.PATH:
			case = case + '*'
			u = cli.UnderGlob('*')
			u.exclude(case)
			for ex in self.EX_PATH:
				with self.subTest(case=case, ex=ex):
					self.assertFalse(u.match(ex))
			for ex in itertools.chain(self.EX_PA, self.EX_ALL):
				with self.subTest(case=case, ex=ex):
					self.assertTrue(u.match(ex))

	def test_incl(self):
		u = cli.BaseMatch()
		u.include('test*')
		self.assertFalse(u.match('path'))
		self.assertFalse(u.match('path/'))
		self.assertFalse(u.match('path/abc'))
		self.assertFalse(u.match('path/abcte/st'))
		self.assertTrue(u.match('test'))
		self.assertTrue(u.match('testing'))
		self.assertTrue(u.match('test/'))
		self.assertTrue(u.match('test/abc'))
		self.assertFalse(u.match('path/test'))
		self.assertFalse(u.match('path/testing'))
		self.assertFalse(u.match('path/test/'))
		self.assertFalse(u.match('path/test/abc'))

	def test_incl_excl(self):
		u = cli.BaseMatch()
		u.include('test*')
		u.exclude('*[ax][bx][cx]*', '*ing*')
		self.assertFalse(u.match('path'))
		self.assertTrue(u.match('test'))
		self.assertTrue(u.match('test/'))
		self.assertFalse(u.match('testing'))
		self.assertFalse(u.match('test/ing'))
		self.assertFalse(u.match('testing/abc'))
		self.assertFalse(u.match('test/abc'))

	def test_stop(self):
		self.assertFalse(cli.UnderGlob('').stop(object()))


class TestSingleMatch(unittest.TestCase):
	def test_match(self):
		p = 'my/path'
		m = cli.SingleMatch(p)
		self.assertTrue(m.match(p))
		self.assertFalse(m.match(''))
		self.assertFalse(m.match('bad'))
		self.assertFalse(m.match('ma/path'))

	def test_stop(self):
		p = 'my/path'
		self.assertTrue(cli.SingleMatch(p).stop([p]))


class TestUnderGlob(unittest.TestCase):
	ABS = ('/', '/*', '/path', '/path/', '/path/*')
	ALL = ('', '*')
	PA = ('pa*',)
	PATH = ('path', 'p?th', 'p[!b]th', 'p[abc]?h')
	EX_ALL = ('p', 'p/', 'ptt/a/b/c')
	EX_PA = ('pa', 'pat', 'pas', 'pabs')
	EX_PATH = ('path/', 'path/a', 'path/a/b/c')
	def test_glob(self):
		for case in self.ABS:
			with self.subTest(case=case):
				self.assertRaises(ValueError, cli.UnderGlob, case)
		for case in self.ALL:
			u = cli.UnderGlob(case)
			for ex in itertools.chain(self.EX_PATH, self.EX_PA, self.EX_ALL):
				with self.subTest(case=case, ex=ex):
					self.assertTrue(u.match(ex))
		for case in self.PA:
			u = cli.UnderGlob(case)
			for ex in itertools.chain(self.EX_PATH, self.EX_PA):
				with self.subTest(case=case, ex=ex):
					self.assertTrue(u.match(ex))
			for ex in self.EX_ALL:
				with self.subTest(case=case, ex=ex):
					self.assertFalse(u.match(ex))
		for basecase in self.PATH:
			for sufx in ('', '/', '/*'):
				case = basecase + sufx
				u = cli.UnderGlob(case)
				for ex in self.EX_PATH:
					with self.subTest(case=case, ex=ex):
						self.assertTrue(u.match(ex))
				for ex in itertools.chain(self.EX_PA, self.EX_ALL):
					with self.subTest(case=case, ex=ex):
						self.assertFalse(u.match(ex))

	def test_incl(self):
		u = cli.UnderGlob('path')
		u.include('test*')
		self.assertFalse(u.match('path'))
		self.assertFalse(u.match('path/'))
		self.assertFalse(u.match('path/abc'))
		self.assertFalse(u.match('path/abcte/st'))
		self.assertFalse(u.match('test'))
		self.assertFalse(u.match('test/'))
		self.assertTrue(u.match('path/test'))
		self.assertTrue(u.match('path/testing'))
		self.assertTrue(u.match('path/test/'))
		self.assertTrue(u.match('path/test/abc'))

	def test_incl_excl(self):
		u = cli.UnderGlob('path')
		u.include('test*')
		u.exclude('*[ax][bx][cx]*', '*ing*')
		self.assertFalse(u.match('path'))
		self.assertFalse(u.match('path/'))
		self.assertFalse(u.match('path/abc'))
		self.assertFalse(u.match('path/abcte/st'))
		self.assertFalse(u.match('test'))
		self.assertFalse(u.match('test/'))
		self.assertTrue(u.match('path/test'))
		self.assertFalse(u.match('path/testing'))
		self.assertTrue(u.match('path/test/'))
		self.assertFalse(u.match('path/test/abc'))

	def test_stop(self):
		self.assertFalse(cli.UnderGlob('').stop(object()))


class TestSSHLoc(unittest.TestCase):
	SSHCASES = (
		('', cli.SSHLoc(host='', user=None, port=None)),
		('@', cli.SSHLoc(host='', user='', port=None)),
		('a', cli.SSHLoc(host='a', user=None, port=None)),
		('@a', cli.SSHLoc(host='a', user='', port=None)),
		('usr@a', cli.SSHLoc(host='a', user='usr', port=None)),
		('a:port', cli.SSHLoc(host='a:port', user=None, port=None)),
		('usr@a@port', cli.SSHLoc(host='a@port', user='usr', port=None)),
		('@usr@a@port13', cli.SSHLoc(host='usr@a@port13', user='', port=None)),
		('[f::1]', cli.SSHLoc(host='[f::1]', user=None, port=None)),
		('@[f::1]', cli.SSHLoc(host='[f::1]', user='', port=None)),
		('usr@[f::1]', cli.SSHLoc(host='[f::1]', user='usr', port=None)),
	)
	URLCASES = (
		('', cli.SSHLoc(host='', user=None, port=None)),
		('@', cli.SSHLoc(host='', user='', port=None)),
		(':', cli.SSHLoc(host='', user=None, port='')),
		('@:', cli.SSHLoc(host='', user='', port='')),
		('a', cli.SSHLoc(host='a', user=None, port=None)),
		('@a', cli.SSHLoc(host='a', user='', port=None)),
		('a:', cli.SSHLoc(host='a', user=None, port='')),
		('@a:', cli.SSHLoc(host='a', user='', port='')),
		('usr@a', cli.SSHLoc(host='a', user='usr', port=None)),
		('a:port', cli.SSHLoc(host='a', user=None, port='port')),
		('usr@a:port', cli.SSHLoc(host='a', user='usr', port='port')),
		('usr@a:@port:', cli.SSHLoc(host='a', user='usr', port='@port:')),
		('@usr@a:@port:13', cli.SSHLoc(host='usr@a', user='', port='@port:13')),
		('[f::1]', cli.SSHLoc(host='[f::1]', user=None, port=None)),
		('@[f::1]', cli.SSHLoc(host='[f::1]', user='', port=None)),
		('[f::1]:', cli.SSHLoc(host='[f::1]', user=None, port='')),
		('@[f::1]:', cli.SSHLoc(host='[f::1]', user='', port='')),
		('usr@[f::1]', cli.SSHLoc(host='[f::1]', user='usr', port=None)),
		('[f::1]:port', cli.SSHLoc(host='[f::1]', user=None, port='port')),
		('usr@[f::1]:port', cli.SSHLoc(host='[f::1]', user='usr', port='port')),
		('usr@[f::1]:@port:', cli.SSHLoc(host='[f::1]', user='usr', port='@port:')),
		('@[f::1]:@port:13', cli.SSHLoc(host='[f::1]', user='', port='@port:13')),
	)

	def test_parse_ssh(self):
		for inp, exp in self.SSHCASES:
			with self.subTest(inp=inp):
				self.assertEqual(cli.SSHLoc.parse_ssh(inp), exp)

	def test_parse_url(self):
		for inp, exp in self.URLCASES:
			with self.subTest(inp=inp):
				self.assertEqual(cli.SSHLoc.parse_url(inp), exp)

	def test_validate(self):
		for _, loc in itertools.chain(self.SSHCASES, self.URLCASES):
			with self.subTest(loc=loc):
				v = loc.host and (loc.user is None or loc.user) and (loc.port is None or loc.port)
				if v:
					self.assertIs(loc.validate(), loc)
				else:
					self.assertRaises(ValueError, loc.validate)

	def test_asdict(self):
		for _, loc in itertools.chain(self.SSHCASES, self.URLCASES):
			with self.subTest(loc=loc):
				exp = {'host': loc.host, 'user': loc.user, 'port': loc.port}
				self.assertEqual(loc.asdict(), exp)


class TestParseRoot(unittest.TestCase):
	PATHS = ('', 'a', 'a/b/c', '/', '/abs/path', './with:colons/in:name',
		     '//double/root', '../rel/path/../s', '/almost://url')

	def test_path(self):
		for loc in self.PATHS:
			with self.subTest(loc=loc):
				r, *a = cli.parse_root(loc)
				self.assertEqual(r, 'local')
				self.assertEqual(a, [{}, loc])

	def test_sshloc(self):
		PRES = ('h', 'u@h', '[f::1]', 'u@[f::1]')
		CASES = itertools.chain(*((pre + v for v in self.PATHS) for pre in PRES))
		for pre in PRES:
			for path in self.PATHS:
				loc = ':'.join((pre, path))
				with self.subTest(loc=loc):
					if path.startswith('//') and pre == 'h':
						# Double-root can be confused for url if host matches schema characters; intended behavior
						r, *a = cli.parse_root(loc)
						self.assertEqual(r, pre)
					else:
						r, *a = cli.parse_root(loc)
						self.assertEqual(r, 'ssh')
						self.assertEqual(a[0], cli.SSHLoc.parse_ssh(pre).asdict())
						self.assertEqual(a[1], path)

	def test_url(self):
		for path in self.PATHS:
			loc = 'file://' + path
			with self.subTest(loc=loc):
				r, *a = cli.parse_root(loc)
				self.assertEqual(r, 'local')
				self.assertEqual(a, [{}, path])
			if path.startswith('/'):
				# Absolute paths only for URL-based SSH & btrsync
				sloc = 'ssh://usr@host:23' + path
				with self.subTest(loc=sloc):
					r, *a = cli.parse_root(sloc)
					self.assertEqual(r, 'ssh')
					self.assertEqual(a[0], cli.SSHLoc(user='usr', host='host', port='23').asdict())
					self.assertEqual(a[1], path)
				bloc = 'btrsync://host:8080' + path
				with self.subTest(loc=bloc):
					r, *a = cli.parse_root(bloc)
					self.assertEqual(r, 'btrsync')
				# IPv6-style netlocs
				sloc = 'ssh://usr@[f::1]:23' + path
				with self.subTest(loc=sloc):
					r, *a = cli.parse_root(sloc)
					self.assertEqual(r, 'ssh')
					self.assertEqual(a[0], cli.SSHLoc(user='usr', host='[f::1]', port='23').asdict())
					self.assertEqual(a[1], path)
				bloc = 'btrsync://[f::1]:8080' + path
				with self.subTest(loc=bloc):
					r, *a = cli.parse_root(bloc)
					self.assertEqual(r, 'btrsync')


class TestHumanBytes(unittest.TestCase):
	DEFSEP = ' '
	THRESH = 1024
	UNITS = ('  B', 'KiB', 'MiB', 'GiB', 'TiB', 'EiB')
	USCALE = [(unit, 2**(10*i)) for i, unit in enumerate(UNITS)]

	@staticmethod
	def numfmt(n):
		return f'{n:6.1f}'

	@staticmethod
	def sjoin(*args, sep=DEFSEP):
		return sep.join(args)

	def test_zero(self):
		self.assertEqual(cli.humanbytes(0), self.sjoin(self.numfmt(0), '  B'))

	def test_thresh(self):
		for i, (unit, scale) in enumerate(self.USCALE[:-1]):
			n = scale * self.THRESH
			with self.subTest(n=n):
				exp_n = n / self.USCALE[i+1][1]
				exp_u = self.USCALE[i+1][0]
				self.assertEqual(cli.humanbytes(n),
				                 self.sjoin(self.numfmt(exp_n), exp_u))

	def test_ovrunit(self):
		unit, scale = self.USCALE[-1]
		for mul in range(1, 5):
			n = scale * self.THRESH * mul
			with self.subTest(n=n):
				self.assertEqual(cli.humanbytes(n),
				                 self.sjoin(self.numfmt(n/scale), unit))

	def test_log(self):
		for unit, scale in self.USCALE:
			for p in range(1, 100):
				if 2**p - 1 >= self.THRESH:
					break
				n = scale * (2**p - 1)
				with self.subTest(n=n):
					self.assertEqual(cli.humanbytes(n),
					                 self.sjoin(self.numfmt(2**p - 1), unit))


if __name__ == '__main__':
	unittest.main()
