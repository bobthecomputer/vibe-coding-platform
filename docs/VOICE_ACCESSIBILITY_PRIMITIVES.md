# Voice Accessibility Primitives

Fluxio now has an isolated voice toolkit under `web/src/fluxio/voice/`. It does not claim live dictation by itself. It checks for either a browser speech API or a local `window.__FLUXIO_VOICE_BRIDGE__` before enabling microphone capture.

## What it provides

- Transcript buffer: stores final and interim dictation segments, trims old entries, tracks low-confidence text, and tells the UI when review is needed.
- Command grammar: turns phrases such as `open settings`, `show proof`, `send message`, and `approve request` into structured actions.
- Recovery copy: gives plain-language messages for unsupported browsers, denied microphone permission, unclear speech, and unknown commands.
- Keyboard parity labels: builds labels that announce the pointer action, keyboard shortcut, and matching voice phrase.
- Reduced-motion affordance: exposes motion attributes and CSS that keep status changes readable without continuous animation.
- Optional React controller and panel: `useVoiceInteractionController` and `VoiceCommandPanel` can be mounted near the composer or top bar when the shell owner is ready.

## Integration Sketch

```jsx
import { VoiceCommandPanel } from "./voice/index.js";

function ShellVoiceSlot({ dispatchVoiceAction }) {
  return <VoiceCommandPanel onVoiceCommand={dispatchVoiceAction} />;
}
```

The shell integration should map structured voice actions to existing UI handlers:

- `surface.open` with `{ surface: "settings" }` should use the same path as the Settings tab.
- `composer.send` should use the same submit path as `Ctrl+Enter` and should keep its confirmation prompt.
- `approval.resolve` must keep the existing approval guard and should never run from a single unclear phrase.
- `voice.clearTranscript` clears only the local transcript buffer.

## Support Rules

Do not show "live speech recognition ready" until `detectVoiceInputSupport()` returns `supported: true`.

If support is missing, the visible copy should say:

`Live dictation is not available in this browser yet. Use OS dictation, paste text, or connect the local voice bridge.`

If support exists, the first start still requires microphone permission. The UI should keep a keyboard path for every voice path.

