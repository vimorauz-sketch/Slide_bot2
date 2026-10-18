import logging
from typing import Dict, Any
from services.payment.base import BasePaymentProvider

logger = logging.getLogger(__name__)

class MockPaymentProvider(BasePaymentProvider):
    async def create_checkout(self, order_id: str, amount_uzs: int, description: str) -> Dict[str, Any]:
        return {
            "checkout_url": f"https://t.me/slidelab_bot?start=pay_{order_id}",
            "provider_tx_id": f"mock_tx_{order_id}",
            "status": "WAITING_PAYMENT",
            "amount": amount_uzs
        }

    async def verify_payment(self, transaction_id: str) -> bool:
        # Mock payment auto confirms upon user pressing 'To'lovni tasdiqlash'
        return True

class ClickPaymentProvider(BasePaymentProvider):
    def __init__(self, service_id: str = "0000", merchant_id: str = "0000"):
        self.service_id = service_id
        self.merchant_id = merchant_id

    async def create_checkout(self, order_id: str, amount_uzs: int, description: str) -> Dict[str, Any]:
        checkout_url = f"https://my.click.uz/services/pay?service_id={self.service_id}&merchant_id={self.merchant_id}&amount={amount_uzs}&transaction_param={order_id}"
        return {
            "checkout_url": checkout_url,
            "provider_tx_id": f"click_{order_id}",
            "status": "WAITING_PAYMENT",
            "amount": amount_uzs
        }

    async def verify_payment(self, transaction_id: str) -> bool:
        return True

class PaymePaymentProvider(BasePaymentProvider):
    def __init__(self, merchant_id: str = "0000"):
        self.merchant_id = merchant_id

    async def create_checkout(self, order_id: str, amount_uzs: int, description: str) -> Dict[str, Any]:
        # Amount in tiyin (1 UZS = 100 tiyin)
        amount_tiyin = amount_uzs * 100
        checkout_url = f"https://checkout.paycom.uz/{self.merchant_id}?ac.order_id={order_id}&a={amount_tiyin}"
        return {
            "checkout_url": checkout_url,
            "provider_tx_id": f"payme_{order_id}",
            "status": "WAITING_PAYMENT",
            "amount": amount_uzs
        }

    async def verify_payment(self, transaction_id: str) -> bool:
        return True
