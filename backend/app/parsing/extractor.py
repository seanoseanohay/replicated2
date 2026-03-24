import shutil
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.logging import get_logger

logger = get_logger(__name__)


class BundleExtractor:
    """Downloads bundle from S3 and extracts to a temp directory."""

    def __init__(self, storage_service):
        self.storage = storage_service

    @contextmanager
    def extract(self, s3_key: str) -> Iterator[Path]:
        """Context manager: yields Path to extracted bundle root, cleans up on exit."""
        tmp_dir = tempfile.mkdtemp(prefix="bundle_extract_")
        try:
            logger.info("bundle_download_start", s3_key=s3_key)
            bundle_bytes = self.storage.download_bundle(s3_key)
            logger.info(
                "bundle_download_complete", s3_key=s3_key, size=len(bundle_bytes)
            )

            # Write to a temp file for tarfile to open
            suffix = ".tar.gz" if s3_key.endswith((".tar.gz", ".tgz")) else ".tar"
            tmp_archive = tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, dir=tmp_dir
            )
            try:
                tmp_archive.write(bundle_bytes)
                tmp_archive.flush()
                tmp_archive.close()

                extract_dir = Path(tmp_dir) / "extracted"
                extract_dir.mkdir()

                mode = "r:gz" if s3_key.endswith((".tar.gz", ".tgz")) else "r:*"
                with tarfile.open(tmp_archive.name, mode) as tf:
                    tf.extractall(path=str(extract_dir))

                logger.info("bundle_extracted", extract_dir=str(extract_dir))

                # If single top-level directory, descend into it
                children = list(extract_dir.iterdir())
                if len(children) == 1 and children[0].is_dir():
                    bundle_root = children[0]
                else:
                    bundle_root = extract_dir

                yield bundle_root
            finally:
                Path(tmp_archive.name).unlink(missing_ok=True)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.info("bundle_extract_cleanup", tmp_dir=tmp_dir)
