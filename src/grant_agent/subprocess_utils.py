from __future__ import annotations

import os
import subprocess
from typing import Any


def hidden_windows_subprocess_kwargs(
    *,
    new_process_group: bool = False,
) -> dict[str, Any]:
    if os.name != "nt":
        return {}

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if new_process_group:
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    payload: dict[str, Any] = {"creationflags": flags}
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_type is not None:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        payload["startupinfo"] = startupinfo
    return payload


def background_creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )
