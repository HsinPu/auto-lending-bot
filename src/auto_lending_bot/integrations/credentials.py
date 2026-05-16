from dataclasses import dataclass

from auto_lending_bot.config import Settings
from auto_lending_bot.profiles import (
    DEFAULT_PROFILE_CONTEXT,
    BotProfileContext,
    ensure_default_profile,
)


@dataclass(frozen=True)
class ExchangeCredentials:
    api_key: str
    api_secret: str


class ExchangeCredentialProvider:
    def credentials_for(
        self,
        settings: Settings,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> ExchangeCredentials:
        ensure_default_profile(profile_context)
        return ExchangeCredentials(
            api_key=settings.api_key,
            api_secret=settings.api_secret,
        )
