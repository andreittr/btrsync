#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Command line interface to btrsync. Run as main with '-h' for usage information."""

import re
import sys
import fnmatch
import posixpath
import asyncio
import argparse
import urllib.parse
import dataclasses

from . import sync
from . import VERSION


class IncrSync(sync.BtrSync):
	""":class:`btrsync.sync.BtrSync` class that skips non-incremental transfers."""
	@staticmethod
	def check(vol, parent):
		return parent is not None


def humanbytes(n, sep=' '):
	"""
	Represent `n` bytes in human-readable form using IEC units (i.e., KiB, MiB, etc.).

	:param n: the number of bytes to represent
	:param sep: separator between numeric value and unit
	:returns: human-readable representation as string
	"""
	THRESH = 1024
	UNITS = ('  B', 'KiB', 'MiB', 'GiB', 'TiB', 'EiB')
	SCALE = [(2**(10*i), u) for i, u in enumerate(UNITS)]
	def rv(q, u): return sep.join((f'{q:6.1f}', u))
	for sz, unit in SCALE[:-1]:
		r = n/sz
		if abs(r) < THRESH:
			return rv(r, unit)
	return rv(n/SCALE[-1][0], SCALE[-1][1])


class CliProgress(sync.ProgressTransfer):
	"""Transfer class that periodically reports progress on stdout."""
	def __init__(self, *args, **kwargs):
		super().__init__(prog_seq='|/-\\', *args, **kwargs)

	async def report_progress(self, total, prev, seq):
		print('\r', next(seq), humanbytes(total),
		      humanbytes((total - prev) / self.period) + '/sec', end='')


class BaseMatch:
	"""
	Match against a set of include and exclude globs.

	If no include globs are given, match all not explicitly excluded.
	"""
	def __init__(self):
		self.incl = []
		self.excl = []

	def include(self, *globs):
		"""Add `globs` to the list of included globs."""
		self.incl.extend(globs)

	def exclude(self, *globs):
		"""Add `globs` to the list of excluded globs."""
		self.excl.extend(globs)

	def base_match(self, path):
		"""
		Return the form of `path` to be matched against includes and excludes, or :const:`None` to exclude it outright.

		By default return `path` unaltered; override to change behavior.
		"""
		return path

	def match(self, path):
		"""Return :const:`True` if `path` matches against :func:`base_match` and current includes and excludes, :const:`False` otherwise."""
		rpath = self.base_match(path)
		if rpath is None:
			return False
		if self.incl and not any(fnmatch.fnmatch(rpath, i) for i in self.incl):
			return False
		if any(fnmatch.fnmatch(rpath, x) for x in self.excl):
			return False
		return True

	def stop(self, paths):
		"""
		Return :const:`True` if further processing should stop after handling `paths`, or :const:`False` if it should continue.

		By default always return :const:`False`."""
		return False


class SingleMatch(BaseMatch):
	"""
	Match a single path, accounting for include and exclude globs, and stop all processing afterwards.

	:param path: the target path to match
	"""
	def __init__(self, path):
		super().__init__()
		self.path = path

	def __repr__(self):
		return f'SingleMatch({self.path})'

	def base_match(self, path):
		"""Match a single path and return it unaltered."""
		return path if path == self.path else None

	def stop(self, paths):
		"""Return :const:`True` to stop immediately after processing the target path."""
		assert(self.path in paths)
		return True


class UnderGlob(BaseMatch):
	"""
	Match all paths that are below or matching a particular glob, further accounting for include and exclude globs.

	:param glob: a shell-like glob matching the path prefix of targets
	"""
	def __init__(self, glob):
		super().__init__()
		if posixpath.isabs(glob):
			raise ValueError('glob must specify a relative path')
		if not glob.endswith('*'):
			glob = posixpath.join(glob, '*')
		rx = fnmatch.translate(glob)
		assert(rx.endswith('.*)\\Z'))
		rx = rx[:-len('.*)\\Z')] + '(.*))\\Z'
		self.under = re.compile(rx)
		self._glob = glob
		self._re = rx

	def __repr__(self):
		return f'UnderGlob({self._glob})'

	def base_match(self, path):
		"""Match everything below the base glob, and return a path relative to it."""
		m = self.under.match(path)
		return m.groups()[0] if m is not None else None


