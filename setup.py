#!/usr/bin/env python

import sys

from setuptools import setup, find_packages

if 'register' in sys.argv or 'upload' in sys.argv:
    raise Exception('I don\'t want to be on PyPI!')

setup(
    name='contract-plus',
    description='contract forked from https://github.com/barbuza/contract',
    license='none',
    version='1.0',
    author='barbuza',
    author_email='',
    packages=find_packages(),
    include_package_data=True,
    )
