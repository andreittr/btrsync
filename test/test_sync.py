#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import unittest
import itertools

from btrsync import util
from btrsync.sync.root import BtrfsError
from btrsync.sync.root.local import LocalBtrfsRoot
from btrsync.sync.root.local import LocalRoot
from btrsync.sync.root.ssh import SSHRoot


class TestBtrfsError(unittest.TestCase):
	def test_args(self):
		e0 = BtrfsError()
		self.assertEqual(str(e0), '')
		e1 = BtrfsError('fail msg')
		self.assertEqual(str(e1), 'BTRFS operation failed:\n\tfail msg')
		e2 = BtrfsError('context', 'message')
		self.assertEqual(str(e2), '"context" failed:\n\tmessage')
		en = BtrfsError('more', 'args', 'than', 'needed', 'before', 'message')
		self.assertEqual(str(en), '"more, args, than, needed, before" failed:\n\tmessage')


class TestLocalBtrfsRoot(unittest.TestCase):
	ARGS = list(itertools.product((True, False), (True, False), ('all', 'strict', 'isolated')))

	def test_args(self):
		p = 'my/path'
		r = LocalBtrfsRoot(p)
		self.assertEqual(r.name, p)
		for ro, cr, scope in self.ARGS:
			r = LocalBtrfsRoot(p, scope=scope, readonly=ro, create_recvpath=cr)
			with self.subTest(case=r):
				self.assertEqual(r.name, p)
				self.assertEqual(r.scope, scope)
				self.assertEqual(r.readonly, ro)
				self.assertEqual(r.create_recvpath, cr)
		self.assertRaises(ValueError, LocalBtrfsRoot, p, scope='bogus')

	def test_repr(self):
		p = 'my/path'
		for ro, cr, scope in self.ARGS:
			r = LocalBtrfsRoot(p, scope=scope, readonly=ro, create_recvpath=cr)
			with self.subTest(case=r):
				rr = eval(repr(r))
				self.assertEqual(rr.name, r.name)
				self.assertEqual(rr.scope, r.scope)
				self.assertEqual(rr.readonly, r.readonly)
				self.assertEqual(rr.create_recvpath, r.create_recvpath)


class TestLocalRoot(unittest.TestCase):
	def test_sudo(self):
		c = util.Cmd('myprog', ['test', 'args'])
		r = LocalRoot(sudo=False)
		wc, *o = r.wrapcmds([c])
		self.assertEqual(o, [])
		self.assertEqual(wc, c)

		r = LocalRoot(sudo=True)
		wc, *o = r.wrapcmds([c])
		self.assertEqual(o, [])
		self.assertEqual(wc.prg, 'sudo')
		self.assertIn(c.prg, wc.args)
		ci = wc.args.index(c.prg)
		self.assertEqual(wc.args[ci+1:ci+3], c.args)


class TestSSHRoot(unittest.TestCase):
	TESTCMD = util.Cmd('myprog', ['test', 'args'])
	PARAMS = list(itertools.product(
		(None, 'testuser'),
		(None, 1337),
		(None, 'my/pks'),
		(False, True),
		(False, True)
	))

	def _wc(self, r):
		wc, *o = r.wrapcmds([self.TESTCMD])
		self.assertEqual(o, [])
		return wc

	def _assertArg(self, args, arg, val):
		self.assertIn(arg, args)
		self.assertEqual(args[args.index(arg)+1], val)

	def _propcheck(self, wc, *, user=None, port=None, pkpath=None, compress=False):
		if compress:
			self.assertIn('-C', wc.args)
		else:
			self.assertNotIn('-C', wc.args)
		if pkpath is None:
			self.assertNotIn('-i', wc.args)
		else:
			self._assertArg(wc.args, '-i', pkpath)
		if port is None:
			self.assertNotIn('-p', wc.args)
		else:
			self._assertArg(wc.args, '-p', str(port))
		if user is None:
			self.assertNotIn('-l', wc.args)
		else:
			self._assertArg(wc.args, '-l', user)

	def _cmdcheck(self, wc, sudo):
		if sudo:
			for arg in wc.args:
				if arg.startswith('sudo'):
					self.assertTrue(arg.endswith(self.TESTCMD.shellify()))
					break
			else:
				self.fail('sudo command not found in wrap')
		else:
			for arg in wc.args:
				self.assertFalse(arg.startswith('sudo'))
			self.assertIn(self.TESTCMD.shellify(), wc.args)

	def test_ssh(self, wc=None):
		if wc is None:
			wc = self._wc(SSHRoot('testhost'))
		self.assertEqual(wc.prg, 'ssh')
		self.assertIn('testhost', wc.args)

	def test_params(self):
		h = 'testhost'
		for u, p, pk, c, s in self.PARAMS:
			r = SSHRoot(h, user=u, port=p, pkpath=pk, compress=c, sudo=s)
			with self.subTest(case=r):
				wc = self._wc(r)
				self.test_ssh(wc)
				self._propcheck(wc, user=u, port=p, pkpath=pk, compress=c)
				self._cmdcheck(wc, s)

	def test_pipe(self):
		r = SSHRoot('testhost')
		wc, *o = r.wrapcmds([self.TESTCMD]*3)
		self.assertEqual(o, [])
		self.assertIn('|', wc.args[-1])
		self.assertIn('myprog', wc.args[-1])
		for arg in wc.args[:-1]:
			self.assertNotIn('|', arg)
			self.assertNotIn('myprog', arg)

	def test_name(self):
		h = 'testhost'
		u = 'testuser'
		p = 'my/path'
		r = SSHRoot(h)(p)
		self.assertEqual(r.name, f'{h}:{p}')
		r = SSHRoot(h, user=u)(p)
		self.assertEqual(r.name, f'{u}@{h}:{p}')

	def test_repr(self):
		h = 'testhost'
		rp = 'rootpath'
		for u, p, pk, c, s in self.PARAMS:
			r = SSHRoot(h, user=u, port=p, pkpath=pk, compress=c, sudo=s)(rp)
			rr = eval(repr(r))
			with self.subTest(case=r, clone=rr):
				self.assertEqual(rr.name, r.name)
				wc = self._wc(rr)
				self.test_ssh(wc)
				self._propcheck(wc, user=u, port=p, pkpath=pk, compress=c)
				self._cmdcheck(wc, s)


if __name__ == '__main__':
	unittest.main()
