"""
Contract tests for scripts/archive_staging_tags.py (oss-release-remediation
W0.6, S5).

The tag-archive tool preserves the 17 ``backup-staging-*`` tag trees and
the ``backups/staging_*`` restore-point dirs in the staging MinIO BEFORE
the local deletion. These tests pin its contract with a real tmp git repo
(real ``git tag``/``git archive``), real tmp backup dirs, and real
tar/gzip — no mocks or stubs:

- tag discovery resolves through real git; tags pointing at ONE commit
  share ONE tree archive (content-dedup — all 17 real tags resolve to a
  single commit, hash-proven);
- the manifest carries one row per tag NAME (mapping to the shared
  archive) and one row per backup dir, each with sha256 + size + ETag +
  verified/deleted flags — and NEVER the bucket name or any credential
  (the W0.9 redaction contract: bucket names stay out of committed
  docs);
- ``delete`` refuses without --confirm, refuses on an unverified or
  incomplete manifest, and only then deletes the tags + dirs and flips
  the rows;
- the live MinIO roundtrip is env-gated (MINIO_ARCHIVE_TEST_ENDPOINT)
  via the W16 policy — the real upload+verify runs during the window
  execution, not here.
"""

import importlib.util
import subprocess
import sys
import tarfile
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

spec = importlib.util.spec_from_file_location(
    "archive_staging_tags", scripts_dir / "archive_staging_tags.py"
)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def _init_repo(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "file.txt").write_text("staging snapshot\n")
    subprocess.run(["git", "-C", str(path), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "snapshot"], check=True)
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class TestTagDiscovery:
    def test_discovers_backup_staging_tags_only(self, tmp_path):
        repo = tmp_path / "repo"
        commit = _init_repo(repo)
        subprocess.run(
            ["git", "-C", str(repo), "tag", "backup-staging-20251207_194944", commit],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "tag", "backup-staging-20251208_093914", commit],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "tag", "v1.0.0", commit], check=True)

        tags = archive.discover_tags(repo)
        assert tags == ["backup-staging-20251207_194944", "backup-staging-20251208_093914"]

    def test_tag_commit_resolves(self, tmp_path):
        repo = tmp_path / "repo"
        commit = _init_repo(repo)
        subprocess.run(
            ["git", "-C", str(repo), "tag", "backup-staging-20251207_194944", commit], check=True
        )
        assert archive.tag_commit(repo, "backup-staging-20251207_194944") == commit


