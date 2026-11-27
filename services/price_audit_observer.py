import logging

from services.price_observer import PriceObserver


logger = logging.getLogger("exchange.market")


class PriceAuditObserver(PriceObserver):
    """Records committed market price events."""

    def on_price_changed(self, symbol, new_price):

        logger.info(
            "Market price committed: "
            "symbol=%s price_cents=%s",
            symbol,
            new_price
        )