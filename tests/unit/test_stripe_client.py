"""Tests for Stripe integration."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from atlas_session.stripe_client import (
    StripeNotConfigured,
    StripeSignatureError,
    create_checkout_session,
    handle_checkout_completed,
    is_stripe_configured,
    refresh_local_license,
    validate_license_with_stripe,
    verify_webhook_signature,
)


class TestStripeConfiguration:
    """Tests for Stripe configuration detection."""

    def test_is_stripe_configured_no_key(self, monkeypatch):
        """Returns False when STRIPE_SECRET_KEY is not set."""
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        assert not is_stripe_configured()

    def test_is_stripe_configured_with_key(self, monkeypatch):
        """Returns True when STRIPE_SECRET_KEY is set."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        assert is_stripe_configured()

    def test_is_stripe_configured_no_library(self, monkeypatch):
        """Returns False when stripe library can't be imported."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

        # Reset and set stripe to None to simulate import failure
        import atlas_session.stripe_client as sc

        sc._STRIPE_IMPORTED = True
        sc.stripe = None

        assert not is_stripe_configured()

        # Reset for other tests
        sc._STRIPE_IMPORTED = False
        sc.stripe = None


class TestCreateCheckoutSession:
    """Tests for checkout session creation."""

    def test_create_checkout_no_key_raises(self, monkeypatch):
        """Raises StripeNotConfigured when no API key."""
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

        with pytest.raises(StripeNotConfigured):
            create_checkout_session(
                customer_email="test@example.com",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    def test_create_checkout_no_price_id_raises(self, monkeypatch):
        """Raises StripeNotConfigured when price ID is not set."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.delenv("STRIPE_PRICE_MONTHLY_ID", raising=False)

        with pytest.raises(StripeNotConfigured, match="PRICE_MONTHLY_ID"):
            create_checkout_session(
                customer_email="test@example.com",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                mode="subscription",
            )

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_create_checkout_success(self, mock_stripe, mock_ensure, monkeypatch):
        """Creates checkout session successfully."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("STRIPE_PRICE_MONTHLY_ID", "price_monthly")

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/123"
        mock_session.id = "cs_test_123"

        mock_stripe.checkout.Session.create.return_value = mock_session

        result = create_checkout_session(
            customer_email="test@example.com",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result["status"] == "ok"
        assert "checkout_url" in result
        assert result["session_id"] == "cs_test_123"

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_create_checkout_yearly(self, mock_stripe, mock_ensure, monkeypatch):
        """Creates yearly payment checkout session."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("STRIPE_PRICE_YEARLY_ID", "price_yearly")

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/456"
        mock_session.id = "cs_test_456"

        mock_stripe.checkout.Session.create.return_value = mock_session

        result = create_checkout_session(
            customer_email="test@example.com",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            mode="payment",
        )

        assert result["status"] == "ok"
        assert result["session_id"] == "cs_test_456"

        # Verify mode was passed correctly
        call_args = mock_stripe.checkout.Session.create.call_args
        assert call_args[1]["mode"] == "payment"


