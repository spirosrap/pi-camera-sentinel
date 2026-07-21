# Changelog

## 1.18.1 - 2026-07-21

- Tune motion defaults to retain small pets farther from a wide-angle camera.
- Sample twice per second at 320 x 180 with a 0.8% changed-area trigger.
- Keep two-frame confirmation and a 30-second cooldown to limit brief-noise alerts.

## 1.18.0 - 2026-07-21

- Add optional per-channel JPEG color correction on the capable relay host.
- Apply the same correction to live MJPEG frames and downloaded or displayed snapshots.
- Preserve the original no-reencoding relay path when all channel gains remain at their default value.

## 1.17.0 - 2026-07-17

- Keep the last rendered frame unobstructed during transport reconnects that recover within 15 seconds.
- Switch automatically to a two-frame-per-second snapshot stream after three long-lived stream failures in one minute.
- Keep snapshot fallback recovery in the same canvas without exposing a mode change or broken-image surface.
- Hold the relay's shared Pi stream open for 30 seconds across brief viewer gaps to prevent connection churn.
- Reserve the centered reconnect notice for sustained interruptions and genuine camera outages.

## 1.16.2 - 2026-07-17

- Keep a client build identity in the HTML instead of presenting the server version as the loaded UI version.
- Automatically replace stale dashboard documents with a versioned, timestamped URL when the server release changes.
- Prevent an old native-MJPEG page from appearing current after only its status response updates.

## 1.16.1 - 2026-07-17

- Replace the browser's unreliable native MJPEG image renderer with a streamed JPEG canvas renderer.
- Measure each successfully drawn frame so stalled or failed rendering can never remain falsely Live.
- Preserve the last complete canvas frame during reconnects without exposing a broken-image surface.
- Abort and rebuild streams that do not draw a fresh frame within five seconds.
- Permit image-only `blob:` URLs in the dashboard security policy for isolated JPEG decoding.
- Expose non-visible renderer phase diagnostics for live troubleshooting.

## 1.15.1 - 2026-07-17

- Reconnect a stalled Pi MJPEG upstream without closing attached browser streams.
- Detect failed browser image connections independently of healthy dashboard snapshots.
- Keep the latest camera snapshot visible while the live view reconnects instead of exposing a black broken-image state.
- Replace raw transport errors in the viewer with a concise latest-frame status.
- Retry interrupted live views within eight seconds and reconnect cleanly when a hidden tab returns.
- Add integration coverage for a viewer surviving an upstream camera disconnect.

## 1.14.0 - 2026-07-17

- Fan every relay viewer out from one shared Pi MJPEG connection instead of opening one Pi stream per browser tab.
- Start the shared upstream lazily and release it shortly after the last viewer disconnects.
- Preserve original JPEG frame bytes, resolution, quality, and frame rate without re-encoding.
- Add multi-viewer integration coverage that proves concurrent viewers create only one camera request.

## 1.13.0 - 2026-07-17

- Add an optional LAN-to-Tailscale relay for moving sustained HTTPS and encryption work off the Raspberry Pi.
- Route live stream and snapshot bytes directly over the trusted LAN without resizing or re-encoding them.
- Keep dashboard controls, health, motion history, and retained events authoritative on the Pi.
- Rewrite proxied host and origin headers so same-origin dashboard writes continue to work through the relay.
- Add an optional low-cost redirect that keeps retired Pi URLs and previously sent alert links working.
- Add a hardened relay service, Debian/Ubuntu installer, sample configuration, deployment guide, and integration coverage.

## 1.12.0 - 2026-07-17

- Move ignored-area editing from the long dashboard into a dedicated `/motion-zones` page.
- Add an always-visible dashboard-header shortcut to the editor.
- Label the editor image as a refreshed still frame with its local refresh time.
- Rename the editor around ignored areas so configured rectangles cannot be mistaken for watched zones.
- Keep HTML entry points revalidating while preserving immutable caching for versioned assets.
- Remove motion-editor code from the live dashboard bundle and add dedicated-page regression coverage.

## 1.11.0 - 2026-07-16

- Read only upstream snapshot headers between brightness samples instead of transferring every JPEG.
- Stream proxied snapshots to the browser as they arrive rather than buffering the complete image first.
- Reduce gallery previews to a versioned 320 x 180 fast path while preserving original captures.
- Bound thumbnail generation to three workers and coalesce duplicate requests for the same frame.
- Warm static assets, status, service state, event metadata, and the newest gallery previews at startup.
- Cache compressed static representations instead of rereading and recompressing assets per request.
- Cache unchanged event responses for one minute and invalidate them as soon as the archive changes.
- Refresh expired brightness samples and service state outside interactive request threads.
- Prioritize the first visible gallery row and keep later previews at low browser priority.
- Keep expected browser disconnects out of policy, mask, and camera failure logs.
- Add regression coverage for streamed status probes, static representation caching, event invalidation, and thumbnail single-flight behavior.

