import sys
from setuptools import setup

requires = ['dnspython>=2.6.1,<2.8', 'urllib3>=2.5.0,<2.6.0']

setup(name='radiodnscli',
      version='0.0.1',
      scripts=['bin/radiodns'],
      install_requires=requires)