class TestArchiveDedup:
    def test_tags_on_one_commit_share_one_tree_archive(self, tmp_path):
        repo = tmp_path / "repo"
        commit = _init_repo(repo)
        for name in ("backup-staging-20251207_194944", "backup-staging-20251208_093914"):
            subprocess.run(["git", "-C", str(repo), "tag", name, commit], check=True)
        dest = tmp_path / "archives"
        dest.mkdir()

        result = archive.make_tag_tree_archives(repo, archive.discover_tags(repo), dest)
        # One distinct commit -> one archive, shared by both tag names.
        assert len(result) == 1
        (_key, path, sha256sum, size) = result[0]
        assert path.is_file()
        assert len(sha256sum) == 64
        assert size > 0
        with tarfile.open(path) as tf:
            assert "file.txt" in tf.getnames()

    def test_distinct_commits_produce_distinct_archives(self, tmp_path):
        repo = tmp_path / "repo"
        first = _init_repo(repo)
        (repo / "second.txt").write_text("second\n")
        subprocess.run(["git", "-C", str(repo), "add", "second.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "second"], check=True)
        subprocess.run(["git", "-C", str(repo), "tag", "backup-staging-a", first], check=True)
        subprocess.run(["git", "-C", str(repo), "tag", "backup-staging-b", "HEAD"], check=True)
        dest = tmp_path / "archives"
        dest.mkdir()

        result = archive.make_tag_tree_archives(repo, archive.discover_tags(repo), dest)
        assert len(result) == 2


class TestManifest:
    def test_rows_carry_flags_and_never_the_bucket_or_creds(self, tmp_path):
        manifest = archive.build_manifest(
            destination="bucket-name-length-17",
            tag_rows=[("backup-staging-a", "c0ffee", "key-a", "h" * 64, 123, "etag-a")],
            backup_rows=[("staging_20251207_194944", "key-b", "i" * 64, 456, "etag-b")],
            deleted=False,
        )
        assert "backup-staging-a" in manifest
        assert "c0ffee" in manifest
        assert "verified: yes" in manifest
        assert "deleted: no" in manifest
        assert "sha256 " + "h" * 64 in manifest
        # W0.9 redaction: the destination bucket name and credential
        # material must never enter the committed manifest.
        assert "bucket-name-length-17" not in manifest
        assert "MINIO_ROOT" not in manifest


class TestDeleteGating:
    def _setup(self, tmp_path):
        repo = tmp_path / "repo"
        commit = _init_repo(repo)
        subprocess.run(
            ["git", "-C", str(repo), "tag", "backup-staging-20251207_194944", commit], check=True
        )
        backup_dir = tmp_path / "backups" / "staging_20251207_194944"
        backup_dir.mkdir(parents=True)
        (backup_dir / "config_20251207_194944.tar.gz").write_bytes(b"creds")
        manifest = tmp_path / "manifest.md"
        manifest.write_text(
            "# manifest\n"
            "## Tag trees\n\n"
            "- backup-staging-20251207_194944 — commit c0ffee — key k — "
            "sha256 " + "a" * 64 + " — size 1 — ETag e — verified: yes — "
            "deleted: no\n\n"
            "## Backup directories\n\n"
            "- staging_20251207_194944 — key k2 — sha256 " + "b" * 64 + " — "
            "size 1 — ETag e — verified: yes — deleted: no\n"
        )
        return repo, backup_dir, manifest

    def test_refuses_without_confirm(self, tmp_path, capsys):
        repo, backup_dir, manifest = self._setup(tmp_path)
        rc = archive.run_delete(repo, tmp_path / "backups", manifest, confirm=False)
        assert rc == 1
        assert archive.discover_tags(repo)  # tags untouched
        assert backup_dir.is_dir()
        assert "confirm" in capsys.readouterr().out.lower()

    def test_refuses_on_unverified_row(self, tmp_path, capsys):
        repo, backup_dir, manifest = self._setup(tmp_path)
        manifest.write_text(manifest.read_text().replace("verified: yes", "verified: no"))
        rc = archive.run_delete(repo, tmp_path / "backups", manifest, confirm=True)
        assert rc == 1
        assert backup_dir.is_dir()
        assert "verified" in capsys.readouterr().out.lower()

    def test_deletes_tags_and_dirs_and_flips_rows(self, tmp_path):
        repo, backup_dir, manifest = self._setup(tmp_path)
        rc = archive.run_delete(repo, tmp_path / "backups", manifest, confirm=True)
        assert rc == 0
        assert archive.discover_tags(repo) == []
        assert not backup_dir.exists()
        text = manifest.read_text()
        assert "deleted: yes" in text
        assert "deleted: no" not in text


class TestLiveMinioRoundtrip:
    def test_upload_and_verify_against_a_real_minio(self, tmp_path):
        # W16 env-gated: the staging MinIO runs only during the window
        # execution; CI raises instead of skipping (environment failure
        # policy — see envpolicy.py).
        import os

        from envpolicy import skip_or_fail

        endpoint = os.environ.get("MINIO_ARCHIVE_TEST_ENDPOINT")
        if not endpoint:
            skip_or_fail(
                "MINIO_ARCHIVE_TEST_ENDPOINT not set (the staging MinIO "
                "runs only during the W0.6 window execution)"
            )
        if not os.environ.get("MINIO_ARCHIVE_TEST_USER") or not os.environ.get(
            "MINIO_ARCHIVE_TEST_PASSWORD"
        ):
            skip_or_fail("MINIO_ARCHIVE_TEST_USER/PASSWORD not set for the live roundtrip")
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ["MINIO_ARCHIVE_TEST_USER"],
            aws_secret_access_key=os.environ["MINIO_ARCHIVE_TEST_PASSWORD"],
            region_name="us-east-1",
        )
        bucket = os.environ.get("MINIO_ARCHIVE_TEST_BUCKET", "hub-staging")
        client.create_bucket(Bucket=bucket)
        key = "w06-s5-archive-probe/roundtrip.bin"
        payload = b"w06-roundtrip-probe"
        path = tmp_path / "probe.bin"
        path.write_bytes(payload)

        etag, ok = archive.upload_and_verify(client, bucket, key, path)
        assert ok
        assert etag
        head = client.head_object(Bucket=bucket, Key=key)
        assert head["ContentLength"] == len(payload)
        client.delete_object(Bucket=bucket, Key=key)
