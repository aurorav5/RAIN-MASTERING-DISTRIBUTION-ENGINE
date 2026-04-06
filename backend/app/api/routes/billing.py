from fastapi import APIRouter, Request, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, get_db
from app.models.subscription import Subscription
from app.core.config import settings
from app.api.dependencies import CurrentUser, get_current_user
from datetime import datetime, timezone
import stripe
import structlog

logger = structlog.get_logger()
stripe.api_key = settings.STRIPE_SECRET_KEY
router = APIRouter(prefix="/billing", tags=["billing"])

STRIPE_TIER_MAP: dict[str, str] = {
    settings.STRIPE_PRICE_SPARK_MONTHLY: "spark",
    settings.STRIPE_PRICE_CREATOR_MONTHLY: "creator",
    settings.STRIPE_PRICE_ARTIST_MONTHLY: "artist",
    settings.STRIPE_PRICE_STUDIO_PRO_MONTHLY: "studio_pro",
}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
) -> dict:
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, detail={"code": "RAIN-E700", "message": "Signature verification failed"})

    logger.info("stripe_webhook", event_type=event["type"])

    async with AsyncSessionLocal() as db:
        match event["type"]:
            case "customer.subscription.created" | "customer.subscription.updated":
                await _handle_subscription_update(event["data"]["object"], db)
            case "customer.subscription.deleted":
                await _handle_subscription_deleted(event["data"]["object"], db)
            case "invoice.payment_failed":
                await _handle_payment_failed(event["data"]["object"], db)
            case _:
                pass

    return {"received": True}


async def _handle_subscription_update(sub_obj: dict, db: AsyncSession) -> None:
    customer_id: str = sub_obj["customer"]
    price_id: str = sub_obj["items"]["data"][0]["price"]["id"]
    tier = STRIPE_TIER_MAP.get(price_id, "spark")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.tier = tier
        sub.status = sub_obj["status"]
        sub.stripe_subscription_id = sub_obj["id"]
        sub.current_period_end = datetime.fromtimestamp(
            sub_obj["current_period_end"], tz=timezone.utc
        )
        await db.commit()
        logger.info("subscription_updated", customer=customer_id, tier=tier)


async def _handle_subscription_deleted(sub_obj: dict, db: AsyncSession) -> None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == sub_obj["id"])
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = "canceled"
        sub.tier = "free"
        await db.commit()
        logger.info("subscription_canceled", sub_id=sub_obj["id"])


async def _handle_payment_failed(invoice_obj: dict, db: AsyncSession) -> None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == invoice_obj["customer"])
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = "past_due"
        await db.commit()
        logger.warning("payment_failed", customer=invoice_obj["customer"])


# ---------------------------------------------------------------------------
# Checkout / subscription management endpoints
# ---------------------------------------------------------------------------

_KNOWN_PRICE_IDS: set[str] = {
    settings.STRIPE_PRICE_SPARK_MONTHLY,
    settings.STRIPE_PRICE_CREATOR_MONTHLY,
    settings.STRIPE_PRICE_ARTIST_MONTHLY,
    settings.STRIPE_PRICE_STUDIO_PRO_MONTHLY,
}


class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


@router.post("/checkout-session")
async def create_checkout_session(
    req: CheckoutRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Create Stripe checkout session. Returns session URL."""
    if _KNOWN_PRICE_IDS and req.price_id not in _KNOWN_PRICE_IDS:
        raise HTTPException(
            400,
            detail={"code": "RAIN-B400", "message": "Unknown price_id"},
        )

    logger.info("checkout_session_requested", user_id=str(current_user.user_id), price_id=req.price_id)

    if not settings.STRIPE_SECRET_KEY:
        return {"url": req.success_url + "?mock=true", "session_id": "cs_mock_dev"}

    # Look up or create Stripe customer by user_id metadata
    customers = stripe.Customer.search(query=f'metadata["user_id"]:"{current_user.user_id}"')
    if customers.data:
        customer_id: str = customers.data[0].id
    else:
        customer = stripe.Customer.create(metadata={"user_id": str(current_user.user_id)})
        customer_id = customer.id

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": req.price_id, "quantity": 1}],
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        metadata={"user_id": str(current_user.user_id)},
    )
    return {"url": session.url, "session_id": session.id}


@router.get("/subscription")
async def get_subscription(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current subscription state for the authenticated user."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {
            "tier": "free",
            "status": "active",
            "current_period_end": None,
            "cancel_at_period_end": False,
        }
    return {
        "tier": sub.tier,
        "status": sub.status,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
    }


class PortalRequest(BaseModel):
    return_url: str


@router.post("/portal-session")
async def create_portal_session(
    req: PortalRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create Stripe customer portal session for subscription management."""
    if not settings.STRIPE_SECRET_KEY:
        return {"url": req.return_url + "?portal=mock"}

    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(
            404,
            detail={"code": "RAIN-B404", "message": "No active subscription found"},
        )

    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=req.return_url,
    )
    return {"url": session.url}


@router.post("/cancel")
async def cancel_subscription(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel subscription at period end (not immediately)."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(
            404,
            detail={"code": "RAIN-B404", "message": "No active subscription found"},
        )

    if settings.STRIPE_SECRET_KEY:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)

    sub.cancel_at_period_end = True
    await db.commit()

    effective_date = sub.current_period_end.isoformat() if sub.current_period_end else None
    logger.info("subscription_cancel_requested", user_id=str(current_user.user_id), effective_date=effective_date)
    return {"canceled": True, "effective_date": effective_date}
