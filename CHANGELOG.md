<!--
Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>

SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Changelog

## [0.3] - 2023-01-28
**API-BREAKING CHANGES**, see below items and consult up-to-date documentation.

### Added
- Add CLI option `-o` to dump send streams to file
- Add CLI options `-O` and `-e` to control dumping
- Add CLI support for sources from local file dumps
- Add optional argument to `BtrfsRoot.receive()` for send stream metadata
- Add `.roots` as a property to `btrfs.COWTree` API
- Add helper class for subvolume attributes `util.Vol`
- Add user-facing `.name` property to `BtrfsRoot` API
- Add BtrfsRoots for reading and writing local files and dumping to pipes
- Add `.pipeline()`, shell pipeline parsing support to `util.Cmd` API

### Changed
- Move newline in verbose printing of subvolumes from end to beginning
- Refactor passing data between source and destination: introduce Flows
- Refactor task waiting API of Transfer* classes
- `cmdex.create_pipeline()` now accepts standard library file-like objects for `stdin`, `stdout`, and `stderr`
- Rework error handling between `BtrSync` and `Transfer`
- Refactor `do_btrsync` source and destination params
- Cleanup of internal code

### Removed
- Remove `util.FileDesc` in favor of standard library `io.*` objects

### Fixed
- Provide fallback if `os.splice` is not available
- Fix logic error in SSH wrapping of piped commands
- Fix missing error reporting for first failed task
- Ensure progress is reported at transmission end
- Ignore broken pipe errors in calls to `splice()`
- Various documentation fixes

## [0.2.1] - 2023-01-21

### Fixed
- Fix CLI option `-t` not working
- Ensure correct abnormal exit when `do_btrsync()` fails
- Remove broken CLI error formatting

## [0.2] - 2023-01-14

### Added
- Add CLI option to create destination directory
- Add option to replicate source directory structure

### Changed
- Overhaul format of CLI printed transfer details

### Fixed
- Ensure all transfer subtask error messages print
- doc: Clean up table of contents

## [0.1.1] - 2023-01-07

### Fixed
- Fix PyPI project description not showing

## [0.1] - 2023-01-07
Initial release.
