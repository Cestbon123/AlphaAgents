from app.adapters.broker import MockBrokerDataProvider
from app.domain.models import StockContext


class BasicSelectionStrategy:
    def __init__(self, data_provider: MockBrokerDataProvider) -> None:
        self._data_provider = data_provider

    def select_candidates(self) -> list[StockContext]:
        symbols = self._data_provider.get_candidate_symbols()
        return self._data_provider.get_stock_contexts(symbols)
