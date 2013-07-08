# -*- coding: utf-8 -*-
import tarfile
import hashlib
import shutil
import tempfile
import os
import re
import logging
from datetime import datetime

import simplejson as json
import dirtools
from pyrsync import pyrsync

log = logging.getLogger('incremental_backups_tools')

FILENAME_DATE_FMT = '%Y-%m-%dT%H:%M:%S'


def get_hash(val):
    """ Helper for generating path hash. """
    return hashlib.sha256(val).hexdigest()


def generate_filename(filename, with_date=True, ext="json"):
    """ Helper for generating filename for dump,

    >>> generate_filename('mydir_index')
    mydir_index.2013-07-03-22-20-58.json

    """
    ts = datetime.utcnow().strftime(FILENAME_DATE_FMT)
    if with_date:
        return '{0}.{1}.{2}'.format(filename, ts, ext)
    return '{0}.{1}'.format(filename, ext)


def sort_filename(filename):
    date_str = re.search(r"\d+-\d+-\d+T\d+:\d+:\d+", filename)
    if date_str:
        dt = datetime.strptime(date_str.group(), FILENAME_DATE_FMT)
        return int(dt.strftime('%s'))
    return 0


class DiffBase(object):
    """ Base class for diff tools.

    With helpers to load/dump data from/to files.

    :type _dir: dirtools.Dir instance
    :param _dir: Instance dirtools.Dir

    """
    def __init__(self, _dir):
        self._dir = _dir

    def file_content(self):
        """ Methods that should return the content for dumping to file. """
        raise NotImplemented('Must define a content to dump/load.')

    @classmethod
    def from_file(cls, filename):
        """ Load the JSON file, a stored result of previous main methods call. """
        with open(filename) as f_h:
            return json.loads(f_h.read())

    def to_file(self, filename):
        """ Dump the file in JSON. """
        data = self.file_content()
        with open(filename, "w") as f_h:
            f_h.write(json.dumps(data))


class DirIndex(DiffBase):
    """ Generate a directory index,
        for comparing older version without the full source.

    The index contains:

    - the directory name
    - list of relative files and subdirectories
    - an index containing the pyrsync hash for each file

    """
    def file_content(self):
        return self.data()

    def index(self):
        """ Compute the block checksums for each files (pyrsync algorithm). """
        index = {}
        for f in self._dir.files():
            with open(os.path.join(self._dir.path, f), 'rb') as f_h:
                index[f] = pyrsync.blockchecksums(f_h)
        return index

    def data(self):
        """ Generate the index. """
        data = {}
        data['directory'] = self._dir.path
        data['files'] = list(self._dir.files())
        data['subdirs'] = list(self._dir.subdirs())
        data['index'] = self.index()
        return data


class DiffIndex(DiffBase):
    """ Compare two directory, and generate a DiffIndex, and compute deltas.

    Everything is stored in JSON format when dumping to file.

    The DiffIndex compares the current dir_index with cmp_index,
    cmp_index should be the dir_index of the last diff/backup.

    The diff is needed for patching/restoring.

    :type diff_index: dict
    :param: diff_index: DiffIndex data for the current version of the directory

    :type cmp_index: dict
    :param cmp_index: Old DirIndex for computing incremental changes

    """
    def __init__(self, dir_index, cmp_index):
        self.dir_index = dir_index
        self.cmp_index = cmp_index

    def compute(self):
        """ Actually compute the DirIndex data. """
        data = {}
        data['dir_index'] = self.dir_index
        data['deleted'] = list(set(self.cmp_index['files']) - set(self.dir_index['files']))
        data['created'] = list(set(self.dir_index['files']) - set(self.cmp_index['files']))
        data['updated'] = []
        data['deleted_dirs'] = list(set(self.cmp_index['subdirs']) - set(self.dir_index['subdirs']))
        data['deltas'] = []
        data['hashdir'] = dirtools.Dir(self.dir_index['directory']).hash()

        for f in set(self.cmp_index['files']).intersection(set(self.dir_index['files'])):
            # We cast the block checksums to list as pyrsync return tuple, and json list
            if list(self.cmp_index['index'][f]) != list(self.dir_index['index'][f]):
                # We load the file to generate the delta against the old index
                f_abs = open(dirtools.os.path.join(self.dir_index['directory'],
                             f), 'rb')

                # We store the delta in a temporary file, the file will be deleted when stored in the archives.
                delta_tmp = tempfile.NamedTemporaryFile(delete=False)
                delta_tmp.write(json.dumps(pyrsync.rsyncdelta(f_abs, self.cmp_index['index'][f])))
                data['deltas'].append({'path': f, 'delta_path': delta_tmp.name})
                data['updated'].append(f)
                delta_tmp.close()

        return data

    def file_content(self):
        return self.compute()


