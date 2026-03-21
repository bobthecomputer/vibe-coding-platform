# Desktop Performance Report (M1)

This report tracks the M1 overlay budgets from day one instrumentation.

## Metrics captured

- Cold start time (`cold_start_ms`)
- Hold-hotkey to overlay-open latency (`last_hotkey_latency_ms` and rolling average)
- Idle RAM snapshot (`idle_ram_mb`)

## How to sample

1. Start the app: `npm run tauri:dev`
2. Trigger overlay open/close with the configured hold key (`Space` or fallback `Ctrl+Space`).
3. Open tray menu -> **Performance snapshot** or click **Perf** in the overlay.
4. Read current values in the overlay panel and in app logs.

## Latest local sample

Not captured in this commit (code instrumentation only).

## Budget targets

- Hotkey-to-overlay perceived latency: `< 80ms`
- Idle RAM: `< 80MB` (stretch `< 50MB`)
- Idle CPU: near-zero
