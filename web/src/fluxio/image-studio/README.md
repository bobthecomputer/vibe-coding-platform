# Fluxio Image Studio

This folder owns the standalone image playground surface.

## Integration point

Import and mount `ImageStudioPlayground` from `web/src/fluxio/image-studio/ImageStudioPlayground.jsx` wherever the shell routes the image workspace:

```jsx
import { ImageStudioPlayground } from "./image-studio/ImageStudioPlayground.jsx";
```

The component persists its image project through `imagePlaygroundState.js` and stores route/reference session metadata under `fluxio.image_studio.session.v1`.

## Scope

- Builds prompt, provider route, reference asset, mask, layer, history, and proof artifact state.
- Shows a six-step image breakdown workflow for source intake, region planning, matte quality, prompt intent, review markup, and provider routing.
- Can call the shell-provided `image_playground_operation_command` only when capability metadata says a real provider run is available, then ingests the returned receipt, manifest, image URL, and layer into local history.
- Runs local browser-side chroma-key matte previews against attached images, served artifacts, or the clearly labeled synthetic green-screen sample so operators can inspect transparent output, mask output, removed pixels, and soft-edge coverage before provider handoff.
- Checks local artifact backend health and labels served-artifact proof sources as offline when `/health` is unreachable.
- Produces a provider request draft through `buildImageStudioRequestDraft`.
- Produces `proofReview` metadata that reports draft validity, preview layer counts, mask coverage, annotation counts, reference counts, chroma QA checklist, and real artifact-history coverage.
- Renders annotation pins and rectangles only when they exist in project state; it does not invent proof marks.
- Does not call an image provider, create fake generated images, treat local matte previews as provider output, or store secrets.
- When capability metadata reports a blocked connector, the run action stays disabled and the provider route panel remains the source of truth.
- Keeps provider execution blocked until a real connector supplies the run action and artifact receipt.
- Tracks the OpenAI `gpt-image-2` route as connector-required. Official source links are stored in route metadata, but the local UI still reports draft handoff only until a real provider receipt, output manifest, and artifact hash exist.