## 1.10.0 - 2026-07-16

- Prioritize the live stream and defer below-the-fold dashboard work until it approaches view.
- Pause periodic API work in hidden tabs and refresh active sections when the page returns.
- Add bounded in-memory 480 x 270 event thumbnails without creating a second on-disk archive.
- Keep full-resolution captures for the review viewer and delay adjacent preloads until the selected image is ready.
- Append older event tiles in place and retain visible content while filters refresh.
- Cache archive metadata by directory generation and reuse the same scan for retention summaries.
- Batch four systemd status reads into one process and cache the result briefly.
- Downsample JPEGs in the decoder and reuse brightness metrics between 30-second samples.
- Gzip compress text and JSON responses and add conditional ETags for cacheable resources.
- Stream original event files instead of buffering every response in memory.
- Add request timeouts, single-flight polling guards, and backend timing response headers.
- Add performance and cache regression coverage across the dashboard stack.

## 1.9.0 - 2026-07-16

- Replace the basic capture popup with a responsive archive review viewer.
- Navigate newer and older captures with arrow controls or keyboard arrow keys.
- Load the next archive page automatically when review reaches the loaded boundary.
- Queue boundary paging behind any background archive refresh so navigation never drops a click.
- Preserve active range and activity-period filters while paging in the viewer.
- Show exact capture position, local timestamp, and file size.
- Add an original-file download action without creating a second copy on the Pi.
- Preload adjacent captures and expose clear loading and unavailable-image states.

## 1.8.0 - 2026-07-16

- Turn non-empty activity bars into keyboard-accessible archive filters.
- Query the exact selected hour, day, or adaptive all-time period on the server.
- Keep the full-range trend visible while highlighting the active period.
- Preserve capture pagination inside a selected period.
- Show selected-period counts alongside full-range and retained totals.
- Add a clear action that restores the complete range without changing range tabs.
- Validate paired, finite, positive, and ordered period boundaries at the API edge.

## 1.7.0 - 2026-07-16

- Add motion activity insights for the 24-hour, 7-day, and all-time archive ranges.
- Return deterministic count and size buckets from the existing event API scan.
- Use hourly, daily, or adaptive whole-day intervals without adding a database.
- Show capture total, active periods, peak period, and last activity above event history.
- Render a compact dependency-free activity chart with local-time labels and accessible summaries.
- Keep bucket totals reconciled with the selected range and retained archive policy.
- Preserve pagination behavior and avoid additional image or archive requests.

## 1.6.0 - 2026-07-16

- Add an optional system health watchdog for Pi power, CPU temperature, and archive storage.
- Require repeated unhealthy and healthy samples before declaring a transition.
- Baseline existing conditions silently on first startup to prevent migration alerts.
- Persist per-condition counters and queued Telegram delivery across service restarts.
- Retry failed delivery without losing subsequent health observations.
- Add a hardened systemd service with installer support and dashboard pause control.
- Show active conditions, pending delivery, and configured Telegram state in Monitoring.

## 1.5.0 - 2026-07-16

- Add optional Telegram alerts for automatic feed restart attempts and recoveries.
- Persist a notification cursor in recovery state for deduplication across service restarts.
- Treat existing recovery history as a migration baseline instead of replaying old incidents.
- Retry failed Telegram delivery on the next watchdog cycle without blocking camera recovery.
- Skip transient failed checks and user-requested restarts to keep operational alerts concise.
- Advance the cursor while alerts are disabled so enabling them never releases a backlog.
- Show active recovery Telegram alerts in the dashboard monitoring status.

## 1.4.0 - 2026-07-16

- Classify snapshots older than the configured recovery threshold as stale.
- Keep stale frames from reporting the dashboard and health endpoint as online.
- Retry interrupted browser streams with bounded exponential backoff.
- Reconnect immediately after camera or network recovery.
- Refresh the stream when a long-hidden dashboard tab becomes visible again.
- Keep Pause authoritative by suppressing all automatic reconnect attempts.
- Expose explicit viewer states for connecting, live, retrying, offline, and paused sessions.

## 1.3.0 - 2026-07-15

- Add deterministic archive retention limits by file count, age, and total size.
- Apply the same policy to saved photos and optional motion video clips.
- Preserve the newest contiguous set of captures when count or size limits are exceeded.
- Add a JSON cleanup command with a non-destructive `--dry-run` mode.
- Report current, pending, and projected archive usage through the event API.
- Show the active archive policy and cleanup state in the dashboard.
- Keep the existing 200-file limit while leaving new age and size limits disabled by default.

## 1.2.0 - 2026-07-15

