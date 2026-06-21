# Image / Vision / UI Self-Repair Proof

- Generated: 2026-06-21T13:45:21.145527+00:00
- Preferred route: zai/glm-5.2 through opencode
- Selected route: opencode/big-pickle
- Fallback reason: OpenCode provider discovery reported no Z.AI/GLM provider on this machine, no ZAI_API_KEY/Z_AI_API_KEY/OpenRouter/Together GLM credential is present, the listed OpenCode GLM fallback is rejected at call time, and OpenAI fallbacks fail token refresh locally. Selected opencode/big-pickle as the closest working OpenCode coding route, then fed it the local screenshot-breakdown skill output instead of pretending it saw the image.
- Screenshot: C:\Users\paul\AppData\Local\Temp\codex-clipboard-4588fa50-b17b-44e1-bd56-e29d461f15f8.png

## Skills
- browser_use_local_inspection: 
- leon_lin_design_taste: 
- image_vision_breakdown: vision_breakdown.json, vision_breakdown.md, before screenshot
- ui_self_repair_planner: ui_repair_plan.json, runtime_compartment_proof
- self_repair_verifier: self_repair_verifier.json, after screenshot

## Artifacts
- routeProof: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\route_proof.json
- visionBreakdown: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\vision_breakdown.json
- uiRepairPlan: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\ui_repair_plan.json
- markdownSummary: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\SELF_REPAIR_PROOF.md
- beforeScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\before-image-studio.png
- afterDesktopScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-image-studio-desktop.png
- afterMobileScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-image-studio-mobile.png
- reviewCleanupDesktopScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-review-cleanup-desktop.png
- reviewCleanupMobileScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-review-cleanup-mobile.png
- generatorCleanupDesktopScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-generator-cleanup-desktop.png
- generatorCleanupMobileScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-generator-cleanup-mobile.png
- realGeneratedImageDesktopScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-real-generated-image-desktop.png
- realGeneratedImageMobileScreenshot: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\after-real-generated-image-mobile.png
- displayedGeneratedImageAsset: C:\Users\paul\projects\vibe-coding-platform\web\public\image-studio\generated-coastal-retreat.png
- verifier: C:\Users\paul\projects\vibe-coding-platform\artifacts\pr112-image-vision-ui-self-repair\self_repair_verifier.json

## Verification
- Desktop preview smoke: passed, active proof chain visible.
- Mobile preview smoke: passed, active proof chain visible.
- Review cleanup desktop preview smoke: passed, menu-only top row and collapsed sidebar route rendered.
- Review cleanup mobile preview smoke: passed, compact controls retained.
- Generator cleanup desktop preview smoke: passed; normal UI shows prompt, generator controls, collapsed rail sections, and no proof checklist/status-card clutter.
- Generator cleanup mobile preview smoke: passed; prompt and Generate action are visible in the mobile generator flow.
- Real generated image desktop preview smoke: passed; the canvas displays `Generated coastal retreat image` from a real generated bitmap asset.
- Real generated image mobile preview smoke: passed.
- Real image generation status: no fresh live provider run was faked. The default canvas now displays a real generated reference asset, while live generation still shows `Connect image provider` / `live generation off` until an actual connector returns a provider receipt and artifact.
- Python tests: `tests/test_web_backend.py tests/test_desktop_ui_contract.py` passed.
- Frontend build: `npm run frontend:build` passed.
