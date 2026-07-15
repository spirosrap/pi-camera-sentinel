# Archive Retention

Pi Camera Sentinel can bound its local motion archive by file count, capture age, and total bytes. The policy covers files named `motion-*` with `.jpg`, `.jpeg`, `.png`, or `.mp4` extensions. Other files are ignored.

## Configuration

```text
SENTINEL_OUTPUT_DIR=/var/lib/pi-camera-sentinel
SENTINEL_RETENTION_FILES=200
SENTINEL_RETENTION_DAYS=0
SENTINEL_RETENTION_MB=0
```

Each limit is independent. Set a limit to `0` to disable that rule. Existing installations remain on the 200-file policy unless age or size limits are explicitly added.

Cleanup runs after each motion batch, including batches suppressed by Telegram quiet hours. Photos and optional video clips share the same limits.

## Cleanup Order

The planner sorts captures from newest to oldest and applies limits in this order:

1. Remove captures older than `SENTINEL_RETENTION_DAYS`.
2. Keep at most `SENTINEL_RETENTION_FILES` of the remaining captures.
3. Keep the newest contiguous set that fits within `SENTINEL_RETENTION_MB`.

Every candidate receives one reason: `age`, `count`, or `size`. A capture selected by an earlier rule is not selected again by a later rule.

## Preview And Apply

Load the installed environment and preview cleanup without deleting anything:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel retention-cleanup --dry-run'
```

The JSON report includes the active policy, current archive usage, candidates, projected usage, and result totals. Apply the same plan against the current archive by omitting `--dry-run`:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel retention-cleanup'
```

The dashboard event-history header shows current usage, configured limits, and whether cleanup is pending. The same structured state is available under `summary.retention` from `/api/events`.