- Read Raspberry Pi `vcgencmd get_throttled` hardware flags in addition to kernel logs.
- Distinguish active throttling, recently recovered undervoltage, and historical since-boot events.
- Expose current and historical power flags through the healthcheck and dashboard status API.
- Degrade dashboard health only for active or recent power problems, not sticky historical flags.
- Highlight the Power metric with a concise explanation of the current hardware state.
- Keep the legacy `undervoltage_seen` field for existing integrations.

## 1.1.0 - 2026-07-15

- Add a dashboard action for immediately restarting the configured camera feed service.
- Record feed failures, automatic and manual restarts, failed restarts, and recoveries.
- Keep a bounded 20-entry recovery history and show the five most recent incidents.
- Reload persisted watchdog state each cycle so dashboard actions remain authoritative.
- Preserve v1.0 recovery state files that do not contain incident history.

## 1.0.0 - 2026-07-14

- Add an automatic watchdog for unavailable, offline, empty, or stale camera snapshots.
- Require repeated failed checks and enforce a restart cooldown to prevent loops.
- Persist recovery health, failure counts, restart totals, and timestamps atomically.
- Add one-shot and continuous recovery CLI commands.
- Add a dedicated systemd service and installer support.
- Show feed-recovery health and a pause control in the private dashboard.
- Validate the configured stream service before any systemd restart.

## 0.9.0 - 2026-07-14

- Group nearby motion detections into one Telegram media album.
- Keep the first and latest representative frames while reporting the full burst count.
- Flush pending batches when the camera is unavailable or the service stops.
- Include batch counts, duration, captures, and private event links in Home Assistant payloads.
- Show the active batch window and photo limit in the private dashboard.
- Preserve immediate single-photo delivery when batching is disabled.

## 0.8.0 - 2026-07-14

- Add optional Home Assistant-compatible JSON webhooks for motion events.
- Include camera, host, timestamp, changed ratio, capture name, and private event links.
- Keep webhook failures isolated from Telegram delivery and capture retention.
- Continue webhook delivery during Telegram quiet hours for local automations.
- Add a secret-safe dashboard integration state and test action.
- Add a `send-webhook-test` CLI command without exposing the configured URL.

## 0.7.0 - 2026-07-14

- Add a pointer- and touch-friendly dashboard editor for ignored motion areas.
- Persist up to eight normalized mask regions atomically beside the alert policy.
- Exclude masked pixels from both motion-change counts and the active detection area.
- Reload updated masks in the running detector without restarting the service.
- Preserve the visible stream and archived captures while masks filter detection only.

## 0.6.1 - 2026-07-14

- Keep automatic exposure active in the C920 low-light recovery profile.
- Stop pinning low-light exposure and gain to values that can produce a black frame.
- Add regression coverage for safe low-light recovery controls.

## 0.6.0 - 2026-07-14

- Add timezone-aware Telegram quiet hours with overnight and all-day schedules.
- Add dashboard controls for enabling and editing the alert schedule.
- Continue archiving motion captures while quiet hours suppress notification delivery.
- Persist alert policy changes atomically and fail open when policy evaluation fails.
- Accept legacy `MOTION_*` environment names so standalone notifier deployments can migrate to the maintained monitor.

## 0.5.0 - 2026-07-14

- Add 24-hour, 7-day, and all-time motion-history filters.
- Add paginated access to older retained captures.
- Report in-range and retained event counts plus archive storage usage.
- Add validated event API range, limit, and cursor parameters.
- Keep longer event browsing sessions stable during periodic dashboard refreshes.

## 0.4.0 - 2026-07-14

- Add live systemd state for motion alerts and automatic exposure recovery.
- Add guarded dashboard toggles to pause or resume either service.
- Support custom motion and exposure service names through environment settings.
- Show the installed app version beside the dashboard title.
- Validate service names and restrict dashboard actions to the two configured roles.

## 0.3.0 - 2026-07-14

- Add camera profile controls to the private dashboard.
- Add live sliders for brightness, contrast, saturation, gain, sharpness, exposure, and white balance.
- Add automatic exposure and white-balance toggles with dependent-control handling.
- Add allowlisted, range-validated camera control APIs with same-origin write protection.
- Detect the active camera profile from current V4L2 values, including device rounding tolerance.
- Cap dashboard gain and exposure controls below the C920's extreme white-frame range.

## 0.2.0 - 2026-07-14

- Add a responsive private dashboard with live camera controls and recent motion captures.
- Preserve `/stream` and `/snapshot` through a same-origin dashboard proxy.
- Add JSON status and health endpoints with frame, exposure, power, temperature, uptime, and storage signals.
- Add low-disk-space reporting to the CLI health check.
- Add a dashboard systemd service and update Tailscale Serve setup for private HTTPS access.
- Use the field-tested moderate C920 low-light profile and recovery thresholds.

## 0.1.0 - 2026-06-30

- Initial USB camera stream, Telegram motion alerts, camera profiles, health checks, and exposure watchdog.
