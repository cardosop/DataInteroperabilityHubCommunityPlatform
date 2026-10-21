from django.conf import settings


def test_admin_database_alias_exists_and_matches_default_endpoint():
    assert "admin" in settings.DATABASES
    default_db = settings.DATABASES["default"]
    admin_db = settings.DATABASES["admin"]

    assert admin_db["ENGINE"] == default_db["ENGINE"]
    assert admin_db["NAME"] == default_db["NAME"]
    assert admin_db["HOST"] == default_db["HOST"]
    assert admin_db["PORT"] == default_db["PORT"]
