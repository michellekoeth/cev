#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='cev',
    version='0.1.0',
    description='Claim Evolution Visualizer 0.1',
    long_description=readme,
    author='Michelle Koeth',
    url='https://github.com/michellekoeth/cev',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)
