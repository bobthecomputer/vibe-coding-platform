# Mission 10 - Harness Benchmark Board

## Result

Mission 10 adds a Hermes-first harness benchmark board to Settings > Runtimes & Rooms. The board compares model plus harness combinations, keeps OpenClaw/OpenCode visible as fallback or specialist lanes, and writes a real backend proof artifact before claiming readiness.

## Runtime Proof

- Command: `get_harness_benchmark_board_command`
- Schema: `fluxio.harness_benchmark_board.v1`
- Primary lane: `hermes`
- Fallback lanes: `openclaw`, `opencode`, `local-model`
- Local result: `ready_for_decision_board`
- Proof artifact: `.agent_control/harness_benchmark_board/mission10-local-proof.json`
- Copied command result: `artifacts/mission10-harness-benchmark/harness-benchmark-board-command-result.json`

Actual route discovery from the local proof:

- Hermes available through WSL: `true`
- Native Hermes command visible on Windows PATH: `false`
- Fallback runtime available: `true`
- Matrix rows: 4

## Screenshots

- Before: `artifacts/mission10-harness-benchmark/before-runtimes.png`
- After: `artifacts/mission10-harness-benchmark/after-runtimes-harness-board.png`

Before, the Runtimes screen only exposed harness chips, fusion readiness, and raw runtime rows. After, it includes `Harness benchmark board`, `Capture benchmark proof`, Hermes production lane, OpenClaw fallback lane, GLM/OpenCode specialist lane, primary/fallback receipts, and honest evidence state.

## Verification

- `python -m pytest tests/test_web_backend.py::FluxioWebBackendTests::test_harness_benchmark_board_command_writes_hermes_first_contract -q`
- `python -m pytest tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_settings_runtime_surface_exposes_harness_benchmark_board -q`
- `python -m pytest tests/test_web_backend.py::FluxioWebBackendTests::test_preview_annotation_readiness_command_writes_capture_contract_artifact tests/test_web_backend.py::FluxioWebBackendTests::test_harness_benchmark_board_command_writes_hermes_first_contract tests/test_desktop_ui_contract.py::DesktopUiContractTests::test_settings_runtime_surface_exposes_harness_benchmark_board -q`
- `python -m pytest tests/test_web_backend.py tests/test_desktop_ui_contract.py tests/test_fluxio_harness.py -q` -> 175 passed
- `npm run frontend:build`
- `python scripts/control_route_visual_smoke.py --url "http://127.0.0.1:5188/control?preview-control=1&fixture=live_review&surface=settings&settingsTab=runtimes" --out-dir artifacts/mission10-harness-benchmark --name after-runtimes-harness-board --width 1440 --height 1000 --expect "Harness benchmark board" --expect "Capture benchmark proof" --expect "Hermes + Syntelos Hybrid" --expect "OpenClaw + Syntelos Hybrid"`

## Remaining

The board is now ready for practical decisions, but it still needs accumulated live benchmark samples per task class before changing production routing away from Hermes + Syntelos Hybrid.
