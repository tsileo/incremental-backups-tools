import os
from setuptools import setup, find_packages


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
    packages=find_packages(),
    long_description=read("README.rst"),
    install_requires=["dirtools", "python-librsync"],
    tests_require=[],
    test_suite="test_incremental_backups_tools",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ],
)
