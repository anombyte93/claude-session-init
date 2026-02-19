"""Stripe integration for atlas-session-lifecycle Pro.

Handles checkout session creation, webhook verification, and license
validation via Stripe API.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

# Stripe will be imported only when needed (lazy import)
_STRIPE_IMPORTED = False
stripe = None  # type: ignore[assignment]

# License directory (shared with license.py)
LICENSE_DIR = Path.home() / ".atlas-session"
LICENSE_FILE = "license.json"
CACHE_FILE = ".license_cache"
CACHE_TTL = 86400  # 24 hours


class StripeNotConfigured(RuntimeError):
    """Raised when Stripe API keys are not configured."""

    pass


class StripeSignatureError(RuntimeError):
    """Raised when webhook signature verification fails."""

    pass


def _get_price_id(mode: str) -> str:
    """Get price ID from environment for given mode."""
    if mode == "payment":
        return os.getenv("STRIPE_PRICE_YEARLY_ID", "")
    return os.getenv("STRIPE_PRICE_MONTHLY_ID", "")


def _ensure_stripe() -> None:
    """Lazily import stripe only when needed.

    Raises StripeNotConfigured if STRIPE_SECRET_KEY is not set.
    """
    global stripe, _STRIPE_IMPORTED

    if _STRIPE_IMPORTED:
        if stripe is None:
            raise StripeNotConfigured("STRIPE_SECRET_KEY not configured")
        return

    api_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not api_key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY not configured")

    try:
        import stripe as stripe_lib

        stripe = stripe_lib
        stripe.api_key = api_key
        _STRIPE_IMPORTED = True
    except ImportError:
        raise StripeNotConfigured("stripe library not installed. Add to dependencies.")


def create_checkout_session(
    customer_email: str,
    success_url: str,
    cancel_url: str,
    mode: str = "subscription",
) -> dict:
    """Create a Stripe Checkout session for license purchase.

    Args:
        customer_email: Email for the customer (pre-fills checkout)
        success_url: URL to redirect after success
        cancel_url: URL to redirect if cancelled
        mode: "subscription" or "payment"

    Returns:
        dict with checkout_url and session_id

    Raises:
        StripeNotConfigured: If Stripe keys not configured
        stripe.error.StripeError: For API errors
    """
    _ensure_stripe()

    price_id = _get_price_id(mode)

    if not price_id:
        raise StripeNotConfigured(f"STRIPE_PRICE_{'YEARLY' if mode == 'payment' else 'MONTHLY'}_ID not configured")

    try:
        session = stripe.checkout.Session.create(
            customer_email=customer_email,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                },
            ],
            mode=mode,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "product": "atlas-session-lifecycle",
                "license_type": "yearly" if mode == "payment" else "monthly",
            },
        )
        return {
            "status": "ok",
            "checkout_url": session.url,
            "session_id": session.id,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


def verify_webhook_signature(payload: bytes, signature: str) -> dict:
    """Verify a Stripe webhook signature.

    Args:
        payload: Raw request body as bytes
        signature: Value from Stripe-Signature header

    Returns:
        dict with status and event data if valid

    Raises:
        StripeSignatureError: If signature is invalid
    """
    _ensure_stripe()

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise StripeSignatureError("STRIPE_WEBHOOK_SECRET not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret,
        )
        return {
            "status": "ok",
            "event_type": event.type,
            "data": event.data,
        }
    except stripe.error.SignatureVerificationError as e:
        raise StripeSignatureError(f"Invalid signature: {e}")
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


def handle_checkout_completed(event_data: dict) -> dict:
    """Handle checkout.session.completed event.

    Extracts customer_id and activates local license.

    Args:
        event_data: Event data from verified webhook

    Returns:
        dict with status and customer_id
    """
    try:
        session = event_data.get("object", {})
        customer_id = session.get("customer", "")
        customer_email = session.get("customer_details", {}).get("email", "")

        if not customer_id:
            return {
                "status": "error",
                "message": "No customer_id in session",
            }

        # Activate local license
        LICENSE_DIR.mkdir(parents=True, exist_ok=True)
        license_path = LICENSE_DIR / LICENSE_FILE

        import json

        data = {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "activated_at": time.time(),
            "stripe_session_id": session.get("id", ""),
        }
        license_path.write_text(json.dumps(data, indent=2))

        # Touch cache to mark as freshly validated
        cache_path = LICENSE_DIR / CACHE_FILE
        cache_path.touch()

        return {
            "status": "ok",
            "customer_id": customer_id,
            "customer_email": customer_email,
            "activated": True,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


def validate_license_with_stripe(customer_id: str) -> dict:
    """Validate a license by checking customer status in Stripe.

    Args:
        customer_id: Stripe customer ID (cus_...)

    Returns:
        dict with status and subscription/payment status
    """
    _ensure_stripe()

    try:
        # Verify customer exists (retrieved but not directly used)
        stripe.Customer.retrieve(customer_id)

        # Check for active subscriptions
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="active",
            limit=1,
        )

        if subscriptions.data:
            sub = subscriptions.data[0]
            return {
                "status": "active",
                "type": "subscription",
                "current_period_end": sub.current_period_end,
                "customer_id": customer_id,
            }

        # Check for one-time payments
        payments = stripe.PaymentIntent.list(
            customer=customer_id,
            limit=10,
        )

        for payment in payments.auto_paging_iter():
            if payment.status == "succeeded":
                return {
                    "status": "active",
                    "type": "payment",
                    "customer_id": customer_id,
                }

        return {
            "status": "inactive",
            "customer_id": customer_id,
            "message": "No active subscription or recent payment found",
        }

    except stripe.error.InvalidRequestError as e:
        return {
            "status": "error",
            "message": f"Invalid customer_id: {e}",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


def refresh_local_license() -> dict:
    """Refresh local license by validating with Stripe API.

    Reads customer_id from license.json, validates with Stripe,
    and creates signed cache token if valid.

    Returns:
        dict with status and validation result
    """
    license_path = LICENSE_DIR / LICENSE_FILE

    if not license_path.exists():
        return {
            "status": "error",
            "message": "No local license found",
        }

    import json

    data = json.loads(license_path.read_text())
    customer_id = data.get("customer_id", "")

    if not customer_id:
        return {
            "status": "error",
            "message": "No customer_id in license file",
        }

    # Validate with Stripe
    result = validate_license_with_stripe(customer_id)

    if result.get("status") == "active":
        # Create signed cache token (matches license.py format)
        cache_path = LICENSE_DIR / CACHE_FILE
        expiry = time.time() + CACHE_TTL
        import hashlib
        import hmac

        from atlas_session.license import _HMAC_SECRET

        message = f"{customer_id}:{expiry}".encode()
        signature = hmac.new(_HMAC_SECRET, message, hashlib.sha256).hexdigest()
        token_data = {
            "customer_id": customer_id,
            "expiry": expiry,
            "signature": signature,
        }
        cache_path.write_text(json.dumps(token_data))

        return {
            "status": "ok",
            "validated": True,
            "license_type": result.get("type"),
            "customer_id": customer_id,
        }

    return {
        "status": "inactive",
        "message": result.get("message", "License not active"),
    }


def is_stripe_configured() -> bool:
    """Check if Stripe is properly configured."""
    try:
        _ensure_stripe()
        return True
    except StripeNotConfigured:
        return False
