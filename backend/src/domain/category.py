from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class Category:
    name: str
    id: UUID = field(default_factory=uuid4)
    slug: str = ""
    description: str = ""
