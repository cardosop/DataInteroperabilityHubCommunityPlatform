#!/usr/bin/env python3
"""
oss-release-remediation W0.6 / S5 — staging restore-point archival to the
staging MinIO BEFORE local deletion.

The 17 ``backup-staging-*`` tags and the ``backups/staging_*`` dirs are
staging restore points whose content carries the credential-bearing
``.env.staging`` snapshot and config tarballs. The W0.4 history rewrite
drops them from git — S5 requires the S3 archive to land first, so this
tool archives them into the staging MinIO (the same destination the
``staging-backup`` machinery mirrors to), verifies every object, writes
the manifest, and only then deletes the local copies.

Subcommands:

    archive  — discover the tags + backup dirs, build one tarball per
               distinct tag-tree commit (the 17 tags all resolve to ONE
               commit, hash-proven — content is archived once, every tag
               name maps to it) and one tarball per backup dir, upload
               under ``w06-s5-archive/<name>/``, verify with head_object,
               write the manifest (docs/audits/tag-archive-manifest-…md).
    verify   — re-check every manifest row against the MinIO objects.
    delete   — DESTRUCTIVE: refuses unless ``--confirm`` is given AND
               every manifest row is ``verified: yes``; then deletes the
               local tags (``git tag -d``) and the backup dirs, and flips
               the rows to ``deleted: yes``.

Safety: never prints credentials or the bucket name (the W0.9 redaction
contract — bucket names stay out of committed docs); creds are read from
the env file passed with ``--env-file`` (default .env.staging).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_TAG_PREFIX = "backup-staging-"
_ARCHIVE_PREFIX = "w06-s5-archive"
_DEFAULT_ENV_FILE = _ROOT / ".env.staging"
_DEFAULT_MANIFEST = _ROOT / "docs" / "audits" / "tag-archive-manifest-2026-10-06.md"
_DEFAULT_MINIO_ENDPOINT = "http://localhost:9012"

_ROW = re.compile(
    r"^- (?P<name>\S+) — (?:commit \S+ — )?key (?P<key>\S+) — "
    r"sha256 (?P<sha>[0-9a-f]{64}) — size (?P<size>\d+) — ETag (?P<etag>\S+) — "
    r"verified: (?P<verified>\w+) — deleted: (?P<deleted>\w+)$"
)


def _shasum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_tags(repo: Path) -> list[str]:
    """The local backup-staging-* tags (sorted; real git)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "tag", "-l", f"{_TAG_PREFIX}*"],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(tag for tag in result.stdout.splitlines() if tag)


def tag_commit(repo: Path, tag: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", tag],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def discover_backup_dirs(backups_root: Path) -> list[Path]:
    """The backups/staging_* restore-point dirs (sorted by name)."""
    if not backups_root.is_dir():
        return []
    return sorted(path for path in backups_root.glob("staging_*") if path.is_dir())


def make_tag_tree_archives(
    repo: Path, tags: list[str], dest: Path
) -> list[tuple[str, Path, str, int]]:
    """One tarball per DISTINCT tag-tree commit (content-dedup).

    Returns (key, path, sha256, size) per distinct commit — the caller
    maps each tag NAME to its commit's archive.
    """
    dest.mkdir(parents=True, exist_ok=True)
    archives: dict[str, tuple[str, Path, str, int]] = {}
    for tag in tags:
        commit = tag_commit(repo, tag)
        if commit in archives:
            continue
        key = f"{_ARCHIVE_PREFIX}/tag-tree-{commit}.tar.gz"
        path = dest / f"tag-tree-{commit}.tar.gz"
        with path.open("wb") as out, gzip.GzipFile(
            filename="", mode="wb", fileobj=out, compresslevel=9, mtime=0
        ) as gz:
            subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar", commit],
                stdout=gz,
                check=True,
            )
        archives[commit] = (key, path, _shasum(path), path.stat().st_size)
    return list(archives.values())


def make_backup_dir_archives(
    backup_dirs: list[Path], dest: Path
) -> list[tuple[str, Path, str, int]]:
    """One tarball per backups/staging_* dir."""
    dest.mkdir(parents=True, exist_ok=True)
    archives = []
    for directory in backup_dirs:
        key = f"{_ARCHIVE_PREFIX}/{directory.name}/backup-dir.tar.gz"
        path = dest / f"{directory.name}.tar.gz"
        with tarfile.open(path, "w:gz") as tf:
            tf.add(directory, arcname=directory.name)
        archives.append((key, path, _shasum(path), path.stat().st_size))
    return archives


