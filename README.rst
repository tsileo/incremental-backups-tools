===========================
 Incremental-Backups-Tools
===========================

Storage agnostic incremental backups tools, building blocks for creating incremental backups utilities.

* Use `python-librsync <https://github.com/smartfile/python-librsync>`_ to compute patch/diff.
* Rely on `dirtools <https://github.com/tsileo/dirtools>`_ (for .gitignore like exlusion, and helpers it provides) 

This project is initially designed as a foundation for `bakthat <http://docs.bakthat.io>`_ incremental backups plugin, so the implementation of features like signature, encryption, storage, management of full/incremental backups is up to you.


Installation
============

.. code-block::

    $ sudo apt-get install librsync-dev
    $ pip install incremental-backups-tools


Usage
=====

.. code-block:: python

    from incremental_backups_tools.diff import DirIndex, DiffIndex, DiffData, apply_diff
    from dirtools import Dir


License (MIT)
=============

Copyright (c) 2013 Thomas Sileo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
