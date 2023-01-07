#!/usr/bin/env python

# Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from distutils.core import setup
from setuptools import find_namespace_packages

setup(name='btrsync',
      packages=find_namespace_packages(include=['btrsync*']))
