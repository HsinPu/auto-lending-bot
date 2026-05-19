from auto_lending_bot.config import Settings
from auto_lending_bot.operations.transfers import build_transfer_preview, execute_transfers
from auto_lending_bot.persistence.factory import RepositoryBundle
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext, ensure_default_profile


class ExchangeActionService:
    def __init__(
        self,
        settings: Settings,
        repositories: RepositoryBundle,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        ensure_default_profile(profile_context)
        self._settings = settings
        self._repositories = repositories
        self._profile_context = profile_context

    def transfer_previews(self, exchange) -> list:
        return build_transfer_preview(
            exchange_balances=exchange.get_exchange_balances(),
            lending_balances=exchange.get_lending_balances(),
            transferable_currencies=self._settings.transferable_currencies,
        )

    def transfer_preview_response(self, previews: list) -> dict[str, object]:
        return {
            "action": "transfer-preview",
            "ok": True,
            "dry_run": True,
            "transfer_count": len(previews),
            "transfers": [preview.__dict__ for preview in previews],
        }

    def transfer_funds_response(self, exchange, previews: list) -> dict[str, object]:
        if self._settings.dry_run:
            return {
                "action": "transfer-funds",
                "ok": True,
                "dry_run": True,
                "transferred_count": 0,
                "would_transfer_count": len(previews),
                "transfers": [preview.__dict__ for preview in previews],
            }

        results = execute_transfers(exchange, previews)
        return {
            "action": "transfer-funds",
            "ok": True,
            "dry_run": False,
            "transferred_count": len(results),
            "would_transfer_count": len(previews),
            "transfers": [result.__dict__ for result in results],
        }

    def cancel_open_offers_response(self, exchange) -> dict[str, object]:
        offers = exchange.get_open_loan_offers()
        if self._settings.dry_run:
            return {
                "action": "cancel-open-offers",
                "ok": True,
                "dry_run": True,
                "would_cancel_count": len(offers),
                "canceled_count": 0,
            }

        canceled_count = self._cancel_open_offers(exchange, offers)
        self._repositories.open_offers.replace_all([], profile_context=self._profile_context)
        return {
            "action": "cancel-open-offers",
            "ok": True,
            "dry_run": False,
            "would_cancel_count": len(offers),
            "canceled_count": canceled_count,
        }

    def cancel_open_offer_response(self, exchange, external_offer_id: str) -> dict[str, object]:
        offer = self._repositories.open_offers.find_by_external_offer_id(
            external_offer_id,
            profile_context=self._profile_context,
        )
        if offer is None:
            return {
                "action": "cancel-open-offer",
                "ok": False,
                "dry_run": self._settings.dry_run,
                "external_offer_id": external_offer_id,
                "canceled_count": 0,
                "message": "Open offer was not found in the local snapshot.",
            }

        if self._settings.dry_run:
            return {
                "action": "cancel-open-offer",
                "ok": True,
                "dry_run": True,
                "external_offer_id": external_offer_id,
                "would_cancel_count": 1,
                "canceled_count": 0,
            }

        exchange.cancel_loan_offer(external_offer_id)
        self._repositories.loan_offers.mark_canceled_by_external_offer_id(
            external_offer_id,
            profile_context=self._profile_context,
        )
        deleted_count = self._repositories.open_offers.delete_by_external_offer_id(
            external_offer_id,
            profile_context=self._profile_context,
        )
        return {
            "action": "cancel-open-offer",
            "ok": True,
            "dry_run": False,
            "external_offer_id": external_offer_id,
            "would_cancel_count": 1,
            "canceled_count": 1,
            "deleted_snapshot_count": deleted_count,
        }

    def _cancel_open_offers(self, exchange, offers: list[object]) -> int:
        canceled_count = 0
        for offer in offers:
            external_offer_id = getattr(offer, "external_offer_id", None)
            if not external_offer_id:
                continue
            external_offer_id = str(external_offer_id)
            exchange.cancel_loan_offer(external_offer_id)
            self._repositories.loan_offers.mark_canceled_by_external_offer_id(
                external_offer_id,
                profile_context=self._profile_context,
            )
            canceled_count += 1
        return canceled_count
