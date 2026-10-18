from abc import ABC, abstractmethod
from typing import Dict, Any

class BasePaymentProvider(ABC):
    @abstractmethod
    async def create_checkout(self, order_id: str, amount_uzs: int, description: str) -> Dict[str, Any]:
        """
        Creates checkout payment payload / URL.
        Returns dict containing provider checkout_url, provider_tx_id, status.
        """
        pass

    @abstractmethod
    async def verify_payment(self, transaction_id: str) -> bool:
        """
        Verifies if transaction is successfully paid.
        """
        pass
