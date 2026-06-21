from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from control_route_interaction_smoke import (
    CHROME,
    ROOT,
    Cdp,
    DevToolsSocket,
    assert_current_control_shell,
    free_port,
    wait_for_control_shell,
    wait_for_devtools,
    wait_for_ready,
)


OUT_DIR = Path(os.environ.get("FLUXIO_PROOF_OUT_DIR", ROOT / "artifacts" / "pr98-voice-dictation-safety"))
CHECK_PATH = OUT_DIR / "voice-control-checkpoint-check.json"
URL = os.environ.get(
    "FLUXIO_CONTROL_URL",
    "http://127.0.0.1:1420/control?preview-control=1&fixture=live_review&mode=agent&surface=agent",
)


def capture(cdp: Cdp, path: Path) -> None:
    result = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise RuntimeError("Screenshot capture failed for voice control checkpoint.")
    path.write_bytes(base64.b64decode(data))


def click_button(cdp: Cdp, label: str) -> bool:
    return bool(
        cdp.eval(
            f"""
            (() => {{
              const button = Array.from(document.querySelectorAll("button"))
                .find(item => (item.textContent || "").trim() === {json.dumps(label)});
              if (!button || button.disabled) return false;
              button.click();
              return true;
            }})()
            """
        )
    )


def set_agent_composer(cdp: Cdp, value: str) -> bool:
    return bool(
        cdp.eval(
            f"""
            (() => {{
              const field =
                document.querySelector('textarea[aria-label="Agent message composer"]') ||
                document.querySelector('#thread-note') ||
                document.querySelector('.agent-composer textarea');
              if (!field) return false;
              const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
              if (setter) setter.call(field, {json.dumps(value)});
              else field.value = {json.dumps(value)};
              field.dispatchEvent(new Event("input", {{ bubbles: true }}));
              return true;
            }})()
            """
        )
    )


def set_voice_confirmation_text(cdp: Cdp, value: str) -> bool:
    return bool(
        cdp.eval(
            f"""
            (() => {{
              const field = document.querySelector('textarea[aria-label="Voice confirmation outgoing text"]');
              if (!field || field.disabled) return false;
              const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
              if (setter) setter.call(field, {json.dumps(value)});
              else field.value = {json.dumps(value)};
              field.dispatchEvent(new Event("input", {{ bubbles: true }}));
              return true;
            }})()
            """
        )
    )


def press_voice_shortcut(cdp: Cdp, key: str, *, ctrl: bool = False, shift: bool = False) -> bool:
    return bool(
        cdp.eval(
            f"""
            (() => {{
              const panel = document.querySelector(".fluxio-voice-panel");
              if (!panel) return false;
              panel.focus();
              const event = new KeyboardEvent("keydown", {{
                key: {json.dumps(key)},
                ctrlKey: {str(ctrl).lower()},
                shiftKey: {str(shift).lower()},
                bubbles: true,
                cancelable: true
              }});
              panel.dispatchEvent(event);
              return event.defaultPrevented;
            }})()
            """
        )
    )


