# Dashboard Performance

Pi Camera Sentinel keeps the live camera on the shortest path and moves secondary work out of its way. The implementation stays dependency-light and is designed for Raspberry Pi hardware reached through an encrypted private network.

## Browser Fast Path

- The live stream and core health status start immediately.
- Monitoring loads when it approaches the viewport; motion masks, camera tuning, and event history initialize independently when they are near view.
- Background polling stops while the page is hidden and refreshes initialized sections when the page returns.
- API requests have a fixed timeout and periodic status requests cannot overlap themselves.
- Event filters retain the current tiles while loading, and older pages append without rebuilding existing image elements.
- The selected full-resolution capture loads before adjacent viewer images are preloaded during browser idle time.

## Transfer And Cache Behavior

The event API exposes a 480 x 270 thumbnail URL alongside every original capture URL. Thumbnails are generated on demand, held in a 256-entry process-memory cache, and never written to the archive or filesystem. The review viewer and download action continue to use the original retained file.

Versioned JavaScript and CSS, original event files, and thumbnail URLs use private or public immutable caching as appropriate. Index HTML revalidates with an ETag. Text, JavaScript, CSS, and JSON responses use gzip when the client advertises support. Dynamic API responses remain `no-store`.

## Pi Fast Path

- One directory-generation cache supplies event pages, activity summaries, and retention planning without repeated file scans.
- One batched `systemctl show` process reads all monitored services; a short cache absorbs duplicate clients.
- Status brightness sampling asks the JPEG decoder for a 320 x 180 grayscale draft, then reuses the metric for 30 seconds while reading fresh feed headers.
- Original event responses stream in 64 KB chunks rather than reading the entire file into each request thread.
- Status, archive, and service caches are guarded for concurrent dashboard clients.

Every response includes a same-origin `Server-Timing` measurement named `app`, making backend time visible in browser developer tools and automated performance checks.

## Raspberry Pi 3B Results

Representative localhost measurements on the project Pi, comparing v1.9.0 with v1.10.0:

| Path | v1.9.0 | v1.10.0 |
| --- | ---: | ---: |
| Routine status response | 112 ms | 34 ms |
| Service status response | 350 ms | 184 ms |
| Cached duplicate service response | 350 ms | 5 ms |
| Event history response | 110 ms | 17 ms |
| First 12 gallery images | 3.95 MB | 206 KB |
| Dashboard JavaScript transfer | 69.3 KB | 16.1 KB |
| Dashboard HTML transfer | 20.9 KB | 3.7 KB |

The thumbnail path reduces the initial gallery image transfer by 94.8%. Measurements vary with camera, storage, CPU, and network conditions; the important behavior is that routine polling avoids repeated device probes and archive scans.
