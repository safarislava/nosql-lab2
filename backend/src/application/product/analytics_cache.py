from abc import ABC, abstractmethod

from application.product.dto import ProductStateChangesDto


class IProductAnalyticsCache(ABC):
    """Кэш результата аналитического запроса по товарам."""

    @abstractmethod
    def get(self) -> list[ProductStateChangesDto] | None:
        """Вернуть сохранённый результат, если он ещё не истёк."""
        raise NotImplementedError

    @abstractmethod
    def set(self, stats: list[ProductStateChangesDto]) -> None:
        """Сохранить результат на время TTL."""
        raise NotImplementedError

    @abstractmethod
    def invalidate(self) -> None:
        """Удалить сохранённый результат."""
        raise NotImplementedError
