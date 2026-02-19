"""Tests for license validation and CLI."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch


from atlas_session.license import (
    activate_license,
    is_license_valid,
    revoke_license,
)


class TestLicenseActivation:
    """Tests for license activation flow."""

    def test_activate_writes_license_file(self, tmp_path):
        """Activating with a valid key writes license.json."""
        with patch.object(Path, "__new__", return_value=tmp_path):
            pass  # We'll use monkeypatch instead

    def test_activate_creates_license_dir(self, tmp_path, monkeypatch):
        """activate_license creates ~/.atlas-session/ if missing."""
        license_dir = tmp_path / ".atlas-session"
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        activate_license("test-customer-123")

        assert license_dir.exists()
        license_file = license_dir / "license.json"
        assert license_file.exists()
        data = json.loads(license_file.read_text())
        assert data["customer_id"] == "test-customer-123"
        assert "activated_at" in data

    def test_activate_overwrites_existing(self, tmp_path, monkeypatch):
        """Activating again overwrites the previous license."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        activate_license("old-customer")
        activate_license("new-customer")

        data = json.loads((license_dir / "license.json").read_text())
        assert data["customer_id"] == "new-customer"


class TestLicenseRevocation:
    """Tests for license revocation."""

    def test_revoke_removes_license_file(self, tmp_path, monkeypatch):
        """revoke_license removes license.json."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        license_file = license_dir / "license.json"
        license_file.write_text('{"customer_id": "test"}')
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        revoke_license()

        assert not license_file.exists()

    def test_revoke_removes_cache_too(self, tmp_path, monkeypatch):
        """revoke_license also removes the validation cache."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        (license_dir / "license.json").write_text('{"customer_id": "test"}')
        (license_dir / ".license_cache").touch()
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        revoke_license()

        assert not (license_dir / ".license_cache").exists()

    def test_revoke_noop_when_no_license(self, tmp_path, monkeypatch):
        """revoke_license does not crash if no license exists."""
        license_dir = tmp_path / ".atlas-session"
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        revoke_license()  # Should not raise


class TestLicenseValidation:
    """Tests for is_license_valid."""

    def test_valid_when_license_and_cache_fresh(self, tmp_path, monkeypatch):
        """Returns True when license exists and cache is fresh."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        (license_dir / "license.json").write_text(
            json.dumps({"customer_id": "test", "activated_at": time.time()})
        )
        cache = license_dir / ".license_cache"
        cache.touch()
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        assert is_license_valid() is True

    def test_invalid_when_no_license(self, tmp_path, monkeypatch):
        """Returns False when no license.json exists."""
        license_dir = tmp_path / ".atlas-session"
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        assert is_license_valid() is False

    def test_invalid_when_cache_expired(self, tmp_path, monkeypatch):
        """Returns False when cache is older than 24 hours."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        (license_dir / "license.json").write_text(
            json.dumps({"customer_id": "test", "activated_at": time.time()})
        )
        cache = license_dir / ".license_cache"
        cache.touch()
        # Age the cache beyond 24h
        import os

        old_time = time.time() - 86401
        os.utime(cache, (old_time, old_time))
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        assert is_license_valid() is False

    def test_valid_when_no_cache_but_license_exists(self, tmp_path, monkeypatch):
        """Returns False when license exists but no cache (needs re-validation)."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        (license_dir / "license.json").write_text(
            json.dumps({"customer_id": "test", "activated_at": time.time()})
        )
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        # No cache file = needs validation = returns False
        assert is_license_valid() is False


class TestLicenseCLI:
    """Tests for the atlas-license CLI entry point."""

    def test_cli_activate(self, tmp_path, monkeypatch):
        """atlas-license activate <customer_id> writes license file."""
        license_dir = tmp_path / ".atlas-session"
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        from atlas_session.license import cli_main

        exit_code = cli_main(["activate", "cus_test123"])
        assert exit_code == 0
        assert (license_dir / "license.json").exists()
        data = json.loads((license_dir / "license.json").read_text())
        assert data["customer_id"] == "cus_test123"

    def test_cli_revoke(self, tmp_path, monkeypatch):
        """atlas-license revoke removes license."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        (license_dir / "license.json").write_text('{"customer_id": "x"}')
        (license_dir / ".license_cache").touch()
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        from atlas_session.license import cli_main

        exit_code = cli_main(["revoke"])
        assert exit_code == 0
        assert not (license_dir / "license.json").exists()

    def test_cli_status_valid(self, tmp_path, monkeypatch):
        """atlas-license status shows valid when license is fresh."""
        license_dir = tmp_path / ".atlas-session"
        license_dir.mkdir()
        (license_dir / "license.json").write_text(
            json.dumps({"customer_id": "cus_xyz", "activated_at": time.time()})
        )
        (license_dir / ".license_cache").touch()
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        from atlas_session.license import cli_main

        exit_code = cli_main(["status"])
        assert exit_code == 0

    def test_cli_status_invalid(self, tmp_path, monkeypatch):
        """atlas-license status returns 1 when no license."""
        license_dir = tmp_path / ".atlas-session"
        monkeypatch.setattr("atlas_session.license.LICENSE_DIR", license_dir)

        from atlas_session.license import cli_main

        exit_code = cli_main(["status"])
        assert exit_code == 1

    def test_cli_no_args(self):
        """atlas-license with no args returns 1."""
        from atlas_session.license import cli_main

        exit_code = cli_main([])
        assert exit_code == 1

    def test_cli_activate_missing_customer_id(self):
        """atlas-license activate without customer_id returns 1."""
        from atlas_session.license import cli_main

        exit_code = cli_main(["activate"])
        assert exit_code == 1
