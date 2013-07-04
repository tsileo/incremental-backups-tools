# -*- coding: utf-8 -*-
import tarfile
import hashlib
from tempfile import NamedTemporaryFile
import shutil
import tempfile
import os
from datetime import datetime

import simplejson as json
import dirtools
from pyrsync import pyrsync
import seccure

CURVE = 'secp256r1/nistp256'


def get_hash(val):
    """ Helper for generating path hash. """
    return hashlib.sha256(val).hexdigest()


def generate_filename(filename, ext="json"):
    """ Helper for generating filename for dump,

    >>> generate_filename('mydir_index')
    mydir_index.2013-07-03-22-20-58.json

    """
    ts = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
    return '{0}.{1}.{2}'.format(filename, ts, ext)


class DiffBase(object):
    """ Base object for subclassing,
        with helpers to load/dump data from/to files. """
    def __init__(self, _dir):
        self._dir = _dir

    def file_content(self):
        """ Methods that should return the content for dumping to file. """
        raise NotImplemented()

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
            with open(os.path.join(self._dir.directory, f), 'rb') as f_h:
                index[f] = pyrsync.blockchecksums(f_h)
        return index

    def data(self):
        """ Generate the index. """
        data = {}
        data['directory'] = self._dir.directory
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

    """
    def __init__(self, dir_index, cmp_index):
        self.dir_index = dir_index
        self.cmp_index = cmp_index

    def compute(self):
        data = {}
        data['dir_index'] = self.dir_index
        data['deleted'] = list(set(self.cmp_index['files']) - set(self.dir_index['files']))
        data['created'] = list(set(self.dir_index['files']) - set(self.cmp_index['files']))
        data['updated'] = []
        data['deleted_dirs'] = list(set(self.cmp_index['subdirs']) - set(self.dir_index['subdirs']))
        data['deltas'] = []

        for f in set(self.cmp_index['files']).intersection(set(self.dir_index['files'])):
            if self.cmp_index['index'][f] != self.dir_index['index'][f]:
                # We load the file to generate the delta against the old index
                f_abs = open(dirtools.os.path.join(self.dir_index['directory'],
                             f), 'rb')

                # We store the delta in a temporary file, the file will be deleted when stored in the archives.
                delta_tmp = NamedTemporaryFile(delete=False)
                delta_tmp.write(json.dumps(pyrsync.rsyncdelta(f_abs, self.cmp_index['index'][f])))
                data['deltas'].append({'path': f, 'delta_path': delta_tmp.name})
                data['updated'].append(f)
                delta_tmp.close()

        return data

    def file_content(self):
        return self.compute()


class DiffData(DiffBase):
    """ Create the archive, just after the index creation, and put everything in a tarfile. """
    def __init__(self, diff_index):
        self.diff_index = diff_index

    def create_archive(self):
        """ Actually create a tgz archive, with two directories:

        - created, where the new files are stored.
        - updated, contains the pyrsync deltas.

        Everything is stored at root, with the hash of the path as filename.

        """
        tar = tarfile.open('/tmp/testdirtools.tgz', mode='w:gz')  # fileobj=out

        for created in self.diff_index['created']:
            path = os.path.join(self.diff_index['dir_index']['directory'],
                                created)
            filename = get_hash(created)
            tar.add(path, arcname=os.path.join('created/', filename))

        for delta in self.diff_index['deltas']:
            filename = get_hash(delta['path'])
            arcname = os.path.join('updated/', filename)
            tar.add(delta['delta_path'], arcname=arcname)
            os.remove(delta['delta_path'])

        tar.close()


def apply_diff(base_path, diff_index, diff_archive):
    """ Patch the directory base_path with diff_index/diff_archive.

    :param diff_index: The DiffIndex data.
    :param diff_archive: The DiffData archive corresponding to the DiffIndex.

    Open the tarfile, and apply the updated, created, deleted, deleted_dirs on base_path.

    """
    tar = tarfile.open('/tmp/testdirtools.tgz')
    for updtd in diff_index['updated']:
        try:
            print(updtd)
            abspath = os.path.join(base_path, updtd)

            member = tar.getmember(os.path.join('updated', get_hash(updtd)))

            delta_file = tar.extractfile(member)
            delta = json.loads(delta_file.read())
            delta_file.close()

            patched = tempfile.NamedTemporaryFile()

            with open(abspath, 'rb') as f:
                pyrsync.patchstream(f, patched, delta)

            patched.seek(0)

            with open(abspath, 'wb') as f:
                shutil.copyfileobj(patched, f)

            patched.close()

        except KeyError as exc:
            # It means that a file is missing in the archive.
            print("DIFF CORRUPTED")

    for crtd in diff_index['created']:
        try:
            member = tar.getmember(os.path.join('created', get_hash(crtd)))
            src_file = tar.extractfile(member)

            abspath = os.path.join(base_path, crtd)
            dirname = os.path.dirname(abspath)

            if not os.path.exists(dirname):
                    os.makedirs(dirname)

            with open(abspath, 'wb') as f:
                shutil.copyfileobj(src_file, f)

        except KeyError as exc:
            # It means that a file is missing in the archive.
            print("DIFF CORRUPTED")

    for dltd in diff_index['deleted']:
        print(dltd)
        abspath = os.path.join(base_path, dltd)
        if os.path.isfile(abspath):
            os.remove(abspath)

    for dltd_drs in diff_index['deleted_dirs']:
        print(dltd_drs)
        abspath = os.path.join(base_path, dltd_drs)
        if os.path.isdir(abspath):
            os.rmdir(abspath)

    tar.close()


# TODO gerer les symlinks
# TODO voir deux patchs de suite => unit test
# TODO reflechir a l'encyption avec seccure

"""

d1 = dirtools.Dir('/work/test_dirtools')
di1 = DirIndex(d1).data()

d2 = dirtools.Dir('/work/test_dirtools2')
di2 = DirIndex(d2).data()

#from pprint import pprint
diff_index = DiffIndex(di2, di1).compute()
print diff_index

DiffData(diff_index).create_archive()
#pprint(json.loads(open('/tmp/omg.json').read()))

# TODO
# * Identifiant DiffData
# * Comment connaitre le last full ?
d1 = dirtools.Dir('/work/test_dirtools')
di1 = DirIndex(d1).data()

d2 = dirtools.Dir('/work/test_dirtools2')
di2 = DirIndex(d2).data()

#from pprint import pprint
diff_index = DiffIndex(di2, di1).compute()
#print diff_index

base_path = diff_index['dir_index']['directory']
base_path = '/work/test_dirtools'



"""



print generate_filename("test_dirtools_index")
# TODO trouver un moyen clean de gerer les dumps
# TODO faire un enchainement facile des trucs
# TODO voir ou duplicity gere son cache, faire pareil.
# TODO voir lintegration dans Dirtools ou un autre package ?
# README storage agnostic incremental backup tool
#       don't split big files.
#       
# incremental-backup-tool => incremental_backup_tool
