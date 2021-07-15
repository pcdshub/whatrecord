from dataclasses import dataclass
from typing import List, Optional


@dataclass
class IocshRedirect:
    fileno: int
    name: str
    mode: str


@dataclass
class IocshSplit:
    argv: List[str]
    redirects: List[IocshRedirect]
    error: Optional[str]
