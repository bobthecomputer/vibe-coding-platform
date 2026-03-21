# Night Mode Scheduler

Night mode runs safe maintenance cycles while the app remains in background mode.

## Defaults

- Enabled: `true`
- Window: `01:00` to `06:00` local time
- Autopilot: `false`

## Safe tasks

- Workspace metadata indexing proposal
- Pending question/approval summarization
- Patch plan proposal generation

No destructive actions are executed in night mode.

## Commands

- `get_night_mode_config`
- `configure_night_mode`
- `run_night_mode_now`
- `get_last_night_mode_report`

## Events

- `night-mode://report` emits structured report payloads.
