===========================
 Incremental-Backups-Tools
===========================

Storage agnostic incremental backups tools.

* Use `pyrsync <https://pypi.python.org/pypi/pyrsync>`_ (a pure Python rsync implementation with SHA256 hash) to compute patch/diff.
* Rely on `dirtools <https://github.com/tsileo/dirtools>`_ (for .gitignore like exlusion, and helpers it provides) 

This is initially designed as a foundation for `bakthat <http://docs.bakthat.io>`_ incremental backups plugin, so, implementation of signature, encryption, storage, management of full backups and diff is up to you.


Installation
============

.. code-block::

    $ pip install incremental-backups-tools


Usage
=====

.. code-block:: python

    from incremental_backups_tools import DirIndex, DiffIndex, DiffData, apply_diff
    from dirtools import Dir

    dir = Dir('/home/thomas/mydir')
    DirIndex(dir).to_file('/home/thomas/mydir.index')

    # Store the index

    old_dir_index_data = DirIndex.from_file('/home/thomas/mydir.index')

    # Make some changes in the directory

    dir_index_data = DirIndex(dir).data()
    diff_index = DiffIndex(dir_index_data, old_dir_index_data).compute()
    diff_archive = DiffData(diff_index).create_archive('/home/thomas/mydir.diff.tgz')

    # Reapply these changes from the intial directory

    apply_diff('/home/thomas/mydir', diff_index, diff_archive)


License (MIT)
=============

Copyright (c) 2013 Thomas Sileo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
