# -*- coding: utf-8 -*-
import tempfile
import os
import re
import logging
from datetime import datetime

import dirtools
from incremental_backups_tools import tarvolume

log = logging.getLogger('incremental_backups_tools.backup')


class Backup(object):
    def __init__(self, path):
        if os.path.isfile(path):
            self.dir = dirtools.File(path)
        elif os.path.isdir(path):
            self.dir = dirtools.Dir(path)
        else:
            raise TypeError("Path must be a file or a directory.")

    def 

backup = Backup('/work/writing')
print backup.dir
