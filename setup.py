import sys
from setuptools import setup

if sys.version_info[0] < 3:
    # dnspython dropped support for Python 2.x in 2.0.0
    requires = ['dnspython>=1.16,<2.0']
else:
    requires = ['dnspython>=2.6.1,<2.8']

if sys.version_info[:2] == (3, 4):
    # urllib3 dropped support for Python 3.4 in point release 1.25.8
    requires.append('urllib3>=1.20,<1.25.8')
else:
    requires.append('urllib3>=2.5.0,<2.6.0')

setup(name='radiodnscli',
      version='0.0.1',
      scripts=['bin/radiodns'],
      install_requires=requires)
