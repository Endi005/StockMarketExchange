
from abc import ABC, abstractmethod


class PriceObserver(ABC):

    @abstractmethod
    def on_price_changed(self, symbol, new_price):
        pass
