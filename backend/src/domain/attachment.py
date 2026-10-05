from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AttachmentMetadata:
    filename: str
    content_type: str
    size_bytes: int
    id: UUID = field(default_factory=uuid4)
    order: int = 0
    upload_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    checksum: str = ""
    description: str = ""
