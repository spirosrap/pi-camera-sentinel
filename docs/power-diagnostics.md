# Power Diagnostics

Pi Camera Sentinel reads the Raspberry Pi firmware throttling register with:

```bash
vcgencmd get_throttled
```

The value contains separate current and since-boot flags. For example, `0x50005` means undervoltage and CPU throttling are active now, and both have occurred since boot.

## Dashboard States

- **Undervoltage now**: the current undervoltage bit is set. Check the 5V supply, cable, connectors, and USB camera load.
- **Throttling now**: another current hardware limit is set, such as frequency capping or a temperature limit.
- **Recovered**: a recent kernel undervoltage warning exists, but no current hardware flag is active.
- **Past issue**: a sticky since-boot flag is set, but there is no current or recent problem.
- **Stable**: Raspberry Pi hardware telemetry is available and no throttling flags are set.
- **Unknown**: firmware telemetry is unavailable and kernel logs do not provide a current answer.

Active, recovered, and recent states make dashboard health degraded. A historical state remains visible in the Power metric but does not degrade an otherwise healthy camera.

## Status API

`/api/status` exposes the structured state under `system.power`:

```json
{
  "state": "active",
  "raw_value": "0x50005",
  "current_issues": ["Undervoltage", "CPU throttled"],
  "occurred_issues": ["Undervoltage", "CPU throttled"],
  "under_voltage_now": true,
  "throttled_now": true
}
```

The full object also includes frequency-cap and soft-temperature-limit flags for both current and occurred states. `system.undervoltage_seen` remains available for integrations written before v1.2.

Firmware flags are the current source of truth. The two-hour kernel log check is retained as a fallback and to identify a recently recovered warning.
