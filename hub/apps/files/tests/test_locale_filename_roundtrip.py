"""
Phase 260.2.H — locale-aware filenames (Unicode NFC round-trip).

Validates ``validators.validate_filename`` (NFC + post-truncate re-compose),
``FileService.create_file`` (service-layer choke-point), optional ``FileInitSerializer``,
ORM persistence, and GET /files/{id}/ detail (presign-independent, no mocks).
"""

from __future__ import annotations

import unicodedata

import pytest
from django.test import override_settings
from rest_framework import status

from hub.apps.files.models import File
from hub.apps.files.serializers import FileInitSerializer
from hub.apps.files.services import FileService
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.files.validators import validate_filename

pytestmark = pytest.mark.django_db(transaction=True)

# Eight locale / normalization scenarios (parameterised via subTest).
_LOCALE_FILENAME_ROUNDTRIP_CASES = (
    ("chinese", "中文.csv", "中文.csv"),
    ("arabic_rtl", "مرحبا.txt", "مرحبا.txt"),
    ("japanese", "ファイル.csv", "ファイル.csv"),
    ("korean", "데이터.csv", "데이터.csv"),
    ("vietnamese", "Tiếng_Việt.txt", unicodedata.normalize("NFC", "Tiếng_Việt.txt")),
    ("devanagari", "डेटा.csv", "डेटा.csv"),
    ("nfd_to_nfc_latin", "caf\u0065\u0301.csv", "caf\u00e9.csv"),
    ("emoji_ascii_extension", "chart_\U0001f4ca.csv", "chart_\U0001f4ca.csv"),
)


def _content_type_for_name(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        return "text/csv"
    if ext == "txt":
        return "text/plain"
    return "text/csv"


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
)
class LocaleFilenameRoundtripTest(FilesAPITestBase):
    """Serializer + service + ORM + GET detail — presign-independent."""

    @pytest.mark.integration
    def test_validate_filename_normalizes_nfd_latin_to_nfc(self):
        nfd = "caf\u0065\u0301.csv"
        out = validate_filename(nfd)
        self.assertEqual(out, "caf\u00e9.csv")

    @pytest.mark.integration
    def test_service_create_file_canonicalizes_without_serializer(self):
        """Programmatic callers bypass FileInitSerializer but still get NFC + path rules."""
        nfd = "caf\u0065\u0301.csv"
        fs = FileService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        file_obj = fs.create_file(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name=nfd,
            content_type="text/csv",
            size=128,
            upload_method="browser",
            created_by_id=str(self.user.id),
        )
        self.assertEqual(file_obj.name, "caf\u00e9.csv")
        self.assertTrue(str(file_obj.storage_path).endswith("caf\u00e9.csv"))

    @pytest.mark.integration
    def test_init_serializer_service_db_and_get_detail_roundtrip(self):
        for case_id, upload_name, expected_name in _LOCALE_FILENAME_ROUNDTRIP_CASES:
            with self.subTest(case_id=case_id, upload_name=upload_name):
                ser = FileInitSerializer(
                    data={
                        "name": upload_name,
                        "content_type": _content_type_for_name(upload_name),
                        "size": 512,
                        "upload_method": "browser",
                    }
                )
                self.assertTrue(ser.is_valid(), ser.errors)
                canonical = ser.validated_data["name"]
                self.assertEqual(
                    canonical,
                    expected_name,
                    msg="Serializer pipeline must emit NFC-canonical basename",
                )

                fs = FileService(
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id),
                )
                file_obj = fs.create_file(
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id),
                    name=canonical,
                    content_type=ser.validated_data["content_type"],
                    size=512,
                    upload_method="browser",
                    created_by_id=str(self.user.id),
                )
                self.assertEqual(file_obj.name, expected_name)
                self.assertTrue(str(file_obj.storage_path).endswith(expected_name))

                row = File.objects.get(id=file_obj.id)
                self.assertEqual(row.name, expected_name)

                detail = self.client.get(f"/api/v1/files/{file_obj.id}/")
                self.assertEqual(detail.status_code, status.HTTP_200_OK, detail.data)
                self.assertEqual(detail.data["name"], expected_name)
