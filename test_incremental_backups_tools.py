# -*- coding: utf-8 -*-
import unittest
import os
import shutil

import dirtools
import incremental_backups_tools as ibt


class TestIncrementalBackupstools(unittest.TestCase):
    def setUp(self):
        """ Initialize directory for testing diff and patch. """
        base_path = '/tmp/test_incremental_backups_tools'
        self.base_path = base_path
        os.mkdir(base_path)
        with open(os.path.join(base_path, 'file1'), 'w') as f:
            f.write('contents1')
        with open(os.path.join(base_path, 'file2'), 'w') as f:
            f.write('contents2')
        with open(os.path.join(base_path, 'file3.py'), 'w') as f:
            f.write('print "ok"')
        f = open(os.path.join(base_path, 'file3.pyc'), 'w')
        f.close()
        with open(os.path.join(base_path, '.exclude'), 'w') as f:
            f.write('excluded_dir/\n*.pyc')
        os.mkdir(os.path.join(base_path, 'excluded_dir'))
        with open(os.path.join(base_path, 'excluded_dir/excluded_file'), 'w') as f:
            f.write('excluded')
        os.mkdir(os.path.join(base_path, 'dir1'))
        os.mkdir(os.path.join(base_path, 'dir1/subdir1'))
        with open(os.path.join(base_path, 'dir1/subdir1/file_subdir1'), 'w') as f:
            f.write('inside subir1')
        f = open(os.path.join(base_path, 'dir1/subdir1/.project'), 'w')
        f.close()
        os.mkdir(os.path.join(base_path, 'dir2'))
        with open(os.path.join(base_path, 'dir2/file_dir2'), 'w') as f:
            f.write('inside dir2')

        with open(os.path.join(base_path, 'dir1/subdir1/file_subdir1'), 'w') as f:
            f.write('inside subdir1')

        shutil.copytree(base_path, base_path + '2')
        shutil.copytree(base_path, base_path + '3')
        shutil.copytree(base_path, base_path + '4')

        # We modify test_dirtools for the first time
        with open(os.path.join(base_path + '2', 'file4'), 'w') as f:
            f.write('contents4')
        os.remove(os.path.join(base_path + '2', 'file2'))
        os.mkdir(os.path.join(base_path + '2', 'dir3'))
        with open(os.path.join(base_path + '2', 'dir3/file3'), 'w') as f:
            f.write('contents3')
        with open(os.path.join(base_path + '2', 'file1'), 'w') as f:
            f.write('new things')
        shutil.rmtree(os.path.join(base_path + '2', 'dir1/subdir1'))

        self.dir = dirtools.Dir('/tmp/test_incremental_backups_tools')
        self.dir2 = dirtools.Dir('/tmp/test_incremental_backups_tools2')
        self.dir3 = dirtools.Dir('/tmp/test_incremental_backups_tools3')
        self.dir4 = dirtools.Dir('/tmp/test_incremental_backups_tools4')

    def tearDown(self):
        shutil.rmtree('/tmp/test_incremental_backups_tools')
        shutil.rmtree('/tmp/test_incremental_backups_tools2')
        shutil.rmtree('/tmp/test_incremental_backups_tools3')
        shutil.rmtree('/tmp/test_incremental_backups_tools4')

    def testFullBackup(self):
        pass

if __name__ == '__main__':
    unittest.main()
