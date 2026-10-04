from uuid import UUID

from application.exceptions import ApplicationException


class AttachmentException(ApplicationException):
    """Базовое исключение для операций с вложениями."""

    status_code: int = 400


class AttachmentNotFoundException(AttachmentException):
    status_code: int = 404

    def __init__(self, identifier: str | UUID):
        super().__init__(f"Вложение '{identifier}' не найдено.")
        self.identifier = identifier


class EmptyFilenameException(AttachmentException):
    def __init__(self, message: str = "Имя файла не может быть пустым."):
        super().__init__(message)


class InvalidFileSizeException(AttachmentException):
    def __init__(self, message: str = "Размер файла не может быть отрицательным."):
        super().__init__(message)
