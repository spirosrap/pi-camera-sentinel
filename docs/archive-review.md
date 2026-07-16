# Archive Review Viewer

Selecting any retained capture opens the archive review viewer. It keeps the current 24-hour, 7-day, all-time, or activity-period filter active while moving through that result set.

## Controls

- Use the on-screen left and right arrows to move to the previous or next capture.
- Use the keyboard left and right arrow keys for the same navigation.
- Use the download action to save the original retained JPEG.
- Close the viewer with its close action, the Escape key, or the backdrop.

The footer shows the capture's local timestamp and file size. The header reports its position in the complete filtered result, not only the number currently loaded in the browser.

## Seamless Paging

Event history initially loads 12 captures. When review advances past the last loaded capture and the API has an older-page cursor, the dashboard requests the next page and moves directly to its first capture. Existing window, period_start, and period_end filters remain part of that request.

The viewer preloads the adjacent retained images for smoother navigation. It never creates derivative files or a second archive on the Pi. If retention removes an image during an open review, the viewer reports that the capture is unavailable instead of changing archive state.
