#!/usr/bin/env python3
import os
import sys

if os.environ.get("CONDA_BUILD_STATE") == "RENDER":
    epicscorelibs = None
else:
    try:
        import epicscorelibs
        import epicscorelibs.path
        from Cython.Build import cythonize
    except (ImportError, ModuleNotFoundError, Exception) as ex:
        print(f"""\
Sorry, the following are required to build `whatrecord`. Please install these first:
    epicscorelibs
    cython
{type(ex).__name__}: {ex}
""", file=sys.stderr)
        raise

from setuptools import Extension, find_packages, setup  # isort: skip
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


def get_extensions():
    """Get the list of Cython extensions to add."""
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

    extensions = [
        Extension(
            "_whatrecord.iocsh",
            ["src/_whatrecord/iocsh.pyx"],
            **ext_options
        ),
        Extension(
            "_whatrecord.macro",
            ["src/_whatrecord/macro.pyx"],
            **ext_options,
        ),
    ]

    CYTHONIZE = bool(int(os.getenv("CYTHONIZE", "1")))

    if CYTHONIZE:
        compiler_directives = {"language_level": 3, "embedsignature": True}
        return cythonize(extensions, compiler_directives=compiler_directives)
    return no_cythonize(extensions)


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
    packages=find_packages('.') + find_packages('src'),
    author="SLAC National Accelerator Laboratory",
    description="EPICS IOC record search and meta information tool",
    ext_modules=get_extensions() if epicscorelibs is not None else [],
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
