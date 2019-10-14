#!/usr/bin/env python

from setuptools import setup, find_packages
from codecs import open
import sys
import fastentrypoints

LONG_DESCRIPTION = open('README.md').read()


setup(
    name='recent2',
    version='0.2.2',
    description='Logs bash history to an sqlite database',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    # The project's main homepage.
    url='https://github.com/dotslash/recent2',
    license='MIT',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Environment :: Console',
        'Topic :: System :: Logging',
        'Topic :: System :: Shells',
        'Topic :: Utilities',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only'
    ],
    keywords='logging bash history database sqlite',
    py_modules=["recent2"],
    entry_points={
        'console_scripts': [
            'log-recent=recent2:log',
            'recent-import-bash-history=recent2:import_bash_history',
            'recent=recent2:main',
        ],
    },
)