class TestWebhookSignature:
    """Tests for webhook signature verification."""

    def test_verify_webhook_no_secret(self, monkeypatch):
        """Raises error when webhook secret is not set."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

        with pytest.raises(StripeSignatureError, match="WEBHOOK_SECRET"):
            verify_webhook_signature(b"{}", "")

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_verify_webhook_invalid_signature(
        self, mock_stripe, mock_ensure, monkeypatch
    ):
        """Raises error for invalid signature."""
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_123")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

        class SignatureVerificationError(Exception):
            pass

        mock_stripe.error.SignatureVerificationError = SignatureVerificationError
        mock_stripe.Webhook.construct_event.side_effect = SignatureVerificationError(
            "Invalid signature"
        )

        with pytest.raises(StripeSignatureError):
            verify_webhook_signature(b"{}", "t=123,v1=bad")

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_verify_webhook_success(self, mock_stripe, mock_ensure, monkeypatch):
        """Verifies valid webhook signature."""
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_123")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

        mock_event = MagicMock()
        mock_event.type = "checkout.session.completed"
        mock_event.data = {"object": {"customer": "cus_123"}}

        mock_stripe.Webhook.construct_event.return_value = mock_event

        result = verify_webhook_signature(b"payload", "t=123,v1=valid")

        assert result["status"] == "ok"
        assert result["event_type"] == "checkout.session.completed"
        assert result["data"] == {"object": {"customer": "cus_123"}}


class TestHandleCheckoutCompleted:
    """Tests for checkout completion handling."""

    def test_handle_checkout_activates_license(self, tmp_path, monkeypatch):
        """Activates license when checkout completes."""
        monkeypatch.setattr("atlas_session.stripe_client.LICENSE_DIR", tmp_path)

        session_data = {
            "object": {
                "id": "cs_test_123",
                "customer": "cus_123",
                "customer_details": {"email": "test@example.com"},
            }
        }

        result = handle_checkout_completed(session_data)

        assert result["status"] == "ok"
        assert result["customer_id"] == "cus_123"
        assert result["customer_email"] == "test@example.com"
        assert result["activated"] is True

        # Verify license file was created
        license_file = tmp_path / "license.json"
        assert license_file.exists()

        data = json.loads(license_file.read_text())
        assert data["customer_id"] == "cus_123"
        assert data["customer_email"] == "test@example.com"

        # Verify cache was touched
        cache_file = tmp_path / ".license_cache"
        assert cache_file.exists()

    def test_handle_checkout_no_customer_id(self, tmp_path, monkeypatch):
        """Returns error when session has no customer_id."""
        monkeypatch.setattr("atlas_session.stripe_client.LICENSE_DIR", tmp_path)

        session_data = {
            "object": {
                "id": "cs_test_123",
                "customer": "",
                "customer_details": {"email": "test@example.com"},
            }
        }

        result = handle_checkout_completed(session_data)

        assert result["status"] == "error"
        assert "No customer_id" in result["message"]


class TestValidateLicenseWithStripe:
    """Tests for license validation via Stripe API."""

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_validate_active_subscription(self, mock_stripe, mock_ensure, monkeypatch):
        """Validates customer with active subscription."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

        mock_customer = MagicMock()
        mock_customer.id = "cus_123"
        mock_stripe.Customer.retrieve.return_value = mock_customer

        mock_sub = MagicMock()
        mock_sub.id = "sub_123"
        mock_sub.current_period_end = int(time.time()) + 86400
        mock_subscriptions = MagicMock()
        mock_subscriptions.data = [mock_sub]
        mock_stripe.Subscription.list.return_value = mock_subscriptions

        result = validate_license_with_stripe("cus_123")

        assert result["status"] == "active"
        assert result["type"] == "subscription"
        assert result["customer_id"] == "cus_123"
        assert "current_period_end" in result

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_validate_one_time_payment(self, mock_stripe, mock_ensure, monkeypatch):
        """Validates customer with successful one-time payment."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

        mock_customer = MagicMock()
        mock_stripe.Customer.retrieve.return_value = mock_customer

        # No active subscriptions
        mock_subscriptions = MagicMock()
        mock_subscriptions.data = []
        mock_stripe.Subscription.list.return_value = mock_subscriptions

        # But has successful payment
        mock_payment = MagicMock()
        mock_payment.status = "succeeded"
        mock_payments = MagicMock()
        mock_payments.auto_paging_iter.return_value = [mock_payment]
        mock_stripe.PaymentIntent.list.return_value = mock_payments

        result = validate_license_with_stripe("cus_123")

        assert result["status"] == "active"
        assert result["type"] == "payment"

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_validate_inactive_customer(self, mock_stripe, mock_ensure, monkeypatch):
        """Returns inactive for customer with no active sub or payment."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

        mock_customer = MagicMock()
        mock_stripe.Customer.retrieve.return_value = mock_customer

        mock_subscriptions = MagicMock()
        mock_subscriptions.data = []
        mock_stripe.Subscription.list.return_value = mock_subscriptions

        mock_payments = MagicMock()
        mock_payments.auto_paging_iter.return_value = []
        mock_stripe.PaymentIntent.list.return_value = mock_payments

        result = validate_license_with_stripe("cus_123")

        assert result["status"] == "inactive"
        assert "No active subscription" in result.get("message", "")

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_validate_invalid_customer(self, mock_stripe, mock_ensure, monkeypatch):
        """Returns error for invalid customer_id."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

        class InvalidRequestError(Exception):
            pass

        mock_stripe.error.InvalidRequestError = InvalidRequestError
        mock_stripe.Customer.retrieve.side_effect = InvalidRequestError(
            "No such customer"
        )

        result = validate_license_with_stripe("cus_invalid")

        assert result["status"] == "error"
        assert "Invalid customer_id" in result.get("message", "")


class TestRefreshLocalLicense:
    """Tests for license refresh from Stripe."""

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_refresh_success(self, mock_stripe, mock_ensure, tmp_path, monkeypatch):
        """Refreshes license and creates signed cache token on success."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setattr("atlas_session.stripe_client.LICENSE_DIR", tmp_path)

        # Create existing license
        license_file = tmp_path / "license.json"
        license_file.write_text(
            json.dumps({"customer_id": "cus_123", "activated_at": time.time()})
        )

        # Mock Stripe validation
        mock_customer = MagicMock()
        mock_customer.id = "cus_123"
        mock_stripe.Customer.retrieve.return_value = mock_customer

        mock_sub = MagicMock()
        mock_sub.id = "sub_123"
        mock_sub.current_period_end = int(time.time()) + 86400
        mock_subscriptions = MagicMock()
        mock_subscriptions.data = [mock_sub]
        mock_stripe.Subscription.list.return_value = mock_subscriptions

        result = refresh_local_license()

        assert result["status"] == "ok"
        assert result["validated"] is True
        assert result["license_type"] == "subscription"

        # Cache should be created with signed token
        cache_file = tmp_path / ".license_cache"
        assert cache_file.exists()
        # Verify it has the new signed token format
        cache_data = json.loads(cache_file.read_text())
        assert "signature" in cache_data
        assert cache_data["customer_id"] == "cus_123"

    def test_refresh_no_license(self, tmp_path, monkeypatch):
        """Returns error when no local license exists."""
        monkeypatch.setattr("atlas_session.stripe_client.LICENSE_DIR", tmp_path)

        result = refresh_local_license()

        assert result["status"] == "error"
        assert "No local license found" in result["message"]

    def test_refresh_no_customer_id(self, tmp_path, monkeypatch):
        """Returns error when license has no customer_id."""
        monkeypatch.setattr("atlas_session.stripe_client.LICENSE_DIR", tmp_path)

        # Create license without customer_id
        license_file = tmp_path / "license.json"
        license_file.write_text('{"status": "active"}')

        result = refresh_local_license()

        assert result["status"] == "error"
        assert "No customer_id" in result["message"]

    @patch("atlas_session.stripe_client._ensure_stripe")
    @patch("atlas_session.stripe_client.stripe")
    def test_refresh_inactive(self, mock_stripe, mock_ensure, tmp_path, monkeypatch):
        """Returns inactive when Stripe validation fails."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setattr("atlas_session.stripe_client.LICENSE_DIR", tmp_path)

        # Create existing license
        license_file = tmp_path / "license.json"
        license_file.write_text(
            json.dumps({"customer_id": "cus_123", "activated_at": time.time()})
        )

        # Mock Stripe to return inactive
        with patch("atlas_session.stripe_client.stripe") as mock_stripe:
            mock_customer = MagicMock()
            mock_stripe.Customer.retrieve.return_value = mock_customer

            mock_subscriptions = MagicMock()
            mock_subscriptions.data = []
            mock_stripe.Subscription.list.return_value = mock_subscriptions

            mock_payments = MagicMock()
            mock_payments.auto_paging_iter.return_value = []
            mock_stripe.PaymentIntent.list.return_value = mock_payments

            result = refresh_local_license()

            assert result["status"] == "inactive"