def switch_surface(cdp: Cdp, label: str) -> bool:
    clicked = click_button(cdp, label)
    if clicked:
        time.sleep(0.65)
    return clicked


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="fluxio-voice-checkpoint-cdp-")
    process = subprocess.Popen(
        [
            str(CHROME),
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile.name}",
            "--window-size=1440,1180",
            "about:blank",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ws: DevToolsSocket | None = None
    try:
        tabs = wait_for_devtools(port)
        ws = DevToolsSocket(str(tabs[0]["webSocketDebuggerUrl"]))
        cdp = Cdp(ws)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send("Page.navigate", {"url": URL})
        time.sleep(1.5)
        wait_for_ready(cdp)
        wait_for_control_shell(cdp)
        deadline = time.time() + 12
        while time.time() < deadline:
            if cdp.eval('Boolean(document.querySelector(".voice-control-checkpoint"))'):
                break
            cdp.eval("window.scrollBy(0, 360)")
            time.sleep(0.35)
        cdp.eval(
            """
            document.querySelector(".voice-control-checkpoint")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.45)
        assert_current_control_shell(cdp)
        initial_composer_set = set_agent_composer(cdp, "Continue the PR stack and attach proof.")
        time.sleep(0.25)
        checkpoint_text = str(cdp.eval('document.querySelector(".voice-control-checkpoint")?.innerText || ""'))
        opened_review = click_button(cdp, "Open voice review")
        time.sleep(0.8)
        wait_for_control_shell(cdp)
        cdp.eval(
            """
            (() => {
              const field = document.querySelector("#fluxio-voice-manual-dictation");
              if (!field) return false;
              const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
              if (setter) setter.call(field, "send message");
              else field.value = "send message";
              field.dispatchEvent(new Event("input", { bubbles: true }));
              return true;
            })()
            """
        )
        time.sleep(0.25)
        added_dictation = click_button(cdp, "Add to review")
        time.sleep(0.8)
        cdp.eval(
            """
            document.querySelector(".fluxio-voice-mode-checkpoint")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.45)
        run_disabled = bool(
            cdp.eval(
                """
                (() => {
                  const run = Array.from(document.querySelectorAll("button"))
                    .find(item => (item.textContent || "").trim() === "Run");
                  return Boolean(run?.disabled);
                })()
                """
            )
        )
        mode_switch_found = bool(cdp.eval('Boolean(document.querySelector(".fluxio-voice-mode-switch"))'))
        mode_checkpoint_found = bool(cdp.eval('Boolean(document.querySelector(".fluxio-voice-mode-checkpoint"))'))
        review_mode_checkpoint_text = str(cdp.eval('document.querySelector(".fluxio-voice-mode-checkpoint")?.innerText || ""'))
        marked_reviewed = click_button(cdp, "Mark reviewed")
        time.sleep(0.45)
        command_mode_selected = click_button(cdp, "Command")
        time.sleep(0.35)
        run_shortcut_for_confirmation = press_voice_shortcut(cdp, "Enter", ctrl=True)
        time.sleep(0.65)
        confirmation_target_found = bool(cdp.eval('Boolean(document.querySelector(".fluxio-voice-confirm-target"))'))
        cancel_found = bool(
            cdp.eval(
                """
                Boolean(Array.from(document.querySelectorAll("button"))
                  .find(item => (item.textContent || "").trim() === "Cancel"))
                """
            )
        )
        confirm_target_text = str(cdp.eval('document.querySelector(".fluxio-voice-confirm-target")?.innerText || ""'))
        confirmation_target_draft_before_mutation = str(
            cdp.eval('document.querySelector("textarea[aria-label=\\"Voice confirmation outgoing text\\"]")?.value || ""')
        )
        composer_mutated_after_review = set_voice_confirmation_text(cdp, "Changed after the voice review target was created.")
        agent_surface_reopened_for_mutation = False
        voice_surface_reopened_after_mutation = False
        if not composer_mutated_after_review:
            agent_surface_reopened_for_mutation = switch_surface(cdp, "Agent")
            composer_mutated_after_review = set_agent_composer(cdp, "Changed after the voice review target was created.")
            voice_surface_reopened_after_mutation = switch_surface(cdp, "Voice")
            cdp.eval(
                """
                document.querySelector(".fluxio-voice-confirm-target")
                  ?.scrollIntoView({ block: "center", inline: "nearest" });
                """
            )
        time.sleep(0.35)
        confirm_clicked_after_mutation = click_button(cdp, "Confirm")
        time.sleep(0.9)
        post_confirm_text = str(cdp.eval('document.body.innerText || ""'))
        cancellation_found = "Voice send canceled because the composer changed after review" in post_confirm_text
        handler_outcome_found = bool(cdp.eval('Boolean(document.querySelector(".fluxio-voice-handler-outcome"))'))
        pending_confirmation_cleared = not bool(cdp.eval('Boolean(document.querySelector(".fluxio-voice-confirm-target"))'))
        cdp.eval(
            """
            document.querySelector(".fluxio-voice-handler-outcome")
              ?.scrollIntoView({ block: "center", inline: "nearest" });
            """
        )
        time.sleep(0.45)
        body_text = str(cdp.eval('document.body.innerText || ""'))
        visible_text = (
            f"{checkpoint_text}\n{review_mode_checkpoint_text}\n{body_text}\n"
            f"{confirm_target_text}\n{confirmation_target_draft_before_mutation}\n{post_confirm_text}"
        )
        screenshot_path = OUT_DIR / "voice-control-checkpoint.png"
        capture(cdp, screenshot_path)
        expected = [
            "VOICE CONTROL CHECKPOINT",
            "Open voice review",
            "Mode:",
            "Unknown confidence:",
            "System dictation",
            "MODE CHECKPOINT",
            "Dictation mode",
            "hold_for_mode_review",
            "CONFIRMATION TARGET",
            "Continue the PR stack and attach proof.",
            "Voice send canceled because the composer changed after review",
            "Handler outcome: Canceled",
            "composer_changed_after_review",
        ]
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "url": URL,
            "browser": str(CHROME),
            "screenshotPath": str(screenshot_path.resolve()),
            "initialComposerSet": initial_composer_set,
            "openedReview": opened_review,
            "addedDictation": added_dictation,
            "runDisabledAfterRiskyDictation": run_disabled,
            "modeSwitchFound": mode_switch_found,
            "modeCheckpointFound": mode_checkpoint_found,
            "markedReviewed": marked_reviewed,
            "commandModeSelected": command_mode_selected,
            "runShortcutForConfirmation": run_shortcut_for_confirmation,
            "confirmationTargetFound": confirmation_target_found,
            "cancelFound": cancel_found,
            "agentSurfaceReopenedForMutation": agent_surface_reopened_for_mutation,
            "voiceSurfaceReopenedAfterMutation": voice_surface_reopened_after_mutation,
            "composerMutatedAfterReview": composer_mutated_after_review,
            "confirmClickedAfterMutation": confirm_clicked_after_mutation,
            "cancellationFound": cancellation_found,
            "handlerOutcomeFound": handler_outcome_found,
            "pendingConfirmationCleared": pending_confirmation_cleared,
            "reviewModeCheckpointText": review_mode_checkpoint_text,
            "confirmationTargetText": confirm_target_text,
            "confirmationTargetDraftBeforeMutation": confirmation_target_draft_before_mutation,
            "postConfirmText": post_confirm_text,
            "checkpointText": checkpoint_text,
            "expectedFragments": expected,
            "missingFragments": [fragment for fragment in expected if fragment not in visible_text],
        }
        report["passed"] = (
            not report["missingFragments"]
            and initial_composer_set
            and opened_review
            and added_dictation
            and run_disabled
            and mode_switch_found
            and mode_checkpoint_found
            and marked_reviewed
            and command_mode_selected
            and run_shortcut_for_confirmation
            and confirmation_target_found
            and cancel_found
            and composer_mutated_after_review
            and confirm_clicked_after_mutation
            and cancellation_found
            and handler_outcome_found
            and pending_confirmation_cleared
        )
        CHECK_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    finally:
        if ws:
            ws.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
