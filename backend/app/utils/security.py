import re
import os

# Gzip magic: 1f 8b
# Zip magic: 50 4b 03 04
# tar (plain): no universal magic, but allow octet-stream
ALLOWED_MAGIC = [
    b"\x1f\x8b",           # gzip
    b"\x50\x4b\x03\x04",  # zip
    b"\x50\x4b\x05\x06",  # zip (empty)
]

def validate_magic_bytes(data: bytes) -> bool:
    """Return True if file starts with a recognized archive magic."""
    for magic in ALLOWED_MAGIC:
        if data[:len(magic)] == magic:
            return True
    return False

_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_\-. ]")

def sanitize_filename(filename: str) -> str:
    """
    Strip path components and unsafe characters.
    Returns a safe filename, max 255 chars.
    Raises ValueError if the result is empty.
    """
    # Strip directory components
    name = os.path.basename(filename)
    # Replace unsafe chars with underscore
    name = _SAFE_FILENAME_RE.sub("_", name)
    name = name.strip()
    if not name:
        raise ValueError("Filename is empty after sanitization")
    return name[:255]
