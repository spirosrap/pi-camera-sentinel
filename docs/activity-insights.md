# Motion Activity Insights

Pi Camera Sentinel summarizes the retained motion archive above Event history. The selected 24-hour, 7-day, or all-time range controls both the capture grid and the activity view.

## Metrics

- **Captures** is the exact number of retained image captures in the selected range.
- **Active periods** reports how many chart buckets contain at least one capture.
- **Peak period** shows the busiest bucket and its start time.
- **Last activity** shows the newest retained capture in the selected range.

The chart is relative within the selected range: the tallest bar is the busiest period, and other bars scale against it. Each non-empty bar is an accessible button labeled with its capture count and local-time period.

## Period Drill-Down

Selecting a non-empty chart bar filters Event history to captures whose timestamps fall inside that exact period. The full-range chart remains visible, the active period is highlighted, and pagination continues within the selected period. **Clear period** restores the complete 24-hour, 7-day, or all-time range without changing the active range tab.

The selected start boundary is inclusive and the end boundary is exclusive. This keeps a capture on a shared boundary in exactly one period.

## Bucket Ranges

- `24h` uses 24 rolling one-hour buckets.
- `7d` uses 7 rolling one-day buckets.
- `all` uses whole-day buckets sized to cover the retained archive in no more than 14 periods.

The server computes bucket boundaries in UTC. The dashboard formats labels in the browser's local timezone. A capture exactly on a boundary belongs to the period beginning at that boundary.

## API

`GET /api/events` includes an `activity` object alongside `events`, `summary`, `selection`, and `next_before`:

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

Pass both `period_start` and `period_end` as Unix timestamps to filter the capture page. The API rejects missing pairs, non-finite or non-positive timestamps, and periods whose start is not earlier than their end. A filtered response includes:

```json
{
  "selection": {
    "started_at": "2026-07-16T06:00:00+00:00",
    "ended_at": "2026-07-16T07:00:00+00:00",
    "count": 12,
    "size_bytes": 3821421
  }
}
```

The period intersects the selected top-level `window`; it cannot expose captures outside that range. `before` continues to paginate only the filtered records.

Activity is derived directly from retained file timestamps during the existing archive scan. It does not decode images, issue extra browser requests, or maintain a second database. Archive retention therefore remains the single source of truth.
