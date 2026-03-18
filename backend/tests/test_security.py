# Test sanitize_filename and validate_magic_bytes
import pytest
from app.utils.security import sanitize_filename, validate_magic_bytes


def test_sanitize_filename_strips_path():
    result = sanitize_filename("../../etc/passwd")
    # At minimum, os.path.basename strips the path separators
    assert "/" not in result


def test_sanitize_filename_safe():
    assert sanitize_filename("my-bundle_2024.tar.gz") == "my-bundle_2024.tar.gz"


def test_sanitize_filename_empty_raises():
    with pytest.raises(ValueError):
        sanitize_filename("")


def test_sanitize_filename_unsafe_chars():
    result = sanitize_filename("bundle;rm -rf /*.tar.gz")
    assert ";" not in result
    assert "*" not in result


def test_sanitize_filename_max_length():
    long_name = "a" * 300 + ".tar.gz"
    result = sanitize_filename(long_name)
    assert len(result) <= 255


def test_validate_magic_bytes_gzip():
    gzip_header = b"\x1f\x8b" + b"\x00" * 100
    assert validate_magic_bytes(gzip_header) is True


def test_validate_magic_bytes_zip():
    zip_header = b"\x50\x4b\x03\x04" + b"\x00" * 100
    assert validate_magic_bytes(zip_header) is True


def test_validate_magic_bytes_zip_empty():
    zip_empty = b"\x50\x4b\x05\x06" + b"\x00" * 100
    assert validate_magic_bytes(zip_empty) is True


def test_validate_magic_bytes_invalid():
    assert validate_magic_bytes(b"not an archive at all") is False


def test_validate_magic_bytes_empty():
    assert validate_magic_bytes(b"") is False
