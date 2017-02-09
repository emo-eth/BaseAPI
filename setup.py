#!/usr/bin/env python

from setuptools import setup

version = '0.1.1'

setup(name='BaseAPI',
      py_modules=['BaseAPI'],
      version=version,
      description='A base class for implementing an HTTP API wrapper',
      author='James Wenzel',
      author_email='wenzel.james.r@gmail.com',
      url='https://github.com/jameswenzel/BaseAPI',
      download_url=('http://github.com/jameswenzel/BaseAPI/tarball'
                    '{0}'.format(version)),
      license='Apache License 2.0',
      keywords=['http', 'API', 'REST', 'RESTful', 'API'],
      classifiers=[],
      install_requires=['requests >= 2.2.1']
      )
