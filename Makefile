# Copyright 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: CC0-1.0

all: htmlcov doc dist

.PHONY: test doc .coverage

test:
	python -m unittest

doc:
	$(MAKE) -C doc html

dist:
	python -m build

install: dist
	python -m pip install --force-reinstall $</btrsync*.whl

cov: .coverage
.coverage:
	python -m coverage run --branch --omit='test/*' -m unittest

htmlcov: .coverage
	python -m coverage html

cleanpy:
	find . -type d -name '__pycache__' -execdir rm -rf {} \; 2>/dev/null ||:

cleancov:
	rm -rf .coverage htmlcov

cleandist:
	rm -rf btrsync.egg-info dist

cleandoc:
	@$(MAKE) -C doc clean

cleandocgen:
	@$(MAKE) -C doc cleangen

clean: cleanpy cleancov cleandist cleandoc cleandocgen
