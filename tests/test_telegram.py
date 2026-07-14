import json
from dataclasses import replace

import pytest

from pi_camera_sentinel import telegram
from pi_camera_sentinel.config import Settings


def test_send_media_group_builds_telegram_album(monkeypatch, tmp_path):
    paths = []
    for index in range(3):
        path = tmp_path / f"motion-{index}.jpg"
        path.write_bytes(f"photo-{index}".encode())
        paths.append(path)

    calls = []

    def fake_request(_settings, method, *, data, files):
        calls.append(
            {
                "method": method,
                "data": data,
                "file_names": [value[0] for value in files.values()],
            }
        )

    monkeypatch.setattr(telegram, "telegram_request", fake_request)
    settings = replace(Settings.from_env(), telegram_chat_id="123")

    telegram.send_media_group(settings, paths, "Motion burst")

    media = json.loads(calls[0]["data"]["media"])
    assert calls == [
        {
            "method": "sendMediaGroup",
            "data": {
                "chat_id": "123",
                "media": calls[0]["data"]["media"],
            },
            "file_names": ["motion-0.jpg", "motion-1.jpg", "motion-2.jpg"],
        }
    ]
    assert media == [
        {"type": "photo", "media": "attach://photo0", "caption": "Motion burst"},
        {"type": "photo", "media": "attach://photo1"},
        {"type": "photo", "media": "attach://photo2"},
    ]


@pytest.mark.parametrize("count", [1, 11])
def test_send_media_group_enforces_telegram_limits(tmp_path, count):
    paths = [tmp_path / f"motion-{index}.jpg" for index in range(count)]

    with pytest.raises(ValueError, match="between 2 and 10"):
        telegram.send_media_group(Settings.from_env(), paths, "Motion burst")
