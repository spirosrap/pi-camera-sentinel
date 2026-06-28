from __future__ import annotations

from pathlib import Path

import requests

from .config import Settings


def telegram_request(
    settings: Settings,
    method: str,
    *,
    data: dict[str, str],
    files: dict | None = None,
    timeout: float = 60,
) -> dict:
    url = f"https://api.telegram.org/bot{settings.telegram_token}/{method}"
    response = requests.post(url, data=data, files=files, timeout=timeout)
    try:
        payload = response.json()
    except ValueError:
        payload = {"ok": False, "description": response.text[:500]}
    if not response.ok or not payload.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: HTTP {response.status_code}: {payload}")
    return payload


def send_message(settings: Settings, text: str) -> None:
    telegram_request(
        settings,
        "sendMessage",
        data={
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        },
    )


def send_photo(settings: Settings, path: Path, caption: str) -> None:
    with path.open("rb") as handle:
        telegram_request(
            settings,
            "sendPhoto",
            data={
                "chat_id": settings.telegram_chat_id,
                "caption": caption,
            },
            files={"photo": handle},
        )


def send_video(settings: Settings, path: Path, caption: str) -> None:
    with path.open("rb") as handle:
        telegram_request(
            settings,
            "sendVideo",
            data={
                "chat_id": settings.telegram_chat_id,
                "caption": caption,
                "supports_streaming": "true",
            },
            files={"video": handle},
        )


def get_chat_ids(settings: Settings) -> list[dict[str, str]]:
    if not settings.telegram_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    url = f"https://api.telegram.org/bot{settings.telegram_token}/getUpdates"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram getUpdates failed: {payload}")

    chats: dict[str, dict[str, str]] = {}
    for update in payload.get("result", []):
        message = update.get("message") or update.get("edited_message") or update.get("channel_post")
        if not message:
            continue
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        chats[str(chat_id)] = {
            "id": str(chat_id),
            "type": str(chat.get("type", "")),
            "title": str(chat.get("title") or chat.get("username") or chat.get("first_name") or ""),
        }
    return list(chats.values())
