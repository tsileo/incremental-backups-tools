# -*- coding: utf-8 -*-
import unittest
import fake_filesystem
import fake_filesystem_shutil
import fake_tempfile
import dirtools
import incremental_backups_tools as ibtools


class TestDirtools(unittest.TestCase):
    def setUp(self):
        """ Initialize a fake filesystem and dirtools. """

        # First we create a fake filesystem in order to test dirtools
        fk = fake_filesystem.FakeFilesystem()
        fk.CreateDirectory('/test_dirtools')
        fk.CreateFile('/test_dirtools/file1', contents='contents1')
        fk.CreateFile('/test_dirtools/file2', contents='contents2')
        fk.CreateFile('/test_dirtools/file3.py', contents='print "ok"')
        fk.CreateFile('/test_dirtools/file3.pyc', contents='')
        fk.CreateFile('/test_dirtools/.exclude',
                      contents='excluded_dir/\n*.pyc')

        fk.CreateDirectory('/test_dirtools/excluded_dir')
        fk.CreateFile('/test_dirtools/excluded_dir/excluded_file',
                      contents='excluded')

        fk.CreateDirectory('/test_dirtools/dir1')
        fk.CreateDirectory('/test_dirtools/dir1/subdir1')
        fk.CreateFile('/test_dirtools/dir1/subdir1/file_subdir1',
                      contents='inside subdir1')
        fk.CreateFile('/test_dirtools/dir1/subdir1/.project')

        fk.CreateDirectory('/test_dirtools/dir2')
        fk.CreateFile('/test_dirtools/dir2/file_dir2', contents='inside dir2')

        # Sort of "monkey patch" to use the fake filesystem
        self.os = fake_filesystem.FakeOsModule(fk)
        self.open = fake_filesystem.FakeFileOpen(fk)
        self.shutil = fake_filesystem_shutil.FakeShutilModule(fk)
        self.tempfile = fake_tempfile.FakeTempfileModule(fk)

        ibtools.os = self.os
        ibtools.open = self.open
        ibtools.shutil = self.shutil
        ibtools.tempfile = self.tempfile

        # We make two copies of test_dirtools

        self.shutil.copytree('/test_dirtools', '/test_dirtools2')
        self.shutil.copytree('/test_dirtools', '/test_dirtools3')

        # We modify test_dirtools for the first time

        fk.CreateFile('/test_dirtools2/file4', contents='contents4')
        self.os.remove('/test_dirtools2/file2')
        fk.CreateDirectory('/test_dirtools2/dir3')
        fk.CreateFile('/test_dirtools2/dir3/file3', contents='contents3')
        with self.open('/test_dirtools2/file1', 'w') as f:
            f.write('new things')
        self.shutil.rmtree('/test_dirtools2/dir1/subdir1')

        # Dirtools initialization
        dirtools.os = self.os
        dirtools.open = self.open
        self.dir = dirtools.Dir('/test_dirtools')
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
        self.dir2 = dirtools.Dir('/test_dirtools2')
        self.dir2_files_expected = ["file1",
                                    "file3.py",
                                    "file4",
                                    ".exclude",
                                    "dir2/file_dir2",
                                    "dir3/file3"]

        self.dir3 = dirtools.Dir('/test_dirtools3')

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

        self.assertEqual(index1['directory'], '/test_dirtools')
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
                         '/test_dirtools3')
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
                         '/test_dirtools2')
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
        pass

if __name__ == '__main__':
    unittest.main()
