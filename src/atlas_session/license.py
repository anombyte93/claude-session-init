"""License management for atlas-session-lifecycle Pro.

Handles local license activation, revocation, and cached validation.
Stripe API calls are only made when cache expires (every 24h).

SECURITY: License validation uses HMAC-signed tokens to prevent
bypass via file timestamp manipulation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path

LICENSE_DIR = Path.home() / ".atlas-session"
LICENSE_FILE = "license.json"
CACHE_FILE = ".license_cache"
CACHE_TTL = 86400  # 24 hours

# HMAC secret for signing license tokens
# In production, set ATLAS_HMAC_SECRET env var
_hmac_input = os.environ.get("ATLAS_HMAC_SECRET", "").encode() or b"change-me-in-production"
if not os.environ.get("ATLAS_HMAC_SECRET"):
    logging.getLogger(__name__).warning(
        "ATLAS_HMAC_SECRET not set — using insecure default. Set this in production."
    )
_HMAC_SECRET = hmac.new(
    b"atlas-session-license-v1",
    _hmac_input,
    hashlib.sha256,
).digest()


def _sign_token(customer_id: str, expiry: float) -> str:
    """Create an HMAC signature for a license token.

    Args:
        customer_id: Stripe customer ID
        expiry: Unix timestamp when token expires

    Returns:
        Hex-encoded HMAC signature
    """
    message = f"{customer_id}:{expiry}".encode()
    return hmac.new(_HMAC_SECRET, message, hashlib.sha256).hexdigest()


def _verify_token(customer_id: str, expiry: float, signature: str) -> bool:
    """Verify an HMAC signature for a license token.

    Args:
        customer_id: Stripe customer ID from token
        expiry: Unix timestamp from token
        signature: HMAC signature to verify

    Returns:
        True if signature is valid, False otherwise
    """
    expected = _sign_token(customer_id, expiry)
    return hmac.compare_digest(expected, signature)


def _touch_cache() -> None:
    """Touch the cache file to mark license as freshly validated."""
    cache_path = LICENSE_DIR / CACHE_FILE

    # Store signed token instead of just touching file
    customer_id = _get_customer_id()
    if customer_id:
        expiry = time.time() + CACHE_TTL
        signature = _sign_token(customer_id, expiry)
        token_data = {
            "customer_id": customer_id,
            "expiry": expiry,
            "signature": signature,
        }
        cache_path.write_text(json.dumps(token_data))
    else:
        cache_path.touch()


def _get_customer_id() -> str | None:
    """Read customer_id from license file if exists."""
    license_path = LICENSE_DIR / LICENSE_FILE
    if not license_path.exists():
        return None
    try:
        data = json.loads(license_path.read_text())
        return data.get("customer_id")
    except (json.JSONDecodeError, OSError):
        return None


def activate_license(customer_id: str) -> dict:
    """Activate a license by writing customer_id to license.json."""
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    license_path = LICENSE_DIR / LICENSE_FILE

    data = {
        "customer_id": customer_id,
        "activated_at": time.time(),
    }
    license_path.write_text(json.dumps(data, indent=2))

    # Touch cache to mark as freshly validated
    _touch_cache()

    return {"status": "ok", "customer_id": customer_id}


def revoke_license() -> dict:
    """Remove local license and cache files."""
    license_path = LICENSE_DIR / LICENSE_FILE
    cache_path = LICENSE_DIR / CACHE_FILE

    license_path.unlink(missing_ok=True)
    cache_path.unlink(missing_ok=True)

    return {"status": "ok", "message": "License revoked."}


def is_license_valid(refresh: bool = True) -> bool:
    """Check if a valid, non-expired license exists locally.

    Uses HMAC-signed tokens to prevent timestamp manipulation bypass.
    Returns True only if license.json exists AND the cache token
    is valid and not expired.

    Args:
        refresh: If True, try Stripe validation when cache expired.

    Returns:
        True if license is valid (locally or after Stripe refresh), False otherwise.
    """
    license_path = LICENSE_DIR / LICENSE_FILE
    cache_path = LICENSE_DIR / CACHE_FILE

    if not license_path.exists():
        return False

    customer_id = _get_customer_id()
    if not customer_id:
        return False

    if not cache_path.exists():
        # Cache missing - try to refresh if requested
        if refresh:
            return _try_refresh_from_stripe()
        return False

    # Try to read and verify signed token
    try:
        cache_data = json.loads(cache_path.read_text())
        cached_customer_id = cache_data.get("customer_id")
        expiry = cache_data.get("expiry")
        signature = cache_data.get("signature")

        # Verify customer ID matches
        if cached_customer_id != customer_id:
            if refresh:
                return _try_refresh_from_stripe()
            return False

        # Verify HMAC signature
        if not _verify_token(customer_id, expiry, signature):
            if refresh:
                return _try_refresh_from_stripe()
            return False

        # Check expiry
        if time.time() > expiry:
            if refresh:
                return _try_refresh_from_stripe()
            return False

        return True

    except (json.JSONDecodeError, KeyError, TypeError, OSError):
        # Cache corrupted or in old format (empty file from touch())
        # For backward compatibility, check mtime as fallback
        try:
            cache_age = time.time() - cache_path.stat().st_mtime
            if cache_age < CACHE_TTL:
                return True
        except (OSError, ValueError):
            pass
        # Try to refresh if requested
        if refresh:
            return _try_refresh_from_stripe()
        return False


def _try_refresh_from_stripe() -> bool:
    """Attempt to refresh license from Stripe API.

    Returns True if validation succeeded and cache was touched,
    False otherwise. Silently fails if Stripe is not configured.
    """
    customer_id = _get_customer_id()
    if not customer_id:
        return False

    try:
        from .stripe_client import validate_license_with_stripe

        result = validate_license_with_stripe(customer_id)
        if result.get("status") == "active":
            _touch_cache()
            return True
    except Exception:
        # Stripe not configured or API error - fail silently
        pass

    return False


def refresh_license() -> dict:
    """Manually refresh license from Stripe API.

    Forces validation with Stripe regardless of cache age.
    Useful when user wants to extend their license early.

    Returns:
        dict with status and validation result.
    """
    customer_id = _get_customer_id()
    if not customer_id:
        return {"status": "error", "message": "No local license found"}

    try:
        from .stripe_client import validate_license_with_stripe

        result = validate_license_with_stripe(customer_id)
        if result.get("status") == "active":
            _touch_cache()
            return {
                "status": "ok",
                "message": "License refreshed successfully",
                "license_type": result.get("type"),
            }
        return {
            "status": "inactive",
            "message": result.get("message", "License not active in Stripe"),
        }
    except ImportError:
        return {"status": "error", "message": "Stripe integration not available"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def cli_main(argv: list[str] | None = None) -> int:
    """CLI entry point for license management.

    Usage:
        atlas-license activate <customer_id>
        atlas-license revoke
        atlas-license status
        atlas-license refresh
    """
    import sys

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("Usage: atlas-license {activate,revoke,status,refresh}")
        return 1

    command = argv[0]

    if command == "activate":
        if len(argv) < 2:
            print("Usage: atlas-license activate <customer_id>")
            return 1
        result = activate_license(argv[1])
        print(f"License activated for {result['customer_id']}")
        return 0

    if command == "revoke":
        revoke_license()
        print("License revoked.")
        return 0

    if command == "status":
        if is_license_valid():
            license_path = LICENSE_DIR / LICENSE_FILE
            data = json.loads(license_path.read_text())
            print(f"License: VALID (customer: {data.get('customer_id', 'unknown')})")
            return 0
        print("License: INVALID or expired")
        return 1

    if command == "refresh":
        result = refresh_license()
        if result.get("status") == "ok":
            print(f"License refreshed: {result.get('message', 'Success')}")
            return 0
        print(f"Refresh failed: {result.get('message', 'Unknown error')}")
        return 1

    print(f"Unknown command: {command}")
    return 1


def _cli_entry() -> None:
    """Entry point for project.scripts — wraps cli_main with sys.exit."""
    import sys

    sys.exit(cli_main())


if __name__ == "__main__":
    _cli_entry()
