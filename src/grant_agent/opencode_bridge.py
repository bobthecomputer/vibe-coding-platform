from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .subprocess_utils import hidden_windows_subprocess_kwargs
except ImportError:  # pragma: no cover - direct script fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from grant_agent.subprocess_utils import hidden_windows_subprocess_kwargs

STRUCTURED_EVENT_PREFIX = "FLUXIO_EVENT:"


def emit_event(
    *,
    kind: str,
    message: str,
    status: str = "running",
    data: dict[str, Any] | None = None,
) -> None:
    payload = {
        "kind": kind,
        "message": message,
        "status": status,
        "data": data or {},
    }
    print(f"{STRUCTURED_EVENT_PREFIX}{json.dumps(payload, ensure_ascii=True)}", flush=True)


def _event_text(payload: dict[str, Any]) -> str:
    part = payload.get("part")
    if isinstance(part, dict) and str(part.get("type") or "").lower() == "text":
        return str(part.get("text") or "").strip()
    if str(payload.get("type") or "").lower() == "text":
        value = payload.get("text")
        if isinstance(value, str):
            return value.strip()
    return ""


def _event_session_id(payload: dict[str, Any]) -> str:
    value = payload.get("sessionID") or payload.get("sessionId")
    if value:
        return str(value)
    part = payload.get("part")
    if isinstance(part, dict):
        value = part.get("sessionID") or part.get("sessionId")
        if value:
            return str(value)
    return ""


def _compact(value: object, *, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def run_opencode(
    *,
    opencode_command: str,
    prompt: str,
    model: str = "",
    title: str = "",
    variant: str = "",
) -> int:
    args = [opencode_command, "run", "--format", "json"]
    if model:
        args.extend(["--model", model])
    if title:
        args.extend(["--title", title])
    if variant:
        args.extend(["--variant", variant])
    args.append(prompt)

    emit_event(
        kind="runtime.launch",
        message=f"OpenCode run started{f' with {model}' if model else ''}.",
        status="running",
        data={
            "sourceKind": "real-runtime-output",
            "captureMode": "fresh-runtime-command",
            "model": model,
            "runtime": "opencode",
        },
    )
    child = subprocess.Popen(  # noqa: S603
        _popen_args(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **hidden_windows_subprocess_kwargs(),
    )

    text_parts: list[str] = []
    session_id = ""
    raw_tail: list[str] = []
    if child.stdout is not None:
        for raw_line in iter(child.stdout.readline, ""):
            line = raw_line.strip()
            if not line:
                continue
            raw_tail.append(line)
            raw_tail = raw_tail[-6:]
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                emit_event(
                    kind="runtime.output",
                    message=_compact(line),
                    status="running",
                    data={
                        "sourceKind": "real-runtime-output",
                        "captureMode": "fresh-runtime-command",
                        "model": model,
                        "runtime": "opencode",
                    },
                )
                continue
            if isinstance(payload, dict):
                event_session_id = _event_session_id(payload)
                if event_session_id:
                    session_id = event_session_id
                text = _event_text(payload)
                if text:
                    text_parts.append(text)

    return_code = child.wait()
    assistant_text = "\n".join(part for part in text_parts if part).strip()
    event_data = {
        "sourceKind": "real-runtime-output",
        "captureMode": "fresh-runtime-command",
        "runtime": "opencode",
        "model": model,
        "externalRuntimeSessionId": session_id,
    }
    if assistant_text:
        emit_event(
            kind="runtime.model_message",
            message=assistant_text,
            status="running",
            data=event_data,
        )
    elif raw_tail:
        emit_event(
            kind="runtime.output",
            message=_compact(" | ".join(raw_tail), limit=900),
            status="failed" if return_code else "completed",
            data=event_data,
        )
    emit_event(
        kind="runtime.finished" if return_code == 0 else "runtime.failed",
        message=(
            "OpenCode run completed."
            if return_code == 0
            else f"OpenCode run failed with exit code {return_code}."
        ),
        status="running" if return_code == 0 else "failed",
        data=event_data,
    )
    return return_code


def _popen_args(args: list[str]) -> list[str]:
    if not args:
        return args
    resolved = shutil.which(args[0]) or args[0]
    launch_args = [resolved, *args[1:]]
    if os.name == "nt" and Path(resolved).suffix.lower() in {".bat", ".cmd"}:
        return ["cmd", "/d", "/s", "/c", subprocess.list2cmdline(launch_args)]
    return launch_args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bridge OpenCode JSON output into Fluxio runtime events.")
    parser.add_argument("--opencode-command", default="opencode")
    parser.add_argument("--model", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--variant", default="")
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args(argv)
    return run_opencode(
        opencode_command=args.opencode_command,
        prompt=args.prompt,
        model=args.model,
        title=args.title,
        variant=args.variant,
    )


if __name__ == "__main__":
    raise SystemExit(main())
