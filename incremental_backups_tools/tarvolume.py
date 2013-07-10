# -*- coding: utf-8 -*-
import tarfile
import tempfile
import os
import logging
import collections

import dirtools

log = logging.getLogger('incremental_backups_tools.tarvolume')

DEFAULT_VOLUME_SIZE = 20 * 2 ** 20


class TarVolumeReader(object):
    """ Multi-volume archive Writer.

    Allows to extract the full archive (volume by volume) transparently,
    or with the help of a volume_index, extract just some files or a directory.

    Two ways to open a multi-volume archive,
    either providing the path and the archive key,
    either with a list containing the full path of each volume.

    """
    def __init__(self, archive_dir=None, archive_key=None,
                 volumes=[], volume_index=None):
        self.archive_key = archive_key
        self.archive_dir = archive_dir
        self.dir_path = None
        if archive_dir:
            self.dir_path = dirtools.Dir(archive_dir)

        # If no volumes are provided, we gather if from the path/archive_key
        if not volumes:
            glob = '{0}.vol*.tgz'.format(archive_key)
            self.volumes = list(self.dir_path.files(glob))
        else:
            self.volumes = volumes

        if volume_index:
            self.volume_index = volume_index
        else:
            self.volume_index = collections.defaultdict(set)

    def extractall(self, path='.'):
        """ Extract the archive to path or the current working directory.

        :type path: str
        :param path: Path for extraction, current working directory by default

        """
        for v in self.volumes:
            if not os.path.isabs(v) and self.dir_path:
                v = os.path.join(self.dir_path.path, v)
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
            if not os.path.isabs(volume) and self.dir_path:
                volume = os.path.join(self.dir_path.path, volume)
            tar = tarfile.open(volume, 'r:gz')
            tar_member = tar.getmember(member)
            return tar.extractfile(tar_member)
        else:
            raise IOError('Member not found in the volume.')


class TarVolumeWriter(object):
    """ Multi-volume Tar archive Writer.

    :type archive_dir: str
    :param archive_dir: Directory where the volumes will be created.

    :type archive_key: str
    :param archive_key: Archive key for filename creation,
        the archive will be stored in the following format:
        {archive_key}.vol{i}.tgz

    """
    def __init__(self, archive_dir, archive_key,
                 volume_size=DEFAULT_VOLUME_SIZE):
        self.init = False
        self.archive_dir = archive_dir
        self.archive_key = archive_key  # will append .vol{i}.tgz
        # list containing the volumes path
        self.volumes = []
        # Initializing an empty volume index
        self.volume_index = collections.defaultdict(set)
        self.volume_generator = self._volume_generator()
        self.volume_size = volume_size
        self.volume_dir = tempfile.gettempdir()

    def _volume_generator(self):
        """ Volume generator, base on archive_dir and archive_key. """
        archive_name = self.archive_key + '.vol{0}.tgz'
        i = 0
        while 1:
            # TODO gerer le archive name
            current_archive = archive_name.format(i)
            volume_path = os.path.join(self.volume_dir, current_archive)
            archive = bltn_open(volume_path, 'wb')
            yield tarfile.open(fileobj=archive, mode='w:gz'), archive
            i += 1

    def _init_archive(self):
        """ Init the first volume, create the first volume. """
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
        """ Must be called once all files have been added.
        No need to call it with compress. """
        self._tar.close(), self._archive.close()

        # Clean up the volume index for a nicer outputs
        self.volume_index = dict(self.volume_index)
        for k, v in self.volume_index.iteritems():
            self.volume_index[k] = list(v)

    def add(self, name, arcname=None, recursive=True,
            exclude=None, filter=None):
        """ Add the file the multi-volume archive,
        handle volumes transparently.

        Works like tarfile.add, be careful if you don't specify arcname.

        Don't forget to call close after all add calls.

        """
        self._init_archive()
        if not os.path.isabs(name) and arcname is None:
            arcname = name

        total_size = self._archive_size() + os.path.getsize(name)
        # Check the volume size, and create a new module if needed
        self._check_size(total_size)

        self._tar.add(name, arcname, recursive=recursive,
                      exclude=exclude, filter=None)

        # Add the file to the volume index
        self.volume_index[arcname].add(os.path.basename(self._archive.name))

    def addDir(self, dir_instance):
        """ Add the dirtools.Dir instance directory to the archive.

        Return the list of volumes, and a volume index.

        The volume index map relative filename to volume.

        """
        self._init_archive()

        for root, dirs, files in dir_instance.walk():
            cdir = os.path.relpath(root, dir_instance.path)

            for f in files:
                # We add the root if the directory is empty,
                # it won't be created automatically.
                if cdir != '.' and not cdir in self.volume_index:
                    self._tar.add(root, arcname=cdir, recursive=False)
                if cdir != '.':
                    # We also track the volume where the directory is archived.
                    volume_basename = os.path.basename(self._archive.name)
                    self.volume_index[cdir].add(volume_basename)

                absname = os.path.join(root, f)
                arcname = os.path.relpath(absname, dir_instance.parent)

                total_size = self._archive_size() + os.path.getsize(absname)
                # Check the volume size, and create a new module if needed
                self._check_size(total_size)

                # Add the file in the archive
                self._tar.add(absname, arcname=arcname)
                # Add the file to the volume index
                volume_basename = os.path.basename(self._archive.name)
                self.volume_index[arcname].add(volume_basename)

        # Close the archive
        self.close()

        return self.volumes, self.volume_index


class TarVolume(object):
    """ Helper for choosing TarVolume{Reader/Writer}. """
    @classmethod
    def open(cls, archive_dir=None, archive_key=None, mode='r',
             volume_size=DEFAULT_VOLUME_SIZE, volumes=None, volume_index=None):
        if len(mode) > 1 or mode not in 'rw':
            raise ValueError("mode must be 'r' or 'w'")
        if mode == 'r':
            return TarVolumeReader(archive_dir, archive_key,
                                   volumes, volume_index)
        else:
            return TarVolumeWriter(archive_dir, archive_key, volume_size)

bltn_open = open
open = TarVolume.open