from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class IocshRedirect:
    fileno: int
    name: str
    mode: str


@dataclass
class IocshSplit:
    argv: List[str]
    redirects: Dict[int, IocshRedirect]
    error: Optional[str]
