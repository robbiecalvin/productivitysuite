"""Publish complete new files without overwriting existing work."""
import os
from pathlib import Path
import tempfile


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
