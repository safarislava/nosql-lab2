from uuid import UUID

from application.exceptions import ApplicationException


class CategoryException(ApplicationException):
    """Базовое исключение для операций с категориями."""

    status_code: int = 400


class CategoryNotFoundException(CategoryException):
    status_code: int = 404

    def __init__(self, identifier: str | UUID):
        super().__init__(f"Категория '{identifier}' не найдена.")
        self.identifier = identifier


class EmptyCategoryNameException(CategoryException):
    def __init__(self, message: str = "Название категории не может быть пустым."):
        super().__init__(message)
