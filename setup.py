#!/usr/bin/env python3
import sys

from setuptools import find_packages, setup

import versioneer

min_version = (3, 7)

if sys.version_info < min_version:
    error = """
whatrecord does not support Python {0}.{1}.
Python {2}.{3} and above is required. Check your Python version like so:

python3 --version

This may be due to an out-of-date pip. Make sure you have pip >= 9.0.1.
Upgrade pip like so:

pip install --upgrade pip
""".format(
        *sys.version_info[:2], *min_version
    )
    sys.exit(error)


with open("requirements.txt") as fp:
    install_requires = [
        line for line in fp.read().splitlines() if line and not line.startswith("#")
    ]

with open("README.rst", encoding="utf-8") as fp:
    readme = fp.read()


setup(
    name="whatrecord",
    cmdclass=versioneer.get_cmdclass(),
    version=versioneer.get_version(),
    packages=find_packages("."),
    author="SLAC National Accelerator Laboratory",
    description="EPICS IOC record search and meta information tool",
    include_package_data=True,
    install_requires=install_requires,
    license="BSD",
    long_description=readme,
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "whatrecord = whatrecord.bin.main:main",
        ]
    },
    package_dir={
        "_whatrecord": "src/_whatrecord",
        "whatrecord": "whatrecord",
    },
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
    ],
)
