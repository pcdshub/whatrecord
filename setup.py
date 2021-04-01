#!/usr/bin/env python3
import os

import epicscorelibs
import epicscorelibs.path
from Cython.Build import cythonize
from setuptools import Extension, find_packages, setup

ext_options = dict(
    include_dirs=[
        epicscorelibs.path.base_path,
        epicscorelibs.path.include_path,
        "include",
    ],
    libraries=["Com", "dbCore"],
    library_dirs=[epicscorelibs.path.lib_path],
    language="c++",
)


# https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#distributing-cython-modules
def no_cythonize(extensions, **_ignore):
    for extension in extensions:
        sources = []
        for sfile in extension.sources:
            path, ext = os.path.splitext(sfile)
            if ext in (".pyx", ".py"):
                if extension.language == "c++":
                    ext = ".cpp"
                else:
                    ext = ".c"
                sfile = f"{path}{ext}"
            sources.append(sfile)
        extension.sources[:] = sources
    return extensions


extensions = [
    Extension("whatrecord.iocsh", ["src/whatrecord/iocsh.pyx"], **ext_options),
    Extension(
        "whatrecord.macro",
        ["src/whatrecord/macro.pyx", "src/whatrecord/msi.cpp"],
        **ext_options,
    ),
]

CYTHONIZE = bool(int(os.getenv("CYTHONIZE", 1)))

if CYTHONIZE:
    compiler_directives = {"language_level": 3, "embedsignature": True}
    extensions = cythonize(extensions, compiler_directives=compiler_directives)
else:
    extensions = no_cythonize(extensions)

with open("requirements.txt") as fp:
    install_requires = [
        line for line in fp.read().splitlines() if line and not line.startswith("#")
    ]

setup(
    ext_modules=extensions,
    install_requires=install_requires,
    include_package_data=True,
    packages=find_packages(where="src"),
    # extras_require={"dev": dev_requires, "docs": ["sphinx", "sphinx-rtd-theme"]},
    entry_points={
        "console_scripts": [
            "whatrec = whatrecord.bin.main:main",
        ]
    },
    python_requires=">=3.6",
)
