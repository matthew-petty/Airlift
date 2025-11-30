# Airlift Tests

This directory contains real API tests for Airlift that actually interact with Airtable, Dropbox, and rclone services.

## Setup

1. **Install dependencies:**
   ```bash
   poetry install
   ```

2. **Configure environment:**
   - Copy `.env.example` to `.env`
   - Fill in your real Airtable and Dropbox credentials

3. **Configure rclone (optional, for rclone tests):**
   ```bash
   rclone config
   # Create a remote named 'airlift-test-remote'
   ```

4. **Verify assets:**
   - Ensure `tests/assets/` contains the CSV and image files
   - CSV should reference the image files correctly

## Running Tests

### All tests:
```bash
pytest tests/
```

### Specific test classes:
```bash
# Test CSV processing only
pytest tests/test_upload.py::TestCSVProcessing -v

# Test Dropbox integration
pytest tests/test_upload.py::TestDropboxIntegration -v

# Test Airtable integration
pytest tests/test_upload.py::TestAirtableIntegration -v

# Test actual uploads (careful - this uploads real data!)
pytest tests/test_upload.py::TestDataUpload -v

# Test rclone client
pytest tests/test_rclone_upload.py::TestRcloneClient -v

# Test rclone uploads (requires 'airlift-test-remote' configured)
pytest tests/test_rclone_upload.py::TestRcloneUpload -v
```

### With output:
```bash
pytest tests/ -v -s
```

## Test Structure

### test_upload.py
- **TestCSVProcessing**: Tests CSV file parsing and validation
- **TestDropboxIntegration**: Tests real Dropbox file uploads
- **TestAirtableIntegration**: Tests Airtable connection and client
- **TestDataUpload**: Tests actual data upload to Airtable (with/without attachments)
- **TestErrorHandling**: Tests error scenarios with invalid data
- **TestAssetFiles**: Validates test assets are present and correct

### test_rclone_upload.py
- **TestRcloneClient**: Tests rclone client creation, validation, and error handling
- **TestRcloneUpload**: Tests file uploads via rclone and full upload workflow

## Important Notes

⚠️ **These tests make real API calls!**

- **Dropbox**: Will upload test images to your Dropbox account
- **rclone**: Will upload test images to your configured rclone remote
- **Airtable**: Will add records to your specified table
- **Costs**: May incur API usage charges
- **Data**: Will create real data in your services

## Environment Variables

Required in `.env`:
```bash
AIRTABLE_TOKEN=your_token
AIRTABLE_BASE=your_base_id
AIRTABLE_TABLE=your_table_id
DROPBOX_APP_KEY=your_dropbox_app_key
DROPBOX_REFRESH_TOKEN=your_refresh_token
```

Optional for rclone tests:
```bash
RCLONE_TEST_BASE_URL=https://your-server.com/files  # Fallback URL for rclone remotes without link support
```

Note: rclone tests also require a remote named `airlift-test-remote` configured via `rclone config`.

## Assets

The `tests/assets/` directory should contain:
- `big_cats.csv` - Test data file
- `*.jpg` files - Test images referenced in CSV

## Cleanup

After running tests, you may want to:
- Delete uploaded files from Dropbox
- Delete uploaded files from your rclone remote
- Remove test records from Airtable
- Check API usage in all services