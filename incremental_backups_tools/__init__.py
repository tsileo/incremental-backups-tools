# -*- coding: utf-8 -*-
import os
import tarfile
import logging
import tempfile
import shutil
from datetime import datetime
import json
import itertools

import librsync

from dirtools import Dir, DirState, compute_diff, filehash
import sigvault

logging.basicConfig(level=logging.DEBUG)

log = logging

CACHE_PATH = '/home/thomas/.cache/bakthat'


def full_backup(path, cache_path=None):
    if cache_path is None:
        cache_path = tempfile.gettempdir()

    backup_date = datetime.utcnow()
    backup_dir = Dir(path)

    backup_dir_state = DirState(backup_dir)
    state_file = backup_dir_state.to_json(cache_path, dt=backup_date, fmt='{0}.state.{1}.json')

    created_file = '{0}.full.{1}.tgz'.format(backup_dir.path.strip('/').split('/')[-1],
                                             backup_date.isoformat())
    created_file = os.path.join(cache_path, created_file)
    backup_dir.compress_to(created_file)

    # Create a new SigVault
    sigvault_file = '{0}.sigvault.{1}.tgz'.format(backup_dir.path.strip('/').split('/')[-1],
                                                  backup_date.isoformat())
    sigvault_file = os.path.join(CACHE_PATH, sigvault_file)

    sv = sigvault.open_vault(sigvault_file, 'w', base_path=backup_dir.path)

    for f in backup_dir.iterfiles():
        sv.add(f)

    sv.close()

    return {'backup_date': backup_date, 'files': [state_file, created_file, sigvault_file]}


def incremental_backup(path, cache_path=None):
    if cache_path is None:
        cache_path = tempfile.gettempdir()

    backup_date = datetime.utcnow()
    backup_dir = Dir(path)
    backup_key = backup_dir.path.strip('/').split('/')[-1]

    # TODO check if it's really the last state on the remote storage
    last_state = Dir(cache_path).get('{0}.state.*'.format(backup_key), sort_reverse=True, abspath=True)

    last_state = DirState.from_json(last_state)
    current_state = DirState(backup_dir)

    last_sv = sigvault.SigVaultReader(CACHE_PATH, backup_key)

    diff = current_state - last_state

    state_file = current_state.to_json(cache_path, dt=backup_date, fmt='{0}.state.{1}.json')

    created_file = '{0}.created.{1}.tgz'.format(backup_key,
                                                backup_date.isoformat())
    created_file = os.path.join(cache_path, created_file)
    created_file = process_created(created_file,
                                   diff['created'],
                                   backup_dir.path)

    updated_file = '{0}.updated.{1}.tgz'.format(backup_key,
                                                backup_date.isoformat())
    updated_file = os.path.join(cache_path, updated_file)
    updated_file = process_updated(updated_file,
                                   diff['updated'],
                                   backup_dir.path,
                                   last_sv)

    if diff['created'] or diff['updated']:
        sigvault_file = '{0}.sigvault.{1}.tgz'.format(backup_key,
                                                      backup_date.isoformat())

        new_sv = sigvault.open_vault(os.path.join(CACHE_PATH, sigvault_file), 'w', base_path=backup_dir.path)
        for f in itertools.chain(diff['created'], diff['updated']):
            new_sv.add(f)
        new_sv.close()

    return state_file, created_file, updated_file


def process_created(path, created, base_path):
    """ Put new file in a new archive. """
    if created:
        created_archive = tarfile.open(path, 'w:gz')
        for f in created:
            f_abs = os.path.join(base_path, f)
            created_archive.add(f_abs, arcname=f)
        created_archive.close()
        return path


def process_updated(path, updated, base_path, sigvault):
    """ Process upated files, create a new SigVault if needed,
    and create a new archives with delta (from the previous SigVault signatures).
    """
    if updated:
        updated_archive = tarfile.open(path, 'w:gz')
        for f in updated:
            f_abs = os.path.join(base_path, f)
            delta = librsync.delta(open(f_abs, 'rb'),
                                   sigvault.extract(f))

            delta_size = os.fstat(delta.fileno()).st_size

            delta_info = tarfile.TarInfo(f)
            delta_info.size = delta_size
            updated_archive.addfile(delta_info, delta)
        updated_archive.close()
        return path


