# Stripe Integration Setup Guide

This guide covers setting up Stripe payments for atlas-session-lifecycle Pro license sales.

## Overview

The Stripe integration enables:
- **Checkout sessions**: $9/month subscription or $89/year one-time payment
- **Webhook handling**: Automatic license activation on payment completion
- **License validation**: Verify customer status via Stripe API
- **Graceful fallback**: Works offline when Stripe is unavailable

## Step 1: Stripe Account Setup

1. **Create a Stripe account** at https://dashboard.stripe.com/register
2. **Complete account activation** (verify email, business details)
3. **Get your API keys** from Developers > API keys:
   - `sk_test_...` for testing
   - `sk_live_...` for production (never commit this!)

## Step 2: Create Products and Prices

In the Stripe Dashboard:

### Monthly Subscription Product

1. Go to **Products** > **Add product**
2. Create a product:
   - Name: `atlas-session-lifecycle Pro (Monthly)`
   - Description: `Monthly subscription for atlas-session-lifecycle Pro features`
   - Price: `$9.00 USD`
   - Billing: `Recurring` > `Monthly`
3. Copy the **Price ID** (starts with `price_`)
4. Set as `STRIPE_PRICE_MONTHLY_ID` environment variable

### Yearly License Product

1. Go to **Products** > **Add product**
2. Create a product:
   - Name: `atlas-session-lifecycle Pro (Yearly)`
   - Description: `Yearly license for atlas-session-lifecycle Pro features`
   - Price: `$89.00 USD`
   - Billing: `One-time`
3. Copy the **Price ID** (starts with `price_`)
4. Set as `STRIPE_PRICE_YEARLY_ID` environment variable

## Step 3: Configure Webhook Endpoint

### In Development (Stripe CLI)

1. **Install Stripe CLI**:
   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe

   # Linux
   curl -s https://packages.stripe.com/api/security/keypairs/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe-cli.gpg
   echo "deb [signed-by=/usr/share/keyrings/stripe-cli.gpg] https://packages.stripe.com/stripe-cli-debian-local stable main" | sudo tee -a /etc/apt/sources.list.d/stripe.list
   sudo apt-get update
   sudo apt-get install stripe

   # Windows
   # Download from https://github.com/stripe/stripe-cli/releases
   ```

2. **Login to Stripe**:
   ```bash
   stripe login
   ```

3. **Forward webhook events**:
   ```bash
   stripe listen --forward-to localhost:8000/api/stripe/webhook
   ```

4. **Copy the webhook secret** (`whsec_...`) and set as `STRIPE_WEBHOOK_SECRET`

### In Production

1. Go to **Developers** > **Webhooks** > **Add endpoint**
2. Set URL: `https://your-domain.com/api/stripe/webhook`
3. Select events to send:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
4. Copy the **Signing Secret** and set as `STRIPE_WEBHOOK_SECRET`

## Step 4: Environment Variables

Set these in your environment or `.env` file:

```bash
# Required for all Stripe operations
STRIPE_SECRET_KEY=sk_test_...  # or sk_live_... for production

# Required for checkout session creation
STRIPE_PRICE_MONTHLY_ID=price_...
STRIPE_PRICE_YEARLY_ID=price_...

# Required for webhook signature verification
STRIPE_WEBHOOK_SECRET=whsec_...
```

**Security notes**:
- Never commit `.env` files
- Use different keys for test and live modes
- Rotate secrets periodically
- Use secret management (Bitwarden, AWS Secrets Manager, etc.)

## Step 5: Testing

### Test Checkout Flow

```bash
# Set test mode keys
export STRIPE_SECRET_KEY=sk_test_...
export STRIPE_PRICE_MONTHLY_ID=price_...
export STRIPE_WEBHOOK_SECRET=whsec_...

# Run the MCP server
atlas-session

# From another terminal, test checkout via MCP
```

### Test Webhooks with Stripe CLI

```bash
# Trigger a test webhook event
stripe trigger checkout.session.completed

# Trigger subscription cancellation
stripe trigger customer.subscription.deleted
```

### Test Card Numbers

Use these test cards in checkout:

| Card Number | Result | Description |
|-------------|--------|-------------|
| `4242 4242 4242 4242` | Success | Standard test card |
| `4000 0000 0000 0002` | Decline | Card declined |
| `4000 0000 0000 9995` | Decline | Insufficient funds |
| `4000 0025 0000 3155` | Success | Requires authentication |

Use any future expiry date and any 3-digit CVC.

## Step 6: License CLI Commands

```bash
# Check license status
atlas-license status

# Manually refresh from Stripe
atlas-license refresh

# Revoke license
atlas-license revoke
```

## MCP Tools

After setup, these MCP tools are available:

- `stripe_health` - Check if Stripe is configured
- `stripe_create_checkout` - Create a checkout session
- `stripe_webhook` - Process webhook events
- `stripe_refresh_license` - Manually refresh license
- `stripe_validate_customer` - Validate customer status

## Troubleshooting

### "StripeNotConfigured: STRIPE_SECRET_KEY not configured"
- Set the `STRIPE_SECRET_KEY` environment variable
- Ensure it starts with `sk_test_` or `sk_live_`

### "StripeSignatureError: Invalid signature"
- Verify `STRIPE_WEBHOOK_SECRET` matches the webhook endpoint secret
- Check you're using test secret for test mode, live for live mode
- Ensure webhook payload is raw bytes, not parsed JSON

### Webhook not activating license
- Check webhook is receiving `checkout.session.completed` events
- Verify event has `customer` field
- Check `~/.atlas-session/license.json` exists

### License showing as expired
- Run `atlas-license refresh` to validate with Stripe
- Check customer has active subscription or recent payment
- Verify `STRIPE_SECRET_KEY` has access to customer data

## Going to Production

1. **Switch to live mode** in Stripe Dashboard
2. **Update environment variables** with live keys
3. **Create live products** and update price IDs
4. **Add production webhook endpoint**
5. **Test with real card** (small amount, refund immediately)
6. **Monitor webhook delivery logs** in Stripe Dashboard

## Architecture

```
┌─────────────┐     checkout      ┌──────────────┐
│   User      │ ──────────────────>│   Stripe     │
└─────────────┘                    └──────────────┘
       ▲                                  │
       │                                  │ webhook
       │                                  │
       │                                  ▼
┌─────────────┐                    ┌──────────────┐
│  License    │<───────────────────│ atlas-session│
│  (local)    │    activate         │   MCP Server │
└─────────────┘                    └──────────────┘
       │
       │ validate (every 24h)
       ▼
┌──────────────┐
│   Stripe API │
└──────────────┘
```

## Security Checklist

- [ ] Stripe keys stored in secure vault (not in code)
- [ ] Webhook endpoint enforces HTTPS in production
- [ ] Webhook signatures verified before processing
- [ ] Test keys never used in production
- [ ] Production keys rotated quarterly
- [ ] Webhook delivery logs monitored
- [ ] Rate limiting on checkout endpoint
- [ ] Customer IDs validated before license activation
