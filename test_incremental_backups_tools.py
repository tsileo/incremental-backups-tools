# -*- coding: utf-8 -*-
import unittest
import fake_filesystem
import fake_filesystem_shutil
import fake_tempfile
import dirtools


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
        fk.CreateFile('/test_dirtools/.exclude', contents='excluded_dir/\n*.pyc')

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

        # Sort of "monkey patch" to make dirtools use the fake filesystem
        dirtools.os = fake_filesystem.FakeOsModule(fk)
        dirtools.open = fake_filesystem.FakeFileOpen(fk)

        # Dirtools initialization
        self.dir = dirtools.Dir('/test_dirtools')
        self.dir2 = dirtools.Dir('/test_dirtools2')
        self.os = dirtools.os
        self.open = dirtools.open
        self.shutil = fake_filesystem_shutil.FakeShutilModule(fk)
        self.tempfile = fake_tempfile.FakeTempfileModule(self.filesystem)

        self.shutil.copytree('/test_dirtools', '/test_dirtools2')
        self.shutil.copytree('/test_dirtools', '/test_dirtools_copy')

        fk.CreateFile('/test_dirtools2/file4', contents='contents4')
        self.os.remove('/test_dirtools2/file2')
        fk.CreateDirectory('/test_dirtools2/dir3')
        fk.CreateFile('/test_dirtools2/dir3/file3', contents='contents3')
        with self.open('/test_dirtools2/file1', 'w') as f:
            f.write('new things')
        self.shutil.rmtree('/test_dirtools2/dir1/subdir1')

    def testFiles(self):
        """ Check that Dir.files return all files, except those excluded. """
        dir_expected = ["file1",
                        "file2",
                        "file3.py",
                        ".exclude",
                        "dir1/subdir1/file_subdir1",
                        "dir1/subdir1/.project",
                        "dir2/file_dir2"]

        self.assertEqual(sorted(self.dir.files()),
                         sorted(dir_expected))

        dir2_expected = ["file1",
                         "file3.py",
                         "file4",
                         ".exclude",
                         "dir2/file_dir2",
                         "dir3/file3"]

        self.assertEqual(sorted(self.dir2.files()),
                         sorted(dir2_expected))

if __name__ == '__main__':
    unittest.main()
