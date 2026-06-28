# Telegram Alerts

Pi Camera Sentinel sends Telegram alerts through a bot. The bot token and chat ID live only in `/etc/pi-camera-sentinel.env`.

## Create A Bot

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`.
3. Copy the token into:

```text
TELEGRAM_BOT_TOKEN=...
```

4. Send any message to your new bot.
5. On the Pi, run:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel show-chat-ids'
```

6. Copy the private chat ID into:

```text
TELEGRAM_CHAT_ID=...
```

## Test Delivery

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel send-test'
```

If this works, start the motion service:

```bash
sudo systemctl enable --now pi-camera-motion.service
```

## Avoid Spam

Use cooldowns and consecutive-frame checks:

```text
SENTINEL_MIN_FRAMES=2
SENTINEL_COOLDOWN_SECONDS=60
```

For busy scenes, increase:

```text
SENTINEL_CHANGED_RATIO=0.05
```
