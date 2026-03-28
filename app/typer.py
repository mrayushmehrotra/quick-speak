"""
app/typer.py
────────────
Types a text string into whatever window/input currently has keyboard focus,
using `xdotool type`.

Public API
----------
Typer.type_text(text: str)
    Strip text, optionally append a space, then shell out to xdotool.
    Does nothing if text is empty.

Requirements
------------
    sudo apt install xdotool
"""

import subprocess
import config


class Typer:
    def type_text(self, text: str):
        """
        Type `text` into the currently focused input using xdotool.

        Key implementation notes
        ------------------------
        - shell=False is required so special characters are not misinterpreted.
        - `--clearmodifiers` prevents any held modifier keys (Shift, Ctrl, …)
          from the QuickSpeak window itself corrupting the output.
        - `--` separates flags from the text payload; prevents text that starts
          with `-` being treated as a flag.
        - `check=False` means we do not raise on xdotool exit ≠ 0 (e.g. if the
          target window closed between stop and type).
        """
        text = text.strip()
        if not text:
            print("[Typer] Nothing to type (empty string).")
            return

        if config.APPEND_SPACE:
            text = text + " "

        cmd = [
            "xdotool", "type",
            "--clearmodifiers",
            f"--delay={config.TYPE_DELAY_MS}",
            "--",   # end of flags
            text,
        ]

        print(f"[Typer] Typing: {text!r}")
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[Typer] xdotool warning (exit {result.returncode}): {result.stderr.strip()}")
