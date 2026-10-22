from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from database.models import User, PresentationOrder, PaymentTransaction, SystemSetting
from typing import Optional

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
    referred_by: Optional[int] = None
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            referred_by=referred_by
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def get_user(session: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()

async def update_user_language(session: AsyncSession, telegram_id: int, language: str):
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(language=language)
    )
    await session.commit()

async def ensure_user(session: AsyncSession, telegram_id: int) -> None:
    """PostgreSQL enforces the users foreign key: someone who never pressed /start since the
    database was created (e.g. after moving to PostgreSQL) still gets a row before their order."""
    if await session.get(User, telegram_id) is None:
        session.add(User(telegram_id=telegram_id))
        await session.flush()


async def create_presentation_order(
    session: AsyncSession,
    user_id: int,
    topic: str,
    subject: str,
    slide_count: int,
    template_id: str,
    total_price: int,
    pptx_path: Optional[str] = None,
    pdf_path: Optional[str] = None,
    content_json: Optional[str] = None,
    language: Optional[str] = None,
) -> PresentationOrder:
    order = PresentationOrder(
        user_id=user_id,
        topic=topic[:255],
        subject=(subject or "")[:255],
        slide_count=slide_count,
        template_id=template_id,
        total_price=total_price,
        pptx_path=pptx_path,
        pdf_path=pdf_path,
        content_json=content_json,
        language=language,
        status="PREVIEW_READY"
    )
    await ensure_user(session, user_id)
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order

async def get_presentation_order(session: AsyncSession, order_id: str) -> Optional[PresentationOrder]:
    result = await session.execute(select(PresentationOrder).where(PresentationOrder.id == order_id))
    return result.scalar_one_or_none()

async def update_order_status(session: AsyncSession, order_id: str, status: str):
    await session.execute(
        update(PresentationOrder).where(PresentationOrder.id == order_id).values(status=status)
    )
    await session.commit()

async def create_payment_transaction(
    session: AsyncSession,
    order_id: str,
    user_id: int,
    amount: int,
    provider: str = "MOCK"
) -> PaymentTransaction:
    tx = PaymentTransaction(
        order_id=order_id,
        user_id=user_id,
        amount=amount,
        provider=provider,
        status="WAITING_PAYMENT"
    )
    await ensure_user(session, user_id)
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx

async def get_payment_transaction(session: AsyncSession, transaction_id: str) -> Optional[PaymentTransaction]:
    result = await session.execute(select(PaymentTransaction).where(PaymentTransaction.id == transaction_id))
    return result.scalar_one_or_none()

async def update_payment_status(session: AsyncSession, transaction_id: str, status: str):
    await session.execute(
        update(PaymentTransaction).where(PaymentTransaction.id == transaction_id).values(status=status)
    )
    await session.commit()

async def get_payment_transaction_by_provider_id(
    session: AsyncSession, provider: str, provider_trans_id: str
) -> Optional[PaymentTransaction]:
    result = await session.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.provider == provider,
            PaymentTransaction.provider_trans_id == provider_trans_id
        )
    )
    return result.scalar_one_or_none()

async def create_provider_transaction(
    session: AsyncSession,
    order_id: str,
    user_id: int,
    amount: int,
    provider: str,
    provider_trans_id: str,
    state: int,
    create_time: Optional[int] = None
) -> PaymentTransaction:
    tx = PaymentTransaction(
        order_id=order_id,
        user_id=user_id,
        amount=amount,
        provider=provider,
        provider_trans_id=provider_trans_id,
        state=state,
        status="WAITING_PAYMENT",
        provider_create_time=create_time
    )
    await ensure_user(session, user_id)
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx

async def mark_transaction_performed(session: AsyncSession, tx: PaymentTransaction, perform_time: int):
    await session.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == tx.id)
        .values(state=2, status="PAID", provider_perform_time=perform_time)
    )
    await session.commit()
    tx.state = 2
    tx.status = "PAID"
    tx.provider_perform_time = perform_time

async def mark_transaction_cancelled(
    session: AsyncSession, tx: PaymentTransaction, cancel_time: int, reason: Optional[int], new_state: int
):
    await session.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == tx.id)
        .values(state=new_state, status="CANCELLED", provider_cancel_time=cancel_time, cancel_reason=reason)
    )
    await session.commit()
    tx.state = new_state
    tx.status = "CANCELLED"
    tx.provider_cancel_time = cancel_time
    tx.cancel_reason = reason

async def get_provider_transactions_in_range(
    session: AsyncSession, provider: str, from_ts: int, to_ts: int
) -> list[PaymentTransaction]:
    result = await session.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.provider == provider,
            PaymentTransaction.provider_create_time >= from_ts,
            PaymentTransaction.provider_create_time <= to_ts
        )
    )
    return list(result.scalars().all())

async def get_user_orders_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(select(func.count()).select_from(PresentationOrder).where(PresentationOrder.user_id == user_id))
    return result.scalar() or 0

async def count_user_orders_since(session: AsyncSession, user_id: int, since) -> int:
    """Orders (previews) a user created since the given UTC datetime."""
    result = await session.execute(select(func.count()).select_from(PresentationOrder).where(
        PresentationOrder.user_id == user_id, PresentationOrder.created_at >= since))
    return result.scalar() or 0

async def get_user_referrals_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(select(func.count()).select_from(User).where(User.referred_by == user_id))
    return result.scalar() or 0

async def get_setting(session: AsyncSession, key: str, default: str) -> str:
    result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default

async def set_setting(session: AsyncSession, key: str, value: str):
    result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        setting = SystemSetting(key=key, value=value)
        session.add(setting)
    await session.commit()
