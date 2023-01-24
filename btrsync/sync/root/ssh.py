#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Btrfs roots for remote access via SSH.
"""

from . import local

from ... import util


def SSHRoot(host, *, user=None, port=None, pkpath=None, compress=False, sudo=False):
	"""
	Return an appropriate btrfs root class for accessing btrfs filesystems on remote machines using ssh.

	:param host: the remote host to ssh into
	:param user: the user to log in as
	:param port: the port to connect to on `host`
	:param pkpath: the local path to the private key (identity) file to use
	:param compress: if :const:`True`, enable compression on the ssh channel
	:param sudo: if :const:`True`, use ``sudo`` to execute ``btrfs`` commands on the remote machine
	"""
	_rargs = {'host': host, 'user': user, 'port': port, 'pkpath': pkpath, 'compress': compress, 'sudo': sudo}
	args = []
	if compress:
		args.append('-C')
	if user is not None:
		args.extend(('-l', user))
	if port is not None:
		args.extend(('-p', str(port)))
	if pkpath is not None:
		args.extend(('-i', pkpath))
	args.append(host)
	SSH = util.Cmd('ssh', args)

	class SSHBtrfsRoot(local.LocalBtrfsRoot):
		"""SSH btrfs root implemented using a local ``ssh`` binary."""
		if sudo:
			@staticmethod
			def wrapcmds(cmds):
				yield SSH.pipe_arg(c.wrap(local.SUDO) for c in cmds)
		else:
			@staticmethod
			def wrapcmds(cmds):
				yield SSH.pipe_arg(cmds)

		def __repr__(self):
			ssh_args = ', '.join(f'{arg}={val!r}' for arg, val in _rargs.items())
			return f'SSHRoot({ssh_args})({self._reprargs()})'

		@property
		def name(self):
			return (f'{user}@' if user is not None else '') + f'{host}:{self.rootpath}'

	return SSHBtrfsRoot
