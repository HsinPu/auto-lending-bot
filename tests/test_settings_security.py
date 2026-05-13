import pytest

from auto_lending_bot.settings_security import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_secret_round_trips_value() -> None:
    encrypted = encrypt_secret("secret-value", "key")

    assert encrypted.startswith("enc:v1:")
    assert "secret-value" not in encrypted
    assert decrypt_secret(encrypted, "key") == "secret-value"


def test_decrypt_secret_rejects_wrong_key() -> None:
    encrypted = encrypt_secret("secret-value", "key")

    with pytest.raises(ValueError, match="signature"):
        decrypt_secret(encrypted, "other-key")


def test_mask_secret_shows_only_suffix() -> None:
    assert mask_secret("abcdef") == "********cdef"
    assert mask_secret("abc") == "********"
