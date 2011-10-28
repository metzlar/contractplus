#!/usr/bin/env python

import sys

from setuptools import setup

if 'register' in sys.argv or 'upload' in sys.argv:
    raise Exception('I don\'t want to be on PyPI!')

setup(
    name='contractplus',
    description='contract forked from https://github.com/barbuza/contract',
    license='none',
    version='1.2',
    author='barbuza',
    author_email='',
    py_modules=['contract'],
    install_requires=['python-dateutil>=1.5.0,<2.0.0'],
    )
