import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="incremental-backups-tools",
    version="0.1.0",
    author="Thomas Sileo",
    author_email="thomas.sileo@gmail.com",
    description="Storage agnostic incremental backups tools, building blocks for creating incremental backups utilities.",
    license="MIT",
    keywords="incremental backups diff patch rsync",
    url="https://github.com/tsileo/incremental-backups-tools",
    bugtrack_url="https://github.com/tsileo/incremental-backups-tools/issues",
    py_modules=["incremental_backups_tools"],
    long_description=read("README.rst"),
    install_requires=["dirtools", "pyrsync"],
    tests_require=["pyfakefs"],
    test_suite="test_incremental_backups_tools",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ],
    scripts=["incremental_backups_tools.py"],
)
