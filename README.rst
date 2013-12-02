===========================
 Incremental-Backups-Tools
===========================

Storage agnostic incremental backups tools, building blocks for creating incremental backups utilities.

* Use `python-librsync <https://github.com/smartfile/python-librsync>`_ to compute patch/diff.
* Rely on `dirtools <https://github.com/tsileo/dirtools>`_ (for .gitignore like exlusion, and helpers it provides) 

This project is initially designed as a foundation for `bakthat <http://docs.bakthat.io>`_ incremental backups plugin, so the implementation of features like signature, encryption, storage, management of full/incremental backups is up to you.


Components
==========

Full Backup
-----------

A full backup results in three files:

* A SigVault archive (stored in your cache, but also uploaded)
* An archive containing your backups
* A JSON file containing directory state


Incremental Backup
------------------

An incremental backup results in 2-4 file depending on the changes:

* A SigVault archive (stored in your cache, but also uploaded)
* An archive containing created files if any
* An archive containing deltas files if any
* A JSON file containing directory state


SigVault
--------

A ``SigVault`` is a ``tarfile`` wrapper used to store files signatures, used later to compute deltas.

A new one is created for each full/incremental backups, there are stored remotely but it's also saved in the cache, so we don't need to download them each time we want to perform a backup.

When looking for a signature, a search is performed in each ``SigVault``, starting from the most recent until we found it.


Installation
============

.. code-block::

    $ sudo apt-get install librsync-dev
    $ pip install incremental-backups-tools


Usage
=====


.. code-block:: python

    from incremental_backups_tools import full_backup, incremental_backup, restore_backup

    backups_files_report = full_backup('/path/to/backup')

    # After some times
    backups_files_report = incremental_backup('/path/to/backup')

    # Something happened, you must restore from all the archives
    restore_backup('backup', '/path/to/backup_restored')


Everything is store in your default temporary directory, but you can set a different directory:

.. code-block::

    $ export TMP=/my/new/tmp/dir


TODO
====

* Delete old ``SigVault`` when a new full backup is performed.
* Restore oldest backup (match a datetime for selecting full backup to start with)


License (MIT)
=============

Copyright (c) 2013 Thomas Sileo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
