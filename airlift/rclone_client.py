import os
import logging
import subprocess
import shutil
from datetime import datetime
from typing import Optional

from airlift.utils_exceptions import CriticalError

logger = logging.getLogger(__name__)


class rclone_client:
    """
    rclone-based file upload client.

    Drop-in replacement for dropbox_client using rclone subprocess calls.
    Supports any pre-configured rclone remote (WebDAV, S3, Dropbox, etc.).
    """

    # rclone flags for efficient single-file uploads
    UPLOAD_FLAGS = [
        '--no-traverse',
        '--retries', '3',
        '--low-level-retries', '10',
        '-q',
        '--stats', '0',
    ]

    def __init__(self, remote: str, base_url: Optional[str] = None, md: bool = False):
        """
        Initialize rclone client.

        Args:
            remote: rclone remote name (e.g., 'mywebdav', 'mydropbox')
            base_url: Fallback base URL for public file access when 'rclone link' is unsupported
            md: Use 'Marker Data' folder structure (for compatibility with --md flag)
        """
        self.remote = remote.rstrip(':')
        self.base_url = base_url

        # Validate rclone is available
        self._validate_rclone()

        # Validate remote is configured
        self._validate_remote()

        # Set up folder structure (matching dropbox_client pattern)
        if md:
            self.main_folder = "/Marker Data"
        else:
            self.main_folder = "/Airlift"

        c = datetime.now()
        self.sub_folder = f"{self.main_folder}{self.main_folder} {c.strftime('%Y-%m-%d')} {c.strftime('%H-%M-%S')}"

        # Create remote folder
        self._create_remote_folder(self.sub_folder)

        logger.info(f"Created rclone client for {self.remote}:{self.sub_folder}")

    def _validate_rclone(self) -> None:
        """Validate rclone is installed and accessible."""
        if shutil.which('rclone') is None:
            raise CriticalError(
                "rclone not found in PATH. Please install rclone: https://rclone.org/install/"
            )

        try:
            result = subprocess.run(
                ['rclone', 'version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise CriticalError(f"rclone version check failed: {result.stderr}")

            version_line = result.stdout.split('\n')[0]
            logger.debug(f"Found {version_line}")
        except subprocess.TimeoutExpired:
            raise CriticalError("rclone version check timed out")

    def _validate_remote(self) -> None:
        """Validate the rclone remote is configured."""
        try:
            result = subprocess.run(
                ['rclone', 'listremotes'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise CriticalError(f"Failed to list rclone remotes: {result.stderr}")

            remotes = [r.strip().rstrip(':') for r in result.stdout.strip().split('\n') if r.strip()]

            if self.remote not in remotes:
                available = ', '.join(remotes) if remotes else 'none'
                raise CriticalError(
                    f"rclone remote '{self.remote}' not found. "
                    f"Available remotes: {available}. "
                    f"Run 'rclone config' to set up your remote."
                )

            logger.debug(f"Validated remote '{self.remote}'")
        except subprocess.TimeoutExpired:
            raise CriticalError("rclone listremotes timed out")

    def _create_remote_folder(self, path: str) -> None:
        """Create folder on remote."""
        try:
            result = subprocess.run(
                ['rclone', 'mkdir', f'{self.remote}:{path}'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                # Folder may already exist, just log a warning
                logger.warning(f"Could not create folder (may already exist): {result.stderr.strip()}")
            else:
                logger.debug(f"Created remote folder: {self.remote}:{path}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout creating folder {path}")

    def _run_rclone(self, args: list, timeout: int = 120) -> subprocess.CompletedProcess:
        """Execute an rclone command with error handling."""
        cmd = ['rclone'] + args
        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired:
            raise CriticalError(f"rclone command timed out after {timeout}s: {' '.join(cmd)}")

    def upload_to_dropbox(self, filename: str) -> str:
        """
        Upload file to remote and return public URL.

        Method name kept as upload_to_dropbox for interface compatibility
        with dropbox_client.

        Args:
            filename: Path to local file

        Returns:
            Public URL for the uploaded file
        """
        # Validate local file exists
        if not os.path.exists(filename):
            raise CriticalError(f"File not found: {filename}")

        # Construct remote path (preserve parent directory like dropbox_client)
        file_path = os.path.split(filename)
        base_filename = file_path[1]
        last_dir = None

        if file_path[0]:
            last_dir = os.path.split(file_path[0])

        if last_dir:
            if last_dir[0] is None:
                final_path = f'{base_filename}'
            else:
                final_path = f'{last_dir[1]}/{base_filename}'
        else:
            final_path = f'{base_filename}'

        remote_path = f"{self.sub_folder}/{final_path}"
        remote_full = f"{self.remote}:{remote_path}"

        # Upload file
        self._upload_file(filename, remote_full)

        # Get public URL
        url = self._get_public_url(remote_full, remote_path)

        logger.debug(f"Uploaded {base_filename} -> {url}")
        return url

    def _upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a single file using rclone copyto."""
        result = self._run_rclone(
            ['copyto', local_path, remote_path] + self.UPLOAD_FLAGS,
            timeout=120
        )

        if result.returncode != 0:
            raise CriticalError(f"Failed to upload {local_path}: {result.stderr.strip()}")

    def _get_public_url(self, remote_full: str, remote_path: str) -> str:
        """
        Get public URL using hybrid strategy:
        1. Try rclone link command
        2. Fall back to base_url + path if link fails
        """
        # Strategy 1: Try rclone link
        result = self._run_rclone(['link', remote_full, '-q'], timeout=30)

        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            if lines:
                url = lines[-1]
                # Basic URL validation
                if url.startswith(('http://', 'https://')):
                    # Dropbox-specific URL transformation (if using Dropbox via rclone)
                    if 'dropbox.com' in url:
                        url = url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                        url = url.replace('?dl=0', '?dl=1')
                    logger.debug(f"Got URL via rclone link: {url}")
                    return url

        # Strategy 2: Fall back to base_url + path
        if self.base_url:
            fallback_url = f"{self.base_url.rstrip('/')}{remote_path}"
            logger.debug(f"Using fallback URL: {fallback_url}")
            return fallback_url

        # Neither worked
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        raise CriticalError(
            f"Cannot generate public URL for {remote_full}. "
            f"'rclone link' failed ({error_msg}) and no --rclone-base-url provided."
        )
