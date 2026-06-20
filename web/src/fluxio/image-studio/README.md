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
- Produces a provider request draft through `buildImageStudioRequestDraft`.
- Does not call an image provider, create fake generated images, or store secrets.
- Keeps provider execution blocked until a real connector supplies the run action and artifact receipt.
