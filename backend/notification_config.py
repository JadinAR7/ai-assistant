import os


EXISTING_DEFAULT_IMESSAGE_RECIPIENT = "jadinrobinson05@hotmail.com"


def _clean_recipient(recipient: str | None) -> str:
    return str(recipient or "").strip()


def _mask_recipient(recipient: str | None) -> str | None:
    clean = _clean_recipient(recipient)

    if not clean:
        return None

    digits = "".join(char for char in clean if char.isdigit())
    if digits:
        return f"***{digits[-4:]}"

    return f"***{clean[-4:]}"


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def get_default_imessage_recipient(explicit_recipient: str | None = None) -> dict:
    explicit = _clean_recipient(explicit_recipient)
    if explicit:
        return {
            "recipient": explicit,
            "masked_recipient": _mask_recipient(explicit),
            "source": "explicit",
            "configured": True,
        }

    env_recipient = _clean_recipient(os.getenv("SCAN_NOTIFY_IMESSAGE_RECIPIENT"))
    if env_recipient:
        return {
            "recipient": env_recipient,
            "masked_recipient": _mask_recipient(env_recipient),
            "source": "env",
            "configured": True,
        }

    default_recipient = _clean_recipient(EXISTING_DEFAULT_IMESSAGE_RECIPIENT)
    if default_recipient:
        return {
            "recipient": default_recipient,
            "masked_recipient": _mask_recipient(default_recipient),
            "source": "default",
            "configured": True,
        }

    return {
        "recipient": None,
        "masked_recipient": None,
        "source": "none",
        "configured": False,
    }


def get_notification_config() -> dict:
    recipient = get_default_imessage_recipient()

    return {
        "imessage_enabled": _env_flag("SCAN_NOTIFY_IMESSAGE_ENABLED"),
        "default_recipient_configured": bool(recipient["configured"]),
        "recipient_source": recipient["source"],
        "default_recipient": recipient["masked_recipient"],
    }
