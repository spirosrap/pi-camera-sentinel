# Motion Activity Insights

Pi Camera Sentinel summarizes the retained motion archive above Event history. The selected 24-hour, 7-day, or all-time range controls both the capture grid and the activity view.

## Metrics

- **Captures** is the exact number of retained image captures in the selected range.
- **Active periods** reports how many chart buckets contain at least one capture.
- **Peak period** shows the busiest bucket and its start time.
- **Last activity** shows the newest retained capture in the selected range.

The chart is relative within the selected range: the tallest bar is the busiest period, and other bars scale against it. Hovering a bar shows its capture count and start time. The chart also exposes an accessible text summary.

## Bucket Ranges

- `24h` uses 24 rolling one-hour buckets.
- `7d` uses 7 rolling one-day buckets.
- `all` uses whole-day buckets sized to cover the retained archive in no more than 14 periods.

The server computes bucket boundaries in UTC. The dashboard formats labels in the browser's local timezone. A capture exactly on a boundary belongs to the period beginning at that boundary.

## API

`GET /api/events` includes an `activity` object alongside `events`, `summary`, and `next_before`:

```json
{
  "starts_at": "2026-07-15T10:00:00+00:00",
  "ends_at": "2026-07-16T10:00:00+00:00",
  "bucket_seconds": 3600,
  "active_bucket_count": 5,
  "peak_count": 12,
  "peak_started_at": "2026-07-16T06:00:00+00:00",
  "last_captured_at": "2026-07-16T09:42:10+00:00",
  "buckets": []
}
```

Each bucket contains `started_at`, `ended_at`, `count`, and `size_bytes`. Bucket counts always sum to `summary.window_count`. Pagination changes only the returned capture page; activity continues to summarize the complete selected range.

Activity is derived directly from retained file timestamps during the existing archive scan. It does not decode images, issue extra browser requests, or maintain a second database. Archive retention therefore remains the single source of truth.
