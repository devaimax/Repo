from __future__ import annotations

import requests


def notify(message: str, slack_webhook: str | None = None, telegram_token: str | None = None, telegram_chat_id: str | None = None) -> None:
    """Send notifications to configured channels (best-effort)."""

    if slack_webhook:
        try:
            requests.post(slack_webhook, json={"text": message}, timeout=5)
        except Exception:
            pass

    if telegram_token and telegram_chat_id:
        try:
            requests.get(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                params={"chat_id": telegram_chat_id, "text": message},
                timeout=5,
            )
        except Exception:
            pass
