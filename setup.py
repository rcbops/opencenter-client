#!/usr/bin/env python

from setuptools import setup, find_packages

requirements = ['cliapp', 'requests']

setup(name='roush-client',
      version='1.0.0',
      description='Client library for Roush API',
      author='Justin Shepherd',
      author_email='jshepher@rackspace.com',
      url='',
      license='Apache',
      packages=find_packages(exclude=['tests', 'tests.*']),
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
      ],
      install_requires=requirements,
      entry_points={
          'console_scripts': ['r2 = roushclient.client:main']
      }
)
