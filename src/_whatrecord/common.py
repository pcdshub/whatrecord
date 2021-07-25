from dataclasses import dataclass
from typing import Dict, List, Optional

import apischema


@dataclass
class IocshRedirect:
    fileno: int
    name: str
    mode: str


@apischema.fields.with_fields_set
@dataclass
class IocshSplit:
    argv: List[str]
    redirects: Optional[Dict[int, IocshRedirect]] = None
    error: Optional[str] = None
