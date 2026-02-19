"""Stripe MCP tool definitions.

Handles checkout creation, webhook processing, and license validation.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..stripe_client import (
    StripeNotConfigured,
    StripeSignatureError,
    create_checkout_session,
    handle_checkout_completed,
    is_stripe_configured,
    refresh_local_license,
    verify_webhook_signature,
)


def register(mcp: FastMCP) -> None:
    """Register all Stripe tools on the given server."""

    @mcp.tool
    async def stripe_health() -> dict:
        """Check if Stripe is properly configured.

        Returns {healthy, configured} status.
        """
        return {
            "status": "ok",
            "healthy": True,
            "configured": is_stripe_configured(),
        }

    @mcp.tool
    async def stripe_create_checkout(
        customer_email: str,
        success_url: str = "https://atlas-ai.au/success",
        cancel_url: str = "https://atlas-ai.au/cancel",
        plan: str = "monthly",
    ) -> dict:
        """Create a Stripe Checkout session for license purchase.

        Args:
            customer_email: Email for the customer
            success_url: Redirect URL after successful payment
            cancel_url: Redirect URL if payment cancelled
            plan: "monthly" ($9/mo) or "yearly" ($89/yr)

        Returns:
            dict with checkout_url and session_id

        Raises:
            StripeNotConfigured: If Stripe keys not configured
        """
        if plan not in ("monthly", "yearly"):
            return {
                "status": "error",
                "message": "Invalid plan. Use 'monthly' or 'yearly'",
            }

        mode = "subscription" if plan == "monthly" else "payment"

        try:
            return create_checkout_session(
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                mode=mode,
            )
        except StripeNotConfigured as e:
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to create checkout: {e}",
            }

    @mcp.tool
    async def stripe_webhook(
        payload: str,
        signature: str,
    ) -> dict:
        """Process a Stripe webhook event.

        Verifies signature and handles checkout.session.completed events.

        SECURITY: The payload must be the raw UTF-8 bytes from the HTTP request
        body, exactly as received from Stripe. Do not parse, reformat, or
        normalize the JSON before passing to this function - HMAC verification
        depends on byte-exact matching.

        Args:
            payload: Raw request body as string (must be exact bytes from Stripe)
            signature: Stripe-Signature header value

        Returns:
            dict with status and event handling result
        """
        try:
            # CRITICAL: Use exact UTF-8 bytes from request - no re-encoding
            # Stripe HMAC is computed over raw HTTP body bytes
            payload_bytes = payload.encode("utf-8")

            result = verify_webhook_signature(payload_bytes, signature)

            if result.get("status") != "ok":
                return result

            event_type = result.get("event_type", "")

            if event_type == "checkout.session.completed":
                return handle_checkout_completed(result.get("data", {}))
            elif event_type == "customer.subscription.deleted":
                # Handle subscription cancellation - revoke license
                return {
                    "status": "ok",
                    "event": event_type,
                    "message": "Subscription cancelled - license expired",
                }
            else:
                return {
                    "status": "ok",
                    "event": event_type,
                    "message": "Event received but not processed",
                }

        except StripeSignatureError as e:
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Webhook processing failed: {e}",
            }

    @mcp.tool
    async def stripe_refresh_license() -> dict:
        """Manually refresh license from Stripe API.

        Forces validation with Stripe regardless of cache age.

        Returns:
            dict with status and validation result
        """
        try:
            result = refresh_local_license()

            if result.get("status") == "ok":
                return {
                    "status": "ok",
                    "message": "License refreshed successfully",
                    "license_type": result.get("license_type"),
                }
            elif result.get("status") == "inactive":
                return {
                    "status": "inactive",
                    "message": result.get("message", "License not active"),
                }
            else:
                return result

        except Exception as e:
            return {
                "status": "error",
                "message": f"Refresh failed: {e}",
            }

    @mcp.tool
    async def stripe_validate_customer(customer_id: str) -> dict:
        """Validate a customer's license status directly in Stripe.

        Args:
            customer_id: Stripe customer ID (cus_...)

        Returns:
            dict with customer status and subscription info
        """
        try:
            from ..stripe_client import validate_license_with_stripe

            return validate_license_with_stripe(customer_id)
        except StripeNotConfigured as e:
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Validation failed: {e}",
            }