class DiffData(DiffBase):
    """ Handle the archive creation for the DiffIndex.

    Take the DiffIndex data, and put needed files in an archive.

    :type diff_index: dict
    :param diff_index: DiffIndex.compute() result

    """
    def __init__(self, diff_index):
        self.diff_index = diff_index

    def create_archive(self, archive_path):
        """ Actually create a tgz archive, with two directories:

        - created, where the new files are stored.
        - updated, contains the pyrsync deltas.

        Everything is stored at root, with the hash of the path as filename.

        :type archive_path: str
        :param archive_path: Path to the archive

        """
        tar = tarfile.open(archive_path, mode='w:gz')
        # Store the created files in the archive, in the created/ directory
        for created in self.diff_index['created']:
            path = os.path.join(self.diff_index['dir_index']['directory'],
                                created)
            filename = get_hash(created)
            tar.add(path, arcname=os.path.join('created/', filename))

        # Store the delta in the archive, in the updated/ directory
        for delta in self.diff_index['deltas']:
            filename = get_hash(delta['path'])
            arcname = os.path.join('updated/', filename)
            # delta_path is the path to the tmpfile DiffIndex must have created
            tar.add(delta['delta_path'], arcname=arcname)
            os.remove(delta['delta_path'])

        tar.close()


def apply_diff(base_path, diff_index, diff_archive):
    """ Patch the directory base_path with diff_index/diff_archive.

    :param diff_index: The DiffIndex data.
    :param diff_archive: The DiffData archive corresponding to the DiffIndex.

    Open the tarfile, and apply the updated, created, deleted,
    deleted_dirs on base_path.

    """
    tar = tarfile.open(diff_archive, mode='r:gz')

    # First step, we iterate over the updated files
    for updtd in diff_index['updated']:
        try:
            print(updtd)
            abspath = os.path.join(base_path, updtd)

            member = tar.getmember(os.path.join('updated', get_hash(updtd)))

            # Load the pyrsync delta stored in JSON
            delta_file = tar.extractfile(member)
            delta = json.loads(delta_file.read())
            delta_file.close()

            # A tempfile file to store the patched file/result
            # before replacing the original
            patched = tempfile.NamedTemporaryFile()

            # Patch the current version of the file with the delta
            # and store the result in the previously created tempfile
            with open(abspath, 'rb') as f:
                pyrsync.patchstream(f, patched, delta)

            patched.seek(0)

            # Now we replace the orignal file with the patched version
            with open(abspath, 'wb') as f:
                shutil.copyfileobj(patched, f)

            patched.close()

        except KeyError as exc:
            # It means that a file is missing in the archive.
            log.exception(exc)
            raise Exception("DIFF CORRUPTED")

    # Next, we iterate the created files
    for crtd in diff_index['created']:
        try:
            member = tar.getmember(os.path.join('created', get_hash(crtd)))
            src_file = tar.extractfile(member)

            abspath = os.path.join(base_path, crtd)
            dirname = os.path.dirname(abspath)

            # Create directories if they doesn't exist yet
            if not os.path.exists(dirname):
                    os.makedirs(dirname)

            # We copy the file from the archive directly to its destination
            with open(abspath, 'wb') as f:
                shutil.copyfileobj(src_file, f)

        except KeyError as exc:
            # It means that a file is missing in the archive.
            log.exception(exc)
            raise Exception("DIFF CORRUPTED")

    # Then, we iterate the deleted files
    for dltd in diff_index['deleted']:
        print(dltd)
        abspath = os.path.join(base_path, dltd)
        if os.path.isfile(abspath):
            os.remove(abspath)

    # Finally, we iterate the deleted directories
    for dltd_drs in diff_index['deleted_dirs']:
        print(dltd_drs)
        abspath = os.path.join(base_path, dltd_drs)
        if os.path.isdir(abspath):
            os.rmdir(abspath)

    tar.close()

    try:
        assert dirtools.Dir(base_path).hash() == diff_index['hashdir']
    except AssertionError:
        log.error("Diff integrity check failed.")
