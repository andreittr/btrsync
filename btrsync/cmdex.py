#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""
Asynchronous execution of subprocess pipelines.
"""

import os
import asyncio
import threading

from . import util


DEVNULL = asyncio.subprocess.DEVNULL
PIPE = asyncio.subprocess.PIPE


def _killall(procs, forced=False):
	for p in procs:
		if p.returncode is None:
			if forced:
				p.kill()
			else:
				p.terminate()

def _waitall(procs):
	return asyncio.gather(*(p.wait() for p in procs))


async def create_pipeline(*cmds, stdin=None, stdout=None, stderr=None):
	"""
	Asynchronous iterator returning started subprocesses connected together as a pipeline.

	:param cmds: sequence of :class:`btrsync.util.Cmd`-like commands that form the pipeline
	:param stdin: standard input of the first command in the pipeline; :const:`None` means inherit from caller.
		if supplied and not zero, it is guaranteed to be closed on either success or error.
	:param stdout: standard output of the last command in the pipeline; :const:`None` means inherit from caller
	:param stderr: standard error of all commands in the pipeline; :const:`None` means inherit from caller
	:returns: :class:`asyncio.subprocess.Process` instances of started processes
	"""
	def _chkclose(fd):
		if fd is not None and fd >= 0:
			os.close(fd)

	end = stdin
	for prg, args in cmds[:-1]:
		try:
			nextend, head = os.pipe()
		except:
			_chkclose(end)
			raise
		try:
			proc = await asyncio.create_subprocess_exec(prg, *args, stdin=end, stdout=head, stderr=stderr)
		except:
			os.close(nextend)
			raise
		finally:
			_chkclose(end)
			os.close(head)
		yield proc
		end = nextend
	for prg, args in cmds[-1:]:
		try:
			proc = await asyncio.create_subprocess_exec(prg, *args, stdin=end, stdout=stdout, stderr=stderr)
		finally:
			_chkclose(end)
		yield proc


async def wait_procs(procs, *, timeout=None, abort=False):
	"""
	Wait on multiple processes, optionally timing out or aborting on failure.

	:param procs: sequence of processes to wait on
	:param timeout: if not :const:`None`, time out after this many seconds; running processes are left untouched after timeout
	:param abort: if :const:`True`, terminate remaining running processes after an abnormal completion (exit code not 0)
	:returns: a list of tuples ``(process, output)``, in order of completion, of process objects and their captured ``(stdout, stderr)`` output, if any
	"""
	def _wrapproc(p):
		async def pwait():
			r = await p.communicate()
			return p, r
		return pwait()

	rets = []
	for coro in asyncio.as_completed([_wrapproc(p) for p in procs], timeout=timeout):
		try:
			res = await coro
		except TimeoutError:
			break
		rets.append(res)
		if abort and res.returncode:
			_killall(procs)
			abort = False
	return rets


async def ex(*cmds, stdin=None, stdout=None, stderr=None,
                    timeout=None, hard_timeout=True, **kwargs):
	"""
	Execute a series of commands in a pipeline.

	:param cmds: sequence of :class:`btrsync.util.Cmd`-like commands that form the pipeline
	:param stdin: standard input of the first command in the pipeline; :const:`None` means inherit from caller
	:param stdout: standard output of the last command in the pipeline; :const:`None` means inherit from caller
	:param stderr: standard error of all commands in the pipeline; :const:`None` means inherit from caller
	:param timeout: if not :const:`None`, time out after this many seconds
	:param hard_timeout: if :const:`True`, kill spawned processes on timeout, otherwise leave them untouched
	:param kwargs: additional keyword arguments to be passed to :func:`.wait_procs`
	:returns: a tuple ``(procs, rets)``: a list of spawned :class:`asyncio.subprocess.Process` objects, in the order specified by `cmds`, and
		      a list of tuples ``(process, output)``, in order of completion, of process objects and their captured ``(stdout, stderr)`` output, if any
	"""
	procs = []
	try:
		async for p in create_pipeline(*cmds, stdin=stdin, stdout=stdout, stderr=stderr):
			procs.append(p)
	except:
		_killall(procs)
		await _waitall(procs)
		raise

	try:
		r = await wait_procs(procs, timeout=timeout, **kwargs)
	except:
		_killall(procs)
		await _waitall(procs)
		raise
	if len(r) < len(procs) and hard_timeout:
		_killall(procs)
		await _waitall(procs)
	return procs, r

async def ex_out(*cmds, stdout=PIPE, **kwargs):
	"""
	Execute a series of commands in a pipeline, capturing standard output and error.

	:param cmds: sequence of :class:`btrsync.util.Cmd`-like commands that form the pipeline
	:param stdin: standard input of the first command in the pipeline; :const:`None` means inherit from caller
	:param timeout: if not :const:`None`, time out after this many seconds; remaining running processes are killed on timeout
	:returns: a list of tuples ``(exit_code, output)``, in the order specified by `cmds`, of the processes' exit code and captured ``(stdout, stderr)`` output
	"""
	proc, ret = await ex(*cmds, stdout=stdout, stderr=PIPE, hard_timeout=True, **kwargs)
	rv = {r[0]: (r[0].returncode, r[1]) for r in ret}
	return [rv[p] if p in rv else (None, (b'', b'')) for p in proc]
