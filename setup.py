#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from setuptools import setup
from talkbot import __version__


# https://pypi.python.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Communications',
    'Topic :: Communications :: Chat',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
]

fname = os.path.join(os.path.abspath(os.path.dirname(
    __file__)), 'requirements.txt')

extra = {
    'entry_points': {
        'console_scripts': ['talk_bot = talkbot.cli:main']
    },
    'install_requires': open(fname, 'r').readlines()
}

setup(
    name='talkbot',
    version=__version__,
    description='',
    author='Yehor Nazarkin',
    author_email='nimnull@gmail.com',
    url='https://github.com/nimnull/talkabit/',
    packages=['talkbot', ],
    license='LICENSE.txt',
    platforms=['OS Independent'],
    classifiers=CLASSIFIERS,
    long_description=open('README.rst').read(),
    include_package_data=True,
    zip_safe=False,
    **extra
)
