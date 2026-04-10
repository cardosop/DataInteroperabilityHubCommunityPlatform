# FilesAPI

`from datahub_interoperability import FilesAPI`

Handles file upload, download, listing, and deletion. Files are the raw
storage objects that back datasets in Meshant. FilesAPI supports multipart
uploads and presigned download URLs.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.files  # type: FilesAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20)` | List uploaded files | `list[File]` |
| `get(id)` | Get file metadata by UUID | `File` |
| `upload(path, content_type=None)` | Upload a local file | `File` |
| `download(id, dest_path)` | Download a file to a local path | `Path` |
| `get_download_url(id)` | Get a presigned download URL | `str` |
| `delete(id)` | Delete a file | `None` |

## Example

```python
uploaded = api.upload("/tmp/events.csv")
print(f"File ID: {uploaded.id}, size: {uploaded.size_bytes}")
api.download(uploaded.id, "/tmp/copy.csv")
```

## Error Handling

```python
from datahub_interoperability import FilesAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/files/`](../../api-reference/files.md)
- CLI: [`datahub files`](../../cli-reference/files.md)
