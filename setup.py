#!/usr/bin/env python

from setuptools import setup, find_packages

requirements = ['requests<=1.1.0']

setup(
    name='opencenter-client',
    version='1.0.0',
    description='Client library for OpenCenter API',
    author='Rackspace US, Inc.',
    url='https://github.com/rcbops/opencenter-client.git',
    license='Apache2',
    packages=find_packages(exclude=['run_tests.sh', 'tests', 'tests.*']),
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
        'console_scripts': ['r2 = opencenterclient.client:main',
                            'opencentercli = opencenterclient.shell:main']
    }
)
