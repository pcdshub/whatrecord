import dataclasses


@dataclasses.dataclass(repr=False)
class Context:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    def freeze(self):
        return FrozenContext(self.name, self.line)


@dataclasses.dataclass(repr=False, frozen=True)
class FrozenContext:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"


@dataclasses.dataclass
class IocshCommand:
    context: Context
    command: str
