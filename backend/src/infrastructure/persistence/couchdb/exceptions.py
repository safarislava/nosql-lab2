class CouchDbException(Exception):
    """Базовое исключение для операций с CouchDB."""

    def __init__(self, message: str = "Ошибка CouchDB.") -> None:
        super().__init__(message)
        self.message = message


class CouchDbNotFoundException(CouchDbException):
    """Документ или база данных не найдены (HTTP 404)."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"Ресурс CouchDB '{resource}' не найден.")
        self.resource = resource


class CouchDbConflictException(CouchDbException):
    """Конфликт версий документа MVCC (HTTP 409 Conflict)."""

    def __init__(
        self, doc_id: str, message: str = "Конфликт ревизий документа (MVCC)."
    ) -> None:
        super().__init__(f"Конфликт ревизии для документа '{doc_id}': {message}")
        self.doc_id = doc_id


class CouchDbConnectionException(CouchDbException):
    """Ошибка сетевого подключения к узлу CouchDB."""

    def __init__(self, url: str, reason: str = "") -> None:
        msg = f"Не удалось подключиться к узлу CouchDB '{url}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.url = url
