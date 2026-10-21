from sqlalchemy import Column, BigInteger, String, Integer, Float, DateTime, Text, JSON, ForeignKey
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

class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
