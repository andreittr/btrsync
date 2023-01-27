#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from . import BtrfsRoot, BtrfsError

from ... import cmdex


class ExecBtrfsRoot(BtrfsRoot):
	""":class:`BtrfsRoot` base class that executes subcommands."""
	@staticmethod
	def wrapcmds(cmds):
		"""Return `cmds` unchanged; override to customize executed commands."""
		yield from cmds

	@classmethod
	async def _run(cls, *cmds, **kwargs):
		return (await cmdex.ex_out(*cls.wrapcmds(cmds), **kwargs))[-1]

	@classmethod
	async def _run_checked(cls, *cmds, **kwargs):
		ret, (stdout, stderr) = await cls._run(*cmds, **kwargs)
		if ret != 0:
			msg = ' | '.join(c.shellify() for c in cmds)
			raise BtrfsError(msg, stderr.decode('utf-8').rstrip())
		return ret, (stdout, stderr)
