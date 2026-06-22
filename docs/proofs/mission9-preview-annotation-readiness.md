# Mission 9 Preview Annotation Readiness

Status: complete locally, PR127 opened as draft: https://github.com/bobthecomputer/vibe-coding-platform/pull/127

## Scope

Mission 9 finishes a focused Preview/browser/app execution and annotation readiness slice. The goal is to prove the Workbench can expose a real preview capture loop, route the finding through Hermes-first runtime metadata, and attach screenshot/DOM/check proof instead of showing fake browser panels.

## Route And Runtime

- App route: `http://127.0.0.1:5185/control?preview-control=1&fixture=live_review&mode=builder&surface=workbench&targetUrl=http%3A%2F%2F127.0.0.1%3A5185%2Fcontrol%3Fpreview-control%3D1%26fixture%3Dlive_review%26surface%3Dbuilder&previewLabel=Local%20Builder%20fixture`
- Backend command: `get_preview_annotation_readiness_command`
- Schema: `fluxio.preview_annotation_readiness.v1`
- Primary runtime lane: `hermes`
- Fallback lanes: `openclaw`, `opencode`, `browser-cdp`
- Backend artifact: `.agent_control/preview_annotation_readiness/mission9-preview-actual.json`

## Skills Used

- `preview_screenshot_breakdown`
- `ui_taste_review`
- `preview_annotation_router`
- `proof_attachment_verifier`

The backend command records each skill with input, output, route, and artifact metadata.

## Before / After Proof

- Before screenshot: `artifacts/mission9-preview-annotation/before-workbench-preview-annotation-marker.png`
- After screenshot: `artifacts/mission9-preview-annotation/after-workbench-preview-annotation-inapp.png`
- In-app browser facts: `artifacts/mission9-preview-annotation/after-workbench-preview-annotation-inapp.facts.json`
- Visual smoke screenshot: `artifacts/mission9-preview-annotation/mission9-preview-annotation-workbench.png`
- Visual smoke DOM: `artifacts/mission9-preview-annotation/mission9-preview-annotation-workbench.html`
- Visual smoke check: `artifacts/mission9-preview-annotation/mission9-preview-annotation-workbench-check.json`
- Backend command result: `artifacts/mission9-preview-annotation/preview-annotation-readiness-command-result.json`

## What Changed

- Workbench now renders a compact `Preview proof loop` beside the real local preview/browser surface.
- The capture action stays in Workbench when launched from Workbench and calls the backend readiness command.
- The readiness contract is passed through `referenceWorkbenchState`, so the real `FluxioWorkbenchSurface` receives it.
- The backend command verifies screenshot, DOM, smoke-check, and visual finding inputs before writing the proof artifact.
- The UI keeps the schema as a data attribute and proof details in artifacts instead of adding visible proof clutter.

## Verification

- `python -m pytest tests/test_web_backend.py tests/test_desktop_ui_contract.py -q` -> 150 passed.
- `npm run frontend:build` -> passed with the existing large chunk warning.
- `git diff --check` -> passed with line-ending warnings only.
- `python scripts/control_route_visual_smoke.py --url "<route above>" --out-dir artifacts/mission9-preview-annotation --name mission9-preview-annotation-workbench --expect "Preview proof loop" --expect "Capture preview proof"` -> passed.
- In-app browser proof confirmed `hasPreviewAnnotationContract=true`, `primaryLane=hermes`, `schema=fluxio.preview_annotation_readiness.v1`, and enabled `Capture preview proof`.
