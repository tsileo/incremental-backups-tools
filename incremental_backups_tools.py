# -*- coding: utf-8 -*-
import tarfile
import hashlib
import shutil
import tempfile
import os
import re
import logging
from datetime import datetime
import collections

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




class TarVolume(dirtools.Dir):
    """ Implement multi volume tarfile archives.

    :type path: str
    :param path: Path where the volumes are stored.

    :type archive_key: str
    :param archive_key: Archive key

    :type volume_index: dict
    :param volume_index: Volume index (optional when full restore)

    """
    def __init__(self, path, archive_key=None, volume_index=None, volume_size=2 ** 20):
        _return = super(TarVolume, self).__init__(path)
        self.init = False
        self.archive_key = archive_key
        if self.archive_key is None:
            self.archive_key = self.directory
        self.volumes = list(self.files('{0}.vol*.tgz'.format(archive_key)))
        self.volume_index = volume_index
        if volume_index is None:
            self.volume_index = collections.defaultdict(set)
        self.volume_generator = self._volume_generator()
        self.volume_size = volume_size
        return _return

    def _volume_generator(self):
        archive_name = self.archive_key + '.vol{0}.tgz'
        i = 0
        while 1:
            # TODO gerer le archive name
            current_archive = archive_name.format(i)
            archive = open(os.path.join(tempfile.gettempdir(), current_archive), 'wb')
            yield tarfile.open(fileobj=archive, mode='w:gz'), archive
            i += 1

    def _init_archive(self):
        """ Init the first volume. """
        if not self.init:
            self._tar, self._archive = self.volume_generator.next()
            self.volumes.append(self._archive.name)
            self.init = True

    def _archive_size(self):
        """ Return the current volume size. """
        return os.fstat(self._archive.fileno()).st_size

    def _check_size(self, size):
        """ Check the size and roll up a new volume/archive if needed.

        :type size: int
        :pram size: Byte size of the next archive size.

        If the file size is greater than the volume size,
        this volume will contains a single file.
        If the current size + next file size is greater than the volume size,
        we generate a new volume.

        """
        if self._archive_size() != 0 and size > self.volume_size:
            self._tar.close(), self._archive.close()
            self._tar, self._archive = self.volume_generator.next()
            self.volumes.append(self._archive.name)

    def close(self):
        """ Must be called once all files have been added. No need to call it with compress. """
        self._tar.close(), self._archive.close()

        # Clean up the volume index for a nicer outputs
        self.volume_index = dict(self.volume_index)
        for k, v in self.volume_index.iteritems():
            self.volume_index[k] = list(v)

    def add(self, name, arcname=None, recursive=True):
        """ Add the file the multi-volume archive, handle volumes transparently.

        Works like tarfile.add

        Don't forget to call close after all add calls.

        """
        self._init_archive()
        if not os.path.isabs(name):
            name = os.path.join(self.path, name)
        if arcname is None:
            arcname = os.path.relpath(name, self.path)

        total_size = self._archive_size() + os.path.getsize(name)
        # Check the volume size, and create a new module if needed
        self._check_size(total_size)

        self._tar.add(name, arcname, recursive=recursive)

        # Add the file to the volume index
        self.volume_index[arcname].add(os.path.basename(self._archive.name))

    def compress(self):
        """ Compress the initialized directory to multi volume gzipped archive.

        Return the list of volumes, and a volume index.

        The volume index map relative filename to volume.

        """
        self._init_archive()
        for root, dirs, files in self.walk():
            cdir = os.path.relpath(root, self.path)

            for f in files:
                # We add the root if the directory is empty, it won't be created
                # automatically.
                if cdir != '.' and not cdir in self.volume_index:
                    self._tar.add(root, arcname=cdir, recursive=False)
                if cdir != '.':
                    # We also track the volumes where the directory is archived.
                    self.volume_index[cdir].add(os.path.basename(self._archive.name))

                absname = os.path.join(root, f)
                arcname = os.path.relpath(absname, self.parent)

                total_size = self._archive_size() + os.path.getsize(absname)
                # Check the volume size, and create a new module if needed
                self._check_size(total_size)

                # Add the file in the archive
                self._tar.add(absname, arcname=arcname)
                # Add the file to the volume index
                self.volume_index[arcname].add(os.path.basename(self._archive.name))

        # Close the archive
        self.close()

        return self.volumes, self.volume_index

    @classmethod
    def from_volumes(cls, volumes, volume_index=None):
        """ Initialize a TarVolume directory with a custom
            volumes list (and optionally a custom volume_index). """
        # Extraire juste un dossier ou juste fichier
        _cls = cls('.')
        _cls.volumes = volumes
        if volume_index is None:
            volume_index = collections.defaultdict(set)
        _cls.volume_index = volume_index
        return _cls

    def extractall(self, path='.'):
        """ Extract the archive to path or the current working directory.

        :type path: str
        :param path: Path for extraction, current working directory by default

        """
        for v in self.volumes:
            if not os.path.isabs(v):
                v = os.path.join(self.path, v)
            tar = tarfile.open(v, 'r:gz')
            tar.extractall(path)
            tar.close()

    def extract(self, member, path=''):
        """ Extract a member to the current working directory or path.

        :type member: str
        :param member: Relative path to the file

        :type path: str
        :param path: Path for extraction, current working directory by default

        """
        if member in self.volume_index:
            # gerer le cas 2 volumes
            for volume in self.volume_index[member]:
                tar = tarfile.open(volume, 'r:gz')
                tar_member = tar.getmember(member)
                tar.extract(tar_member, path)
                tar.close()
        else:
            raise IOError('Member not found in the volume.')

    def extractfile(self, member):
        """ Extract a single fileobject from the multi volume archive.

        :type member: str
        :param member: Relative path to the file

        """
        if member in self.volume_index:
            volume = list(self.volume_index[member])[0]
            tar = tarfile.open(volume, 'r:gz')
            tar_member = tar.getmember(member)
            _return = tar.extractfile(tar_member)
            tar.close()
            return _return
        else:
            raise IOError('Member not found in the volume.')


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