def upload_and_verify(client, bucket: str, key: str, path: Path) -> tuple[str | None, bool]:
    """put_object then head_object size check; (etag, ok)."""
    client.upload_file(str(path), bucket, key)
    head = client.head_object(Bucket=bucket, Key=key)
    etag = head.get("ETag", "").strip('"')
    return etag, head["ContentLength"] == path.stat().st_size


def build_manifest(
    destination: str,
    tag_rows: list[tuple[str, str, str, str, int, str]],
    backup_rows: list[tuple[str, str, str, int, str]],
    deleted: bool,
) -> str:
    """Render the manifest. ``destination`` is used only as a LENGTH
    (the W0.9 redaction contract — bucket names stay out of docs)."""
    deleted_flag = "yes" if deleted else "no"
    lines = [
        "# Tag Archive Manifest — 2026-10-06 (W0.6 / S5)",
        "",
        "The 17 ``backup-staging-*`` tag trees and the ``backups/staging_*``",
        "restore-point dirs, archived to the staging MinIO BEFORE local",
        "deletion. Contract-enforced by GATE-52",
        "(`scripts/check_tag_archive_manifest.py`).",
        "",
        "## Archive destination",
        "",
        f"- the staging MinIO bucket from ``.env.staging`` (name length "
        f"{len(destination)} — redacted per the W0.9 contract)",
        f"- prefix: ``{_ARCHIVE_PREFIX}/``",
        "",
        "## Tag trees",
        "",
    ]
    for name, commit, key, sha, size, etag in tag_rows:
        lines.append(
            f"- {name} — commit {commit} — key {key} — sha256 {sha} — "
            f"size {size} — ETag {etag} — verified: yes — deleted: {deleted_flag}"
        )
    lines += ["", "## Backup directories", ""]
    for name, key, sha, size, etag in backup_rows:
        lines.append(
            f"- {name} — key {key} — sha256 {sha} — size {size} — "
            f"ETag {etag} — verified: yes — deleted: {deleted_flag}"
        )
    return "\n".join(lines) + "\n"


