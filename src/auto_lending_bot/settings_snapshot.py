import json
from dataclasses import asdict, fields, is_dataclass
from datetime import date

from auto_lending_bot.config import Settings

_TUPLE_FIELDS = {"market_analysis_currencies", "transferable_currencies"}


def settings_snapshot_json(settings: Settings) -> str:
    return json.dumps(_json_safe_settings(_settings_dict(settings)), sort_keys=True, separators=(",", ":"))


def settings_from_snapshot_json(snapshot_json: str) -> Settings:
    values = json.loads(snapshot_json)
    if not isinstance(values, dict):
        msg = "Settings snapshot must be a JSON object."
        raise ValueError(msg)
    for field_name in _TUPLE_FIELDS:
        if field_name in values:
            values[field_name] = tuple(values[field_name])
    if values.get("end_date"):
        values["end_date"] = date.fromisoformat(str(values["end_date"]))
    return Settings(**values)


def _json_safe_settings(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_safe_settings(item) for item in value]
    if isinstance(value, list):
        return [_json_safe_settings(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_settings(item) for key, item in value.items()}
    return value


def _settings_dict(settings: Settings) -> dict[str, object]:
    if is_dataclass(settings):
        return asdict(settings)
    return {field.name: getattr(settings, field.name) for field in fields(Settings)}
