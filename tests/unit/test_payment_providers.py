import pytest
from services.payment.providers import MockPaymentProvider, ClickPaymentProvider, PaymePaymentProvider

pytestmark = pytest.mark.asyncio


async def test_mock_provider_checkout_returns_waiting_status():
    provider = MockPaymentProvider()
    result = await provider.create_checkout("order-1", 3500, "SlideLab Order order-1")
    assert result["status"] == "WAITING_PAYMENT"
    assert result["amount"] == 3500
    assert "order-1" in result["checkout_url"]


async def test_mock_provider_verify_payment_always_confirms():
    provider = MockPaymentProvider()
    assert await provider.verify_payment("any-tx-id") is True


async def test_click_provider_builds_a_well_formed_checkout_url():
    provider = ClickPaymentProvider(service_id="1234", merchant_id="5678")
    result = await provider.create_checkout("order-2", 7000, "desc")

    assert result["checkout_url"].startswith("https://my.click.uz/services/pay?")
    assert "service_id=1234" in result["checkout_url"]
    assert "merchant_id=5678" in result["checkout_url"]
    assert "amount=7000" in result["checkout_url"]
    assert "transaction_param=order-2" in result["checkout_url"]
    assert result["amount"] == 7000


async def test_payme_provider_converts_amount_to_tiyin():
    provider = PaymePaymentProvider(merchant_id="abc123")
    result = await provider.create_checkout("order-3", 1500, "desc")

    # Payme's checkout URL encodes the amount in tiyin (1 UZS = 100 tiyin).
    assert "a=150000" in result["checkout_url"]
    assert "abc123" in result["checkout_url"]
    assert "ac.order_id=order-3" in result["checkout_url"]
    # The returned amount field must still be in UZS, not tiyin, for display purposes.
    assert result["amount"] == 1500


async def test_click_and_payme_verify_payment_are_stubs_returning_true():
    # Documents current (pre-production) behavior: these are not yet wired to a
    # real merchant API, so verify_payment is a stub. Production integration
    # must replace this before PAYMENT_ENV=PRODUCTION is used for real money.
    assert await ClickPaymentProvider().verify_payment("tx") is True
    assert await PaymePaymentProvider().verify_payment("tx") is True
