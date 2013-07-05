# -*- coding: utf-8 -*-
import unittest
import os
import shutil

import dirtools
import incremental_backups_tools as ibtools


class TestDirtools(unittest.TestCase):
    def setUp(self):
        """ Initialize a fake filesystem and dirtools. """
        base_path = '/tmp/test_incremental_backups_tools'
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
        self.dir_files_expected = ["file1",
                                   "file2",
                                   "file3.py",
                                   ".exclude",
                                   "dir1/subdir1/file_subdir1",
                                   "dir1/subdir1/.project",
                                   "dir2/file_dir2"]
        self.dir_subdirs_expected = ['dir1', 'dir2', 'dir1/subdir1']
        self.dir_index_expected = {'file2': ([315753376], ['869ed4d9645d8f65f6650ff3e987e335183c02ebed99deccea2917c6fd7be006']),
                                   'file1': ([315687839], ['809da78733fb34d7548ff1a8abe962ec865f8db07820e00f7a61ba79e2b6ff9f']),
                                   'file3.py': ([349242219], ['5932fe0ea4e9ddc50b2e6d72a0fe5b1009349ea8db5b7d4c964ddd6c42417d51']),
                                   'dir1/subdir1/.project': ([], []),
                                   'dir1/subdir1/file_subdir1': ([693962070], ['df6dccc2a48dd11984403b98c9f5b7bea048971a50db6993b16681fadc602f3f']),
                                   '.exclude': ([1213728457], ['b8a48a60f6fd03db625da3afc795bd6ddd8fc6890917d21107d1ecd7f30027df']),
                                   'dir2/file_dir2': ([431817741], ['ea86619208b8f571df0e831911006036d3cb32daf8bbadef7c9e4684d1142581'])}
        self.dir2 = dirtools.Dir('/tmp/test_incremental_backups_tools2')
        self.dir2_files_expected = ["file1",
                                    "file3.py",
                                    "file4",
                                    ".exclude",
                                    "dir2/file_dir2",
                                    "dir3/file3"]

        self.dir3 = dirtools.Dir('/tmp/test_incremental_backups_tools3')

    def tearDown(self):
        shutil.rmtree('/tmp/test_incremental_backups_tools')
        shutil.rmtree('/tmp/test_incremental_backups_tools2')
        shutil.rmtree('/tmp/test_incremental_backups_tools3')

    def testFiles(self):
        """ Check that Dir.files return all files, except those excluded. """
        self.assertEqual(sorted(self.dir.files()),
                         sorted(self.dir_files_expected))

        self.assertEqual(sorted(self.dir2.files()),
                         sorted(self.dir2_files_expected))

    def testDirIndex(self):
        """ Test the DirIndex. """
        di1 = ibtools.DirIndex(self.dir)
        index1 = di1.data()

        self.assertEqual(index1['directory'], '/tmp/test_incremental_backups_tools')
        self.assertEqual(sorted(index1['files']),
                         sorted(self.dir_files_expected))
        self.assertEqual(sorted(index1['subdirs']),
                         sorted(self.dir_subdirs_expected))
        self.assertEqual(index1['index'], self.dir_index_expected)
        keys_expected = ['directory', 'files', 'subdirs', 'index']
        self.assertEqual(sorted(index1.keys()),
                         sorted(keys_expected))

    def testDiffIndexWithNoChanges(self):
        di1 = ibtools.DirIndex(self.dir)
        index1 = di1.data()
        di3 = ibtools.DirIndex(self.dir3)
        index3 = di3.data()

        diff_index = ibtools.DiffIndex(index3, index1).compute()
        #diff_index = ibtools.DiffIndex(index2, index1).compute()

        # Check that the DirIndex is complete
        self.assertEqual(diff_index['dir_index']['directory'],
                         '/tmp/test_incremental_backups_tools3')
        self.assertEqual(sorted(diff_index['dir_index']['files']),
                         sorted(self.dir_files_expected))
        self.assertEqual(sorted(diff_index['dir_index']['subdirs']),
                         sorted(self.dir_subdirs_expected))
        self.assertEqual(diff_index['dir_index']['index'],
                         self.dir_index_expected)

        self.assertEqual(diff_index['created'], [])
        self.assertEqual(diff_index['deleted'], [])
        self.assertEqual(diff_index['deleted_dirs'], [])
        self.assertEqual(diff_index['updated'], [])
        self.assertEqual(diff_index['deltas'], [])

    def testDiffIndexWithChanges(self):
        di1 = ibtools.DirIndex(self.dir)
        index1 = di1.data()
        di2 = ibtools.DirIndex(self.dir2)
        index2 = di2.data()

        diff_index = ibtools.DiffIndex(index2, index1).compute()

        self.assertEqual(diff_index['dir_index']['directory'],
                         '/tmp/test_incremental_backups_tools2')
        self.assertEqual(sorted(diff_index['dir_index']['files']),
                         sorted(self.dir2_files_expected))

        self.assertEqual(sorted(diff_index['created']),
                         sorted(['dir3/file3', 'file4']))
        self.assertEqual(diff_index['updated'], ['file1'])
        self.assertEqual(sorted(diff_index['deleted']),
                         sorted(['dir1/subdir1/file_subdir1',
                                 'file2', 'dir1/subdir1/.project']))
        self.assertEqual(diff_index['deleted_dirs'], ['dir1/subdir1'])

    def testPatchDiff(self):
        self.assertNotEqual(self.dir2.hash(), self.dir.hash())
        di1 = ibtools.DirIndex(self.dir)
        index1 = di1.data()
        di2 = ibtools.DirIndex(self.dir2)
        index2 = di2.data()

        diff_index = ibtools.DiffIndex(index2, index1).compute()
        diff_archive = '/tmp/testpatchdiff.tgz'
        ibtools.DiffData(diff_index).create_archive(diff_archive)
        ibtools.apply_diff('/tmp/test_incremental_backups_tools', diff_index, diff_archive)
        os.remove(diff_archive)

        self.assertEqual(self.dir2.hash(), self.dir.hash())

if __name__ == '__main__':
    unittest.main()
