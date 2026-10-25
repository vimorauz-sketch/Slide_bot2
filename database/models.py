from sqlalchemy import Column, BigInteger, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database.connection import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    language = Column(String(10), default="uz")
    balance = Column(Integer, default=0)
    referred_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # admin panel
    is_blocked = Column(Boolean, default=False, nullable=False)    # blocked by an admin: the bot ignores them
    blocked_reason = Column(String(255), nullable=True)
    bot_blocked = Column(Boolean, default=False, nullable=False)   # the user blocked the bot (broadcasts skip them)
    last_seen_at = Column(DateTime, nullable=True)
    # free presentations: the one-time trial and bonus presentations (referrals, admin gifts)
    trial_used_at = Column(DateTime, nullable=True)                # None = the free trial is still available
    bonus_credits = Column(Integer, default=0, nullable=False)
    referral_rewarded = Column(Boolean, default=False, nullable=False)  # the inviter already got this friend's bonus

    orders = relationship("PresentationOrder", back_populates="user")

class PresentationOrder(Base):
    __tablename__ = "presentation_orders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    subject = Column(String(255), nullable=True)
    topic = Column(String(255), nullable=False)
    slide_count = Column(Integer, nullable=False)
    template_id = Column(String(100), default="01_minimal_blue")
    status = Column(String(50), default="CREATED")  # CREATED, PREVIEW_READY, PAID, CANCELLED
    total_price = Column(Integer, nullable=False)
    pptx_path = Column(Text, nullable=True)
    pdf_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # payment (TezCheck bill) and delivery
    paid_at = Column(DateTime, nullable=True)
    paid_by = Column(String(30), nullable=True)          # TEZCHECK, ADMIN, DEMO, CLICK, PAYME
    bill_id = Column(String(64), nullable=True, index=True)
    payment_url = Column(Text, nullable=True)
    bill_expires_at = Column(DateTime, nullable=True)
    paid_amount = Column(Integer, nullable=True)         # so'm the customer paid
    fee_amount = Column(Integer, nullable=True)          # TezCheck commission, so'm
    payment_provider = Column(String(30), nullable=True)  # click / payme / test
    delivered_at = Column(DateTime, nullable=True)
    content_json = Column(Text, nullable=True)           # deck text + photos: files can be rebuilt after a redeploy
    language = Column(String(10), nullable=True)

    user = relationship("User", back_populates="orders")
    transactions = relationship("PaymentTransaction", back_populates="order")

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("presentation_orders.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    provider = Column(String(50), default="MOCK")  # CLICK, PAYME, UZUM, MOCK
    status = Column(String(50), default="CREATED") # CREATED, WAITING_PAYMENT, PAYMENT_SUBMITTED, PAID, FAILED, EXPIRED, REFUNDED
    created_at = Column(DateTime, default=datetime.utcnow)

    # Provider webhook state (Click Shop API / Payme Merchant API). `state` follows
    # Payme's convention and is reused for Click too: 1=created/awaiting, 2=performed/paid,
    # -1=cancelled before being performed, -2=cancelled after being performed (refund).
    provider_trans_id = Column(String(100), nullable=True, index=True)  # Click's click_trans_id / Payme's id
    state = Column(Integer, nullable=True)
    cancel_reason = Column(Integer, nullable=True)
    provider_create_time = Column(BigInteger, nullable=True)
    provider_perform_time = Column(BigInteger, nullable=True)
    provider_cancel_time = Column(BigInteger, nullable=True)

    order = relationship("PresentationOrder", back_populates="transactions")

class TemplateModel(Base):
    __tablename__ = "templates"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), default="General")
    theme_config = Column(JSON, nullable=False)
    status = Column(String(20), default="ACTIVE")
    price_multiplier = Column(Float, default=1.0)

class WebhookEvent(Base):
    """Processed payment webhooks (the same event can be delivered more than once)."""
    __tablename__ = "webhook_events"

    id = Column(String(64), primary_key=True)            # body "id" (oev_...)
    type = Column(String(64), nullable=True)
    bill_id = Column(String(64), nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text, nullable=False)
    photo_path = Column(Text, nullable=True)
    button_text = Column(String(64), nullable=True)
    button_url = Column(String(255), nullable=True)
    segment = Column(String(30), default="all")
    status = Column(String(20), default="queued")         # queued, sending, done, stopped, failed
    total = Column(Integer, default=0)
    sent = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    blocked = Column(Integer, default=0)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class AdminToken(Base):
    """One-time dashboard login links sent by the bot (/admin)."""
    __tablename__ = "admin_tokens"

    token_hash = Column(String(64), primary_key=True)
    admin_id = Column(BigInteger, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime, default=datetime.utcnow, index=True)
    admin = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
