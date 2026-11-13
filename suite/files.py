"""Publish complete files; preserve originals until replacement is ready."""
import os
from pathlib import Path
import tempfile
import stat


def create_file(path, content):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        # A same-filesystem hard link publishes atomically and fails if the
        # destination appeared while generation was in progress.
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def replace_file(path, content, expected):
    """Stage a complete replacement and reject edits observed during staging."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Refusing nonregular replacement target: {path}')
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(content)
            output.flush()
            os.fchmod(output.fileno(), mode)
            os.fsync(output.fileno())
        if path.is_symlink() or path.read_text(encoding='utf-8') != expected:
            raise RuntimeError(f'{path.name} changed before replacement.')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
