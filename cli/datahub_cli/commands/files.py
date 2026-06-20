"""
File management commands.
"""

import json
import os

import click
import requests

from ..api_client import api_client


@click.group()
def files():
    """File management commands"""


@files.command("list")
@click.option("--status", help="Filter by status (PENDING, UPLOADED, ARCHIVED)")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_files(status: str | None, limit: int, offset: int, output_format: str):
    """List files"""
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    try:
        # API endpoint: /api/v1/files/ (files/ from api/urls.py, router registered at "")
        data = api_client.get("files/", params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No files found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Name':<40} {'Size':<15} {'Status':<15}")
            click.echo("-" * 110)
            for file_obj in results:
                size = file_obj.get("size", 0)
                size_str = f"{size / 1024 / 1024:.2f} MB" if size > 0 else "0 B"
                click.echo(
                    f"{file_obj.get('id', '')[:36]:<40} "
                    f"{file_obj.get('name', '')[:38]:<40} "
                    f"{size_str:<15} "
                    f"{file_obj.get('status', ''):<15}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list files: {e}")


@files.command("upload")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--name", help="Custom file name (defaults to original filename)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def upload_file(file_path: str, name: str | None, output_format: str):
    """Upload a file"""
    # Get file info
    file_size = os.path.getsize(file_path)
    file_name = name or os.path.basename(file_path)

    # Determine content type
    import mimetypes

    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    # Initialize upload
    try:
        # API endpoint: /api/v1/files/init/ (files/ from api/urls.py, router registered at "")
        # upload_method='sdk' generates a presigned POST URL with form fields.
        init_data = api_client.post(
            "files/init/",
            json_data={
                "name": file_name,
                "content_type": content_type,
                "size": file_size,
                "upload_method": "sdk",
            },
        )

        file_id = init_data.get("file_id")
        upload_url = init_data.get("upload_url")
        fields = init_data.get("fields", {})

        if not upload_url:
            raise click.ClickException("No upload URL received from server")

        # Upload file to S3
        click.echo(f"Uploading {file_name} ({file_size} bytes)...")
        with open(file_path, "rb") as f:
            if fields:
                # Presigned POST — send as multipart form with fields
                upload_response = requests.post(
                    upload_url,
                    data=fields,
                    files={"file": (file_name, f, content_type)},
                )
            else:
                # Presigned PUT — send raw bytes
                upload_response = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": content_type},
                )
            upload_response.raise_for_status()

        # Compute SHA-256 of uploaded content (required by complete endpoint)
        import hashlib

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        content_sha256 = sha256.hexdigest()

        # Complete upload
        # API endpoint: /api/v1/files/{id}/complete/
        complete_data = api_client.post(
            f"files/{file_id}/complete/",
            json_data={"content_sha256": content_sha256},
        )

        if output_format == "json":
            click.echo(json.dumps(complete_data, indent=2))
        else:
            click.echo("File uploaded successfully!")
            click.echo(f"ID: {complete_data.get('id')}")
            click.echo(f"Name: {complete_data.get('name')}")
            click.echo(f"Size: {complete_data.get('size')} bytes")
            click.echo(f"Status: {complete_data.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to upload file: {e}")


@files.command("download")
@click.argument("file_id")
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    help="Output file path (defaults to original filename)",
)
def download_file(file_id: str, output_path: str | None):
    """Download a file"""
    try:
        # Get file info
        # API endpoint structure: /api/v1/files/{id}/ (files/ from api/urls.py + files from router)
        file_data = api_client.get(f"files/{file_id}/")
        file_name = file_data.get("name", "download")

        # Get download URL
        # API endpoint: /api/v1/files/{id}/download/
        download_data = api_client.post(f"files/{file_id}/download/")
        download_url = download_data.get("download_url")

        if not download_url:
            raise click.ClickException("No download URL received from server")

        # Determine output path
        if not output_path:
            output_path = file_name

        # Download file
        click.echo(f"Downloading {file_name}...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        click.echo(f"File downloaded to {output_path}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to download file: {e}")


@files.command("delete")
@click.argument("file_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete_file(file_id: str, confirm: bool):
    """Delete a file"""
    if not confirm and not click.confirm(f"Are you sure you want to delete file {file_id}?"):
        click.echo("Cancelled.")
        return

    try:
        # API endpoint structure: /api/v1/files/{id}/ (files/ from api/urls.py + files from router)
        api_client.delete(f"files/{file_id}/")
        click.echo(f"File {file_id} deleted successfully!")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to delete file: {e}")
