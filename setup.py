"""A setuptools based setup module.

Derived from:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pyz80',
    version='0.0.1a1',
    description='A Z80 Emulator',
    long_description=long_description,
    url='https://github.com/jamesba/pyz80',
    author='James P. Weaver',
    author_email='james.p.barrett@gmail.com',
    license='Apache2',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: System :: Emulators',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
    ],
    keywords='emulator z80 zx80 zx81 spectrum',
    packages=find_packages(exclude=['tests']),
    package_data={'pyz80' : [ 'roms/*.rom', 'roms/COPYING' ]},
    install_requires=[],
    extras_require={
        'dev': [],
        'test': ['mock'],
    },
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'pyz80=pyz80.__main__:main',
        ],
    },
)
