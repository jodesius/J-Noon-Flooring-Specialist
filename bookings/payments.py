"""Stripe integration for the customer portal.

Card data never touches this server: the browser talks to Stripe directly
through Stripe Elements, and we only ever handle the PaymentIntent id and
its status. A `CardPayment` row tracks one intent through its lifecycle;
`CardPayment.mark_succeeded()` writes the money into the `Payment` ledger.

With no Stripe keys configured everything here raises `PaymentsUnavailable`
and the portal falls back to "pay by bank transfer / cash", recorded by
hand.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class PaymentsUnavailable(Exception):
    """Card payments can't run right now (not configured, or Stripe errored)."""


def stripe_enabled():
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLISHABLE_KEY)


def _stripe():
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentsUnavailable("Stripe is not configured.")
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover
        raise PaymentsUnavailable("The 'stripe' package isn't installed.") from exc

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.max_network_retries = 2
    return stripe


def create_payment_intent(card_payment):
    """Create (or, on a retry, re-use) the Stripe PaymentIntent for this
    `CardPayment`. Returns the intent object."""
    stripe = _stripe()
    try:
        intent = stripe.PaymentIntent.create(
            amount=card_payment.amount_pence,
            currency="gbp",
            description=(
                f"{card_payment.job.reference} - "
                f"{card_payment.get_purpose_display()}"
            ),
            metadata={
                "card_payment": str(card_payment.slug),
                "job_reference": card_payment.job.reference,
                "purpose": card_payment.purpose,
            },
            automatic_payment_methods={"enabled": True},
            idempotency_key=f"cardpayment-{card_payment.slug}",
        )
    except Exception as exc:  # network, auth, card-api errors
        logger.exception("Stripe PaymentIntent create failed (CardPayment %s)",
                         card_payment.pk)
        raise PaymentsUnavailable(str(exc)) from exc
    return intent


def retrieve_intent(payment_intent_id):
    stripe = _stripe()
    try:
        return stripe.PaymentIntent.retrieve(payment_intent_id)
    except Exception as exc:
        logger.warning("Stripe PaymentIntent retrieve failed (%s): %s",
                       payment_intent_id, exc)
        raise PaymentsUnavailable(str(exc)) from exc


def verify_webhook(payload, signature_header):
    """Parse and signature-check a Stripe webhook. Raises on a bad signature."""
    stripe = _stripe()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise PaymentsUnavailable("No STRIPE_WEBHOOK_SECRET set.")
    return stripe.Webhook.construct_event(
        payload, signature_header, settings.STRIPE_WEBHOOK_SECRET
    )
