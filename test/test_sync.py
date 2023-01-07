#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import unittest


from btrsync import util
from btrsync.sync.root.local import LocalRoot
from btrsync.sync.root.ssh import SSHRoot


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

	def _wc(self, *args, **kwargs):
		r = SSHRoot(*args, **kwargs)
		wc, *o = r.wrapcmds([self.TESTCMD])
		self.assertEqual(o, [])
		return wc

	def test_ssh(self):
		wc = self._wc('testhost')
		self.assertEqual(wc.prg, 'ssh')
		self.assertIn('testhost', wc.args)
		self.assertIn(self.TESTCMD.shellify(), wc.args)

	def test_params(self):
		wc = self._wc('testhost', compress=False)
		self.assertNotIn('-C', wc.args)
		wc = self._wc('testhost', compress=True)
		self.assertIn('-C', wc.args)

		wc = self._wc('testhost', pkpath=None)
		self.assertNotIn('-i', wc.args)
		wc = self._wc('testhost', pkpath='my/pks')
		self.assertIn('-i', wc.args)
		self.assertEqual(wc.args[wc.args.index('-i')+1], 'my/pks')

		wc = self._wc('testhost', port=None)
		self.assertNotIn('-p', wc.args)
		wc = self._wc('testhost', port='1337')
		self.assertIn('-p', wc.args)
		self.assertEqual(wc.args[wc.args.index('-p')+1], '1337')

		wc = self._wc('testhost', user=None)
		self.assertNotIn('-l', wc.args)
		wc = self._wc('testhost', user='testuser')
		self.assertIn('-l', wc.args)
		self.assertEqual(wc.args[wc.args.index('-l')+1], 'testuser')

	def test_sudo(self):
		wc = self._wc('testhost', sudo=False)
		for arg in wc.args:
			self.assertFalse(arg.startswith('sudo'))
		self.assertIn(self.TESTCMD.shellify(), wc.args)

		wc = self._wc('testhost', sudo=True)
		for arg in wc.args:
			if arg.startswith('sudo'):
				self.assertTrue(arg.endswith(self.TESTCMD.shellify()))
				break
		else:
			self.fail('sudo command not found in wrap')


if __name__ == '__main__':
	unittest.main()