@dataclasses.dataclass(frozen=True)
class SSHLoc:
	"""Convenience class to parse, store, and validate SSH location parameters."""
	user: str
	host: str
	port: str

	SSHRE = re.compile('(?:([^@]*)@)?(.*)')
	URLRE = re.compile('(?:([^@:]*)@)?(\[[A-Fa-f0-9:]+\]|[^:]*)(?::(.*))?')
	@classmethod
	def parse_ssh(cls, locstr):
		"""Parse a SSH location from a ``user@hostname`` form."""
		return cls(*cls.SSHRE.match(locstr).groups(), None)
	@classmethod
	def parse_url(cls, netloc):
		"""Parse a SSH location from a URL netloc component."""
		return cls(*cls.URLRE.match(netloc).groups())

	def validate(self):
		"""
		Validate SSH parameters: `host` cannot be empty, and `user` or `port`, if specified, cannot be empty.

		:returns: `self`
		:raises ValueError: for invalid parameters
		"""
		if not self.host:
			raise ValueError('SSH host cannot be empty')
		if self.user is not None and not self.user:
			raise ValueError('SSH user, if specified, cannot be empty')
		if self.port is not None and not self.port:
			raise ValueError('SSH port, if specified, cannot be empty')
		return self

	def asdict(self):
		"""Return parameters of `self` in the form of a :class:`dict`."""
		return dataclasses.asdict(self)


SSHLOC_RE = re.compile('^((?:[^/:@]*@)?\[[A-Fa-f0-9:]+\]|[^/:]*):(.*)')
URLSCHEME_RE = re.compile('^[A-Za-z][A-Za-z0-9+.-]*://(.*)')

def parse_root(locstr):
	"""
	Parse a location string into a protocol string and btrfs root options.

	:param locstr: the location string to parse
	:returns: a tuple ``(protocol, root_options, root_arguments)``:
		the protocol to pass to :func:`btrsync.sync.default_root` to obtain a root factory,
		the arguments to pass to the root factory to obtain a root class, and
		the location to pass to the root class, respectively.
	"""
	sshmatch = SSHLOC_RE.match(locstr)
	if sshmatch:
		urlmatch = URLSCHEME_RE.match(locstr)
		if urlmatch:
			url = urllib.parse.urlparse(locstr)
			if url.scheme == 'file':
				return 'local', {}, urlmatch.groups()[0]
			elif url.scheme == 'ssh':
				return 'ssh', SSHLoc.parse_url(url.netloc).validate().asdict(), url.path
			else:
				return url.scheme, url
		else:
			host, path = sshmatch.groups()
			return 'ssh', SSHLoc.parse_ssh(host).validate().asdict(), path
	else:
		return 'local', {}, locstr


async def dest_root(loc, rootopts={}, rootargs={}):
	"""Process a destination location string, returning a tuple of ``(btrfs_root, receive_path)``."""
	prot, largs, path = parse_root(loc)
	root, recvpath = await sync.default_root(prot)(**largs, **rootopts).get_root(path, **rootargs)
	return root, recvpath


async def src_root(loc, rootopts={}, rootargs={}):
	"""Process a source location string, returning a tuple of ``(btrfs_root, matcher_instance)``."""
	prot, largs, path = parse_root(loc)
	rtype = sync.default_root(prot)(**largs, **rootopts)
	if await rtype.is_root(path):
		if path.endswith('/'):
			root = rtype(path, **rootargs)
			matcher = UnderGlob('*')
		else:
			root, rpath = await rtype.get_root(posixpath.dirname(path), **rootargs)
			matcher = SingleMatch(posixpath.join(rpath, posixpath.basename(path)))
	else:
		root, rglob = await rtype.get_root(posixpath.dirname(path), **rootargs)
		matcher = UnderGlob(posixpath.join(rglob, posixpath.basename(path)))
	return root, matcher


def format_transfer(volpaths, parent, destdir, *, verb=False):
	"""
	Format the paths that make up a transfer for display on the command line.

	:param volpaths: sequence of paths to send
	:param parent: parent to use for incremental send, or :const:`None` for full send
	:param destdir: destination directory used for receive
	:param verb: if :const:`True` include more details
	:returns: formatted string
	"""
	vpaths = ',\n'.join(volpaths)
	if verb:
		return '\n'.join((
			'',
			vpaths,
			'\t' + (f'incremental from {parent}' if parent is not None else 'full'),
			f'\tinto {destdir}',
		))
	else:
		return vpaths + '\t' + ('full' if parent is None else 'incr') + ' -> ' + destdir


