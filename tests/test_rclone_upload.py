"""
Integration tests for rclone upload functionality.

These tests require:
1. rclone installed and in PATH
2. A remote named 'airlift-test-remote' configured via 'rclone config'
3. Airtable credentials in environment variables

Tests will be skipped if requirements are not met.
"""

import pathlib
import warnings
from dataclasses import dataclass
from pathlib import Path

import pytest

from airlift.airtable_client import new_client
from airlift.airtable_upload import Upload
from airlift.csv_data import csv_read
from airlift.rclone_client import rclone_client
from airlift.utils_exceptions import CriticalError
from airlift.version import __version__

# Suppress warnings from external libraries
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)


@dataclass
class RcloneTestArgs:
    """Args structure for rclone upload tests."""
    csv_file: str
    token: str
    base: str
    table: str
    rclone_remote: str
    rclone_base_url: str
    rclone_timeout: int
    attachment_columns: str
    workers: int
    verbose: bool
    md: bool
    disable_bypass_column_creation: bool
    fail_on_duplicate_csv_columns: bool
    rename_key_column: bool
    attachment_columns_map: bool
    columns_copy: bool
    log: bool


class TestRcloneClient:
    """Tests for rclone_client class."""

    def test_rclone_client_creation(self, rclone_test_config):
        """Test that rclone client can be created with valid remote."""
        client = rclone_client(
            remote=rclone_test_config["remote"],
            base_url=rclone_test_config["base_url"],
            md=False,
            timeout=120
        )

        assert client is not None
        assert client.remote == rclone_test_config["remote"]
        assert client.timeout == 120

    def test_rclone_client_invalid_remote(self):
        """Test that rclone client raises error for invalid remote."""
        with pytest.raises(CriticalError) as exc_info:
            rclone_client(
                remote="nonexistent-remote-12345",
                base_url=None,
                md=False
            )

        assert "not found" in str(exc_info.value).lower()

    def test_rclone_client_invalid_remote_name_chars(self):
        """Test that rclone client rejects remote names with invalid characters."""
        with pytest.raises(CriticalError) as exc_info:
            rclone_client(
                remote="remote;rm -rf /",
                base_url=None,
                md=False
            )

        assert "invalid remote name" in str(exc_info.value).lower()

    def test_rclone_client_md_flag(self, rclone_test_config):
        """Test that md flag creates correct folder structure."""
        client = rclone_client(
            remote=rclone_test_config["remote"],
            base_url=rclone_test_config["base_url"],
            md=True
        )

        assert "/Marker Data" in client.sub_folder

        client_no_md = rclone_client(
            remote=rclone_test_config["remote"],
            base_url=rclone_test_config["base_url"],
            md=False
        )

        assert "/Airlift" in client_no_md.sub_folder


class TestRcloneUpload:
    """Tests for file upload via rclone."""

    @pytest.fixture(autouse=True)
    def setup_args(self, test_config, rclone_test_config):
        """Set up test arguments."""
        self.args = RcloneTestArgs(
            csv_file="tests/assets/big_cats.csv",
            token=test_config["airtable_token"],
            base=test_config["airtable_base"],
            table=test_config["airtable_table"],
            rclone_remote=rclone_test_config["remote"],
            rclone_base_url=rclone_test_config["base_url"],
            rclone_timeout=120,
            disable_bypass_column_creation=True,
            attachment_columns="Image Filename",
            workers=5,
            verbose=True,
            md=False,
            fail_on_duplicate_csv_columns=False,
            rename_key_column=False,
            attachment_columns_map=False,
            columns_copy=False,
            log=False,
        )
        self.rclone_config = rclone_test_config

    def test_single_file_upload(self, test_image_files):
        """Test uploading a single file via rclone."""
        client = rclone_client(
            remote=self.rclone_config["remote"],
            base_url=self.rclone_config["base_url"],
            md=False
        )

        # Upload first test image
        test_file = test_image_files[0]
        url = client.upload_file(test_file)

        assert url is not None
        assert len(url) > 0
        # URL should be http/https or start with base_url if provided
        assert url.startswith(('http://', 'https://')) or (
            self.rclone_config["base_url"] and
            url.startswith(self.rclone_config["base_url"])
        )

        print(f"Uploaded {test_file} -> {url}")

    def test_upload_nonexistent_file(self):
        """Test that uploading nonexistent file raises error."""
        client = rclone_client(
            remote=self.rclone_config["remote"],
            base_url=self.rclone_config["base_url"],
            md=False
        )

        with pytest.raises(CriticalError) as exc_info:
            client.upload_file("/nonexistent/path/to/file.jpg")

        assert "not found" in str(exc_info.value).lower()

    def test_full_upload_workflow(self):
        """Test complete upload workflow with rclone (matching test_upload.py pattern)."""
        args = self.args
        print(f"Airlift version {__version__}")

        # Creating rclone client
        dbx = rclone_client(
            remote=args.rclone_remote,
            base_url=args.rclone_base_url,
            md=args.md,
            timeout=args.rclone_timeout
        )

        # Creating airtable client
        airtable_client = new_client(
            token=args.token,
            base=args.base,
            table=args.table
        )

        print(f"Validating {args.csv_file} and Airtable Schema")

        suffix = pathlib.Path(args.csv_file).suffix

        # Converting data into airtable supported format
        if "csv" in suffix:
            data = csv_read(args.csv_file, args.fail_on_duplicate_csv_columns)
        else:
            raise CriticalError("File type not supported!")

        print("Validation done!")

        if not data:
            raise CriticalError("File is empty!")

        # Validating data and creating an uploadable data
        data = airtable_client.create_uploadable_data(data=data, args=args)

        # Uploading the data
        upload_instance = Upload(
            client=airtable_client,
            new_data=data,
            dbx=dbx,
            args=args
        )
        upload_instance.upload_data()

        print("Upload completed successfully!")
        assert True
