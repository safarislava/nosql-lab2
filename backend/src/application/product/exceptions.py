from uuid import UUID

from application.exceptions import ApplicationException


class ProductException(ApplicationException):
    """Базовое исключение для операций с товарами."""

    status_code: int = 400


class ProductNotFoundException(ProductException):
    status_code: int = 404

    def __init__(self, identifier: str | UUID):
        super().__init__(f"Товар '{identifier}' не найден.")
        self.identifier = identifier


class ProductAlreadyExistsException(ProductException):
    status_code: int = 409

    def __init__(self, identifier: str | UUID):
        super().__init__(f"Товар с ID '{identifier}' уже существует.")
        self.identifier = identifier


class InsufficientStockException(ProductException):
    status_code: int = 400

    def __init__(self, product_id: UUID, requested: int, available: int):
        super().__init__(
            f"Недостаточно товара на складе (ID: {product_id}): запрошено {requested}, доступно {available}."
        )
        self.product_id = product_id
        self.requested = requested
        self.available = available


class InvalidProductDataException(ProductException):
    """Базовое исключение для некорректных данных товара."""

    status_code: int = 400

    def __init__(self, message: str = "Некорректные данные товара."):
        super().__init__(message)


class EmptyProductNameException(InvalidProductDataException):
    def __init__(self, message: str = "Название товара не может быть пустым."):
        super().__init__(message)


class NegativeProductPriceException(InvalidProductDataException):
    def __init__(self, message: str = "Цена товара не может быть отрицательной."):
        super().__init__(message)


class NegativeProductQuantityException(InvalidProductDataException):
    def __init__(self, message: str = "Количество товара не может быть отрицательным."):
        super().__init__(message)


class InvalidStockAmountException(InvalidProductDataException):
    def __init__(
        self,
        message: str = "Количество товара для операции со складом должно быть положительным.",
    ):
        super().__init__(message)