def patch_diff(base_path, diff, created_archive=None, updated_archive=None):
    # First, we iterate the created files
    if diff['created']:
        for crtd in diff['created']:
            created_tar = tarfile.open(created_archive, 'r:gz')
            try:
                src_file = created_tar.extractfile(crtd)

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
                raise Exception("Diff seems corrupted.")
            finally:
                created_tar.close()

    # Next, we iterate updated files in order to patch them
    if diff['updated']:
        for updtd in diff['updated']:
            try:
                updated_tar = tarfile.open(updated_archive, 'r:gz')

                abspath = os.path.join(base_path, updtd)

                # Load the librsync delta
                delta_file = updated_tar.extractfile(updtd)

                # A tempfile file to store the patched file/result
                # before replacing the original
                patched = tempfile.NamedTemporaryFile()

                # Patch the current version of the file with the delta
                # and store the result in the previously created tempfile
                with open(abspath, 'rb') as f:
                    librsync.patch(f, delta_file, patched)

                patched.seek(0)

                # Now we replace the orignal file with the patched version
                with open(abspath, 'wb') as f:
                    shutil.copyfileobj(patched, f)

                patched.close()

            except KeyError as exc:
                # It means that a file is missing in the archive.
                log.exception(exc)
                raise Exception("Diff seems corrupted.")

            finally:
                updated_tar.close()

    # Then, we iterate the deleted files
    for dltd in diff['deleted']:
        abspath = os.path.join(base_path, dltd)
        if os.path.isfile(abspath):
            os.remove(abspath)

    # Finally, we iterate the deleted directories
    for dltd_drs in diff['deleted_dirs']:
        abspath = os.path.join(base_path, dltd_drs)
        if os.path.isdir(abspath):
            os.rmdir(abspath)


def get_full_and_incremental(key, cache_path=None):
    """ From a directory as source, iterate over states files from a full backup,
    till the end/or another full backup. The first item is actually the full backup. """
    if cache_path is None:
        cache_path = tempfile.gettempdir()

    _dir = Dir(cache_path)
    last_full = _dir.get('{0}.full.*'.format(key), sort_reverse=True, abspath=True)
    last_full_date =  '.'.join(last_full.split('.')[-3:-1])
    last_full_dt = datetime.strptime(last_full_date, '%Y-%m-%dT%H:%M:%S.%f')
    previous_state = _dir.get('{0}.state.{1}.json'.format(key, last_full_date), sort_reverse=True, abspath=True)
    yield last_full, None, last_full_dt

    for s_file in _dir.files('{0}.state.*'.format(key)):
        s_str = '.'.join(s_file.split('.')[-3:-1])
        s_dt = datetime.strptime(s_str, '%Y-%m-%dT%H:%M:%S.%f')
        if s_dt > last_full_dt and not _dir.get('{0}.full.{1}.tgz'.format(key, s_str)):
            yield s_file, previous_state, s_dt
            previous_state = s_file


def restore_backup(key, dest, cache_path=None):
    """ Restore backups given the key to dest using cache_path as source
    for state and deltas. """
    if cache_path is None:
        cache_path = tempfile.gettempdir()

    for index, (state_file, previous_state_file, state_dt) in enumerate(get_full_and_incremental(key)):
        if index == 0:
            # At index == 0, state is the full archive
            log.info('Restored full backup ({})'.format(state_dt))
            tarfile.open(state_file, 'r:gz').extractall(dest)
        else:
            with open(state_file, 'rb') as f:
                state = json.loads(f.read())
            with open(previous_state_file, 'rb') as f:
                previous_state = json.loads(f.read())
            diff = compute_diff(state, previous_state)
            _dir = Dir(cache_path)
            patch_diff(dest, diff,
                       _dir.get('{0}.created.{1}.tgz'.format(key, state_dt.isoformat())),
                       _dir.get('{0}.updated.{1}.tgz'.format(key, state_dt.isoformat())))
            log.info('Patched incremental backup ({})'.format(state_dt))

# TODO: full backup list
# TODO: gerer DT str pour restorer

#print full_backup('/work/writing')
#print incremental_backup('/home/thomas/omgtxt2')
#print restore_backup('writing', '/tmp/writing_restored')
