# -*- coding: utf-8 -*-
import tarfile
import os

import librsync

from dirtools import Dir


class SigVaultWriter(object):
    def __init__(self, path, base_path):
        self.base_path = base_path
        self.archive = bltn_open(path, 'wb')
        self.tar = tarfile.open(fileobj=self.archive, mode='w:gz')

    def add(self, path=None, fileobj=None):
        if path is not None:
            fileobj = bltn_open(os.path.join(self.base_path, path), 'rb')
        sig = librsync.signature(fileobj)
        sig_size = os.fstat(sig.fileno()).st_size

        sig_info = tarfile.TarInfo(path)
        sig_info.size = sig_size
        self.tar.addfile(sig_info, sig)

    def close(self):
        self.tar.close()


class SigVaultReader(object):
    def __init__(self, base_path='.', key=None):
        self.tars = []
        _dir = Dir(base_path)
        for sv_file in _dir.files('{0}.sigvault.*.tgz'.format(key),
                                  sort_reverse=True):
            archive = bltn_open(os.path.join(_dir.path, sv_file), 'rb')
            tar = tarfile.open(fileobj=archive, mode='r:gz')
            self.tars.append(tar)

    def extract(self, path):
        for tar in self.tars:
            try:
                m = tar.getmember(path)
                return tar.extractfile(m)
            except:
                pass


class SigVault(object):
    """ Helper for choosing SigVault{Reader/Writer}. """
    @classmethod
    def open(cls, path, mode='r', base_path=None):
        if len(mode) > 1 or mode not in 'rw':
            raise ValueError("mode must be 'r' or 'w'")
        if mode == 'r':
            return SigVaultReader(path)
        else:
            return SigVaultWriter(path, base_path)

bltn_open = open
open = SigVault.open
