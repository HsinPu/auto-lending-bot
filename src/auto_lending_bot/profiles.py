from dataclasses import dataclass


DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_NAME = "Default"


@dataclass(frozen=True)
class BotProfileContext:
    id: str
    name: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name}


DEFAULT_PROFILE_CONTEXT = BotProfileContext(
    id=DEFAULT_PROFILE_ID,
    name=DEFAULT_PROFILE_NAME,
)