class Confirm(sync.ProgressTransfer):
	"""
	Handle the UI aspects of confirming a sync via the command line.

	:param src: the SOURCE command line argument currently being processed
	"""
	VERBOSE = False

	def __init__(self, src, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._preview = []
		self.src = src

	async def transf(self, vols, par, src, dst):
		"""Transfer function as expected by :meth:`btrsync.sync.BtrSync.sync` that only logs transfers."""
		volpaths, parent = self._sendpaths(vols, par)
		recvpath = self._recvpath(volpaths)
		self._preview.append(format_transfer(volpaths, parent, recvpath, verb=self.VERBOSE))

	def head(self):
		"""Called at the beginning to print a header."""
		print('At source', self.src)

	def preview(self):
		"""Called after the dry run sync finishes to print a preview of the transfers to be performed."""
		if not self._preview:
			print('Nothing to do')
		else:
			print('About to sync the following subvolumes:')
			print(*self._preview, sep='\n')

	def confirm(self):
		"""
		Called after :meth:`.preview` to give final confirmation.

		:returns: ``'Y'`` to proceed with sync,
			``'S'`` to skip the current source and continue with the next, and
			``'N'`` to immediately abort
		"""
		r = 'S' if not self._preview else ''
		while r not in ('Y', 'N', 'S'):
			print('Proceed? [y/N/(s)kip]: ', end='', flush=True)
			r = input().upper()
			if not r:
				r = 'N'
		return r


async def do_btrsync(*, srcs, dst, incls, excls, auto, confirm, syncer, syncopts,
                     transfer, transopts, srootopts, srootargs, drootopts, drootargs):
	"""
	Perform btrsync from `srcs` to `dst`.

	:param srcs: sequence of source locations
	:param dst: destination location
	:param incls: list of globs matching subvolumes to include in the sync
	:param excls: list of globs matching subvolumes to exclude from the sync
	:param auto: if :const:`False` do a dry run, if :const:`None` ask for confirmation, if :const:`True` proceed without asking
	:param confirm: :class:`.Confirm`-like class to handle user interaction for confirmation
	:param syncer: :class:`btrsync.sync.BtrSync`-like class to use for sync
	:param syncopts: keyword arguments to pass to `syncer`
	:param transfer: :class:`btrsync.sync.Transfer`-like class to use for sync
	:param transopts: keyword arguments to pass to `transfer`
	:param srootopts: keyword arguments to pass to source btrfs root class factories
	:param srootargs: keyword arguments to pass to source btrfs root classes
	:param drootopts: keyword arguments to pass to the destination btrfs root class factory
	:param drootargs: keyword arguments to pass to the destination btrfs root class
	"""
	dtask = asyncio.create_task(dest_root(dst, drootopts, drootargs))
	stasks = [asyncio.create_task(src_root(s, srootopts, srootargs)) for s in srcs]
	try:
		droot, recvpath = await dtask
		trans = transfer(recvpath=recvpath, **transopts)
		sources = await asyncio.gather(*stasks)
	except:
		for t in stasks:
			t.cancel()
		await asyncio.wait(stasks)
		raise
	for (sroot, matcher), cursrc in zip(sources, srcs):
		if incls is not None:
			matcher.include(*incls)
		matcher.exclude(*excls)
		s = syncer(sroot, droot)
		o = {
			'target': lambda v: matcher.match(v['path']),
			'stop': lambda vs: matcher.stop([v['path'] for v in vs])
		}
		o.update(syncopts)
		# Confirmation
		if auto is not True:
			conf = confirm(cursrc, recvpath=recvpath, **transopts)
			conf.head()
			if not await s.sync(conf.transf, **o):
				break
			conf.preview()
			if auto is False:
				continue
			cont = conf.confirm()
			if cont == 'S':
				continue
			elif cont != 'Y':
				break
		# Go time
		if not await s.sync(trans.transf, **o):
			break


def process_args(cliargs):
	"""Process :mod:`argparse`-style output into arguments for :func:`.do_btrsync`."""

	prog = cliargs.progress and not cliargs.quiet
	class CliTransfer(CliProgress if prog else sync.Transfer):
		"""Transfer class tailored to cli arguments."""
		if cliargs.quiet < 2:
			@staticmethod
			def err(e, *args):
				print('Error:', e, file=sys.stderr)
				if args:
					print(f"@ {', '.join(x['path'] for x in args)}", file=sys.stderr)

		if not cliargs.quiet:
			async def report(self, vols, par, src, dst):
				volpaths, parent = self._sendpaths(vols, par)
				recvpath = self._recvpath(volpaths)
				print(format_transfer(volpaths, parent, recvpath, verb=cliargs.verbose))
			@staticmethod
			async def report_done(vols, par, src, dst):
				print(" - Done")

	class CliConfirm(Confirm):
		VERBOSE = cliargs.verbose

	transopts = {'replicate_dirs': cliargs.replicate_dirs}
	if prog:
		transopts['period'] = cliargs.progress_period
	srootopts = {'sudo': cliargs.sudo or cliargs.sudo_src}
	drootopts = {'sudo': cliargs.sudo or cliargs.sudo_dest}
	srootargs = {}
	if cliargs.scope is not None:
		srootargs['scope'] = cliargs.scope
	drootargs = {'create_recvpath': cliargs.create_destpath or cliargs.replicate_dirs}

	return {
		'srcs': cliargs.src,
		'dst': cliargs.dst,
		'incls': cliargs.include,
		'excls': cliargs.exclude,
		'auto': cliargs.auto,
		'confirm': CliConfirm,
		'syncer': IncrSync if cliargs.incremental_only else sync.BtrSync,
		'syncopts': {'batch': cliargs.batch, 'parallel': cliargs.parallel, 'transfer_existing': cliargs.existing},
		'transfer': CliTransfer,
		'transopts': transopts,
		'srootopts': srootopts,
		'srootargs': srootargs,
		'drootopts': drootopts,
		'drootargs': drootargs
	}


def cli_parser():
	"""Return an :mod:`argparse`-like parser for btrsync's command-line options."""
	PROG_VERSION = f'%(prog)s {VERSION}'
	COPYRIGHT = '''Copyright © 2023 Andrei Tatar.
	This is free software; see the source for copying conditions.
	There is NO warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.'''

	parser = argparse.ArgumentParser(prog='btrsync', description='Sync btrfs volumes')
	parser.add_argument('src', metavar='SOURCE', nargs='+',
	                    help='source location, may contain wildcards')
	parser.add_argument('dst', metavar='DESTINATION',
	                    help='destination location')

	parser.add_argument('-x', '--exclude', action='append', metavar='GLOB', default=[],
	                    help='exclude subvolumes matching GLOB')
	parser.add_argument('-i', '--include', action='append', metavar='GLOB',
	                    help='''explicitly include only subvolumes matching GLOB,
	                    overriding the default behavior of including everything matching SOURCE
	                    and not explicitly excluded''')

	parser.add_argument('-f', '--existing', action='store_true',
	                    help='transfer subvolumes even if they exist on the destination')
	parser.add_argument('-I', '--incremental-only', action='store_true',
	                    help='only perform incremental transfers, skip the rest')

	parser.add_argument('-y', '--no-confirm', action='store_const', const=True, dest='auto',
	                    help='do not ask for confirmation, perform transfers immediately')
	parser.add_argument('-n', '--dry-run', action='store_const', const=False, dest='auto',
	                    help='do not perform transfers, print what would have been done')
	parser.add_argument('--interactive', action='store_const', const=None, dest='auto',
	                    help='(default) ask for confirmation before performing transfers')

	parser.add_argument('-v', '--verbose', action='store_true',
	                    help='print more details')
	parser.add_argument('-q', '--quiet', action='count', default=0,
	                    help='supress printing to only errors, specify twice to supress all output except confirmation prompts')

	parser.add_argument('-p', '--progress', action='store_true',
	                    help='print progress during transfer')
	parser.add_argument('-t', '--progress-period', metavar='SEC', type=float, default=1.0,
	                    help='(requires --progress) print progress every SEC seconds (default: 1)')

	parser.add_argument('-B', '--batch', action='store_true',
	                    help='batch multiple subvolumes into a single transfer, as possible')
	parser.add_argument('-P', '--parallel', action='store_true',
	                    help='run independent transfers in parallel')

	parser.add_argument('-c', '--create-destpath', action='store_true',
	                    help='create the path specified in DESTINATION if it does not exist')
	parser.add_argument('-r', '--replicate-dirs', action='store_true',
	                    help='''(implies `-c') replicate the directory structure
	                    containing subvolumes in SOURCEs over to DESTINATION;
	                    paths are taken relative to the source subvolume root
	                    and applied on top of DESTINATION''')

	parser.add_argument('-s', '--sudo', action='store_true',
	                    help="use `sudo' for commands, in both source and destination")
	parser.add_argument('--sudo-src', action='store_true',
	                    help="use `sudo' for commands executed in source")
	parser.add_argument('--sudo-dest', action='store_true',
	                    help="use `sudo' for commands executed in destination")
	parser.add_argument('--scope', choices=('all', 'strict', 'isolated'),
	                    help='''set the scope for subvolume discovery:
	                    'all' considers all accessible subvolumes,
	                    'strict' will only consider subvolumes directly contained by the source subvolume,
	                    and 'isolated' completely ignores all other subvolumes even for internal calculations
	                    (warning: 'isolated' may dumb down automatic incremental transfers)''')
	vcopts = parser.add_argument_group('version and copyright')
	vcopts.add_argument('-V', '--version', action='version', version=PROG_VERSION,
	                    help='Print version')
	vcopts.add_argument('--copyright', action='version', version=COPYRIGHT,
	                    help='Print copyright information')
	return parser


def cli_main(argv):
	"""Parse command-line arguments from `argv` and run :func:`.do_btrsync`."""
	args = cli_parser().parse_args(args=argv)
	btrsync_args = process_args(args)
	try:
		asyncio.run(do_btrsync(**btrsync_args))
	except BaseException as e:
		if args.quiet < 2:
			print(e, file=sys.stderr)
		if not args.quiet:
			print('Aborted')
		return 1
	else:
		return 0

def main():
	"""Call :func:`.cli_main` with :data:`sys.argv`."""
	return cli_main(sys.argv[1:])

if __name__ == '__main__':
	sys.exit(main())