def _parse_rows(manifest: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    tag_rows, backup_rows = [], []
    section = None
    for line in manifest.read_text().splitlines():
        if line.startswith("## Tag trees"):
            section = "tags"
            continue
        if line.startswith("## Backup directories"):
            section = "backups"
            continue
        if not line.startswith("- "):
            continue
        match = _ROW.match(line)
        if not match:
            continue
        row = match.groupdict()
        if section == "tags":
            tag_rows.append(row)
        elif section == "backups":
            backup_rows.append(row)
    return tag_rows, backup_rows


def run_delete(repo: Path, backups_root: Path, manifest: Path, confirm: bool = False) -> int:
    """Delete the local tags + backup dirs, gated on the verified manifest."""
    if not confirm:
        print("archive-staging-tags: refusing — pass --confirm to delete")
        return 1
    tag_rows, backup_rows = _parse_rows(manifest)
    if not tag_rows and not backup_rows:
        print("archive-staging-tags: refusing — the manifest has no rows")
        return 1
    unverified = [row["name"] for row in tag_rows + backup_rows if row.get("verified") != "yes"]
    if unverified:
        print(f"archive-staging-tags: refusing — unverified manifest rows: {', '.join(unverified)}")
        return 1

    local_tags = set(discover_tags(repo))
    missing = [row["name"] for row in tag_rows if row["name"] not in local_tags]
    if missing:
        print(
            "archive-staging-tags: refusing — manifest tags not present "
            f"locally: {', '.join(missing)}"
        )
        return 1

    for row in tag_rows:
        subprocess.run(
            ["git", "-C", str(repo), "tag", "-d", row["name"]],
            check=True,
        )
        print(f"deleted tag {row['name']}")
    for row in backup_rows:
        directory = backups_root / row["name"]
        if directory.exists():
            shutil.rmtree(directory)
            print(f"deleted backup dir {directory}")
        else:
            print(f"note: backup dir {directory} already absent")

    text = manifest.read_text().replace("deleted: no", "deleted: yes")
    manifest.write_text(text)
    return 0


def _env_values(env_file: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not env_file.is_file():
        return parsed
    for raw_line in env_file.read_text().splitlines():
        if "=" not in raw_line or raw_line.startswith("#"):
            continue
        key, value = raw_line.split("=", 1)
        parsed[key.strip()] = value
    return parsed


def _client(env_values: dict[str, str], endpoint: str):
    import boto3

    user = os.environ.get("MINIO_ROOT_USER", env_values.get("MINIO_ROOT_USER", ""))
    password = os.environ.get("MINIO_ROOT_PASSWORD", env_values.get("MINIO_ROOT_PASSWORD", ""))
    if not user or not password:
        raise SystemExit(
            "archive-staging-tags: MINIO_ROOT_USER/PASSWORD not set "
            "(source .env.staging or pass --env-file)"
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=user,
        aws_secret_access_key=password,
        region_name="us-east-1",
    )


def _bucket(env_values: dict[str, str]) -> str:
    bucket = os.environ.get(
        "AWS_STORAGE_BUCKET_NAME", env_values.get("AWS_STORAGE_BUCKET_NAME", "")
    )
    if not bucket:
        raise SystemExit(
            "archive-staging-tags: AWS_STORAGE_BUCKET_NAME not set "
            "(source .env.staging or pass --env-file)"
        )
    return bucket


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subcommand", choices=("archive", "verify", "delete"))
    parser.add_argument("--repo", type=Path, default=_ROOT)
    parser.add_argument("--backups-dir", type=Path, default=_ROOT / "backups")
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--minio-endpoint", default=_DEFAULT_MINIO_ENDPOINT)
    parser.add_argument("--env-file", type=Path, default=_DEFAULT_ENV_FILE)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)

    if args.subcommand == "delete":
        return run_delete(args.repo, args.backups_dir, args.manifest, args.confirm)

    env_values = _env_values(args.env_file)
    client = _client(env_values, args.minio_endpoint)
    bucket = _bucket(env_values)

    if args.subcommand == "verify":
        tag_rows, backup_rows = _parse_rows(args.manifest)
        failed = False
        for row in tag_rows + backup_rows:
            try:
                head = client.head_object(Bucket=bucket, Key=row["key"])
            except Exception as exc:  # noqa: BLE001 — probe; no creds printed
                print(f"verify {row['name']}: FAIL ({type(exc).__name__})")
                failed = True
                continue
            ok = head["ContentLength"] == int(row["size"])
            print(f"verify {row['name']}: {'PASS' if ok else 'FAIL (size mismatch)'}")
            failed = failed or not ok
        return 1 if failed else 0

    # archive
    tags = discover_tags(args.repo)
    backup_dirs = discover_backup_dirs(args.backups_dir)
    if not tags and not backup_dirs:
        print("archive-staging-tags: nothing to archive")
        return 1

    with tempfile.TemporaryDirectory(prefix="w06-archive-") as tmp:
        dest = Path(tmp)
        tag_archives = make_tag_tree_archives(args.repo, tags, dest)
        backup_archives = make_backup_dir_archives(backup_dirs, dest)

        tag_rows: list[tuple[str, str, str, str, int, str]] = []
        for tag in tags:
            commit = tag_commit(args.repo, tag)
            matching = [
                (key, path, sha, size)
                for key, path, sha, size in tag_archives
                if key.endswith(f"{commit}.tar.gz")
            ]
            key, path, sha, size = matching[0]
            etag, ok = upload_and_verify(client, bucket, key, path)
            if not ok:
                print(f"archive {tag}: upload verify FAILED")
                return 1
            tag_rows.append((tag, commit, key, sha, size, etag or ""))
            print(f"archived {tag} -> {key}")

        backup_rows: list[tuple[str, str, str, int, str]] = []
        for (key, path, sha, size), directory in zip(backup_archives, backup_dirs, strict=True):
            etag, ok = upload_and_verify(client, bucket, key, path)
            if not ok:
                print(f"archive {directory.name}: upload verify FAILED")
                return 1
            backup_rows.append((directory.name, key, sha, size, etag or ""))
            print(f"archived {directory.name} -> {key}")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(build_manifest(bucket, tag_rows, backup_rows, deleted=False))
    print(f"manifest written: {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
