"""Call Claude Code CLI to generate answers from retrieved context."""

from __future__ import annotations

import os
import subprocess
import shutil


def is_claude_available() -> bool:
    """Check if the claude CLI is installed and accessible."""
    return shutil.which("claude") is not None


def is_claude_ready() -> tuple[bool, str]:
    """Check if Claude CLI is installed AND authenticated.

    Returns:
        Tuple of (ready, message).
    """
    if not is_claude_available():
        return False, "Claude Code CLI not found. Install it or add it to PATH."

    try:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        result = subprocess.run(
            ["claude", "-p", "ping"],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "login" in stderr.lower() or "auth" in stderr.lower():
                return False, "Claude Code CLI not logged in. Run 'claude login' first."
            return False, f"Claude Code CLI error: {stderr[:200]}"
        return True, "Claude Code CLI ready."
    except subprocess.TimeoutExpired:
        return False, "Claude Code CLI timed out on health check."
    except Exception as e:
        return False, f"Claude Code CLI check failed: {e}"


def ask_claude(prompt: str, timeout: int = 120) -> str:
    """Send a prompt to Claude Code CLI and return the response.

    Args:
        prompt: The full prompt (system context + question).
        timeout: Max seconds to wait for response.

    Returns:
        Claude's response text, or an error message starting with [Error].
    """
    if not is_claude_available():
        return "[Error] Claude Code CLI not found. Install it or add it to PATH."

    try:
        # Remove CLAUDECODE env var so claude CLI doesn't refuse to run
        # when launched from within a Claude Code session.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            env=env,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            return f"[Error] Claude CLI returned code {result.returncode}: {stderr}"

        output = result.stdout.strip()
        if not output:
            return "[Error] Claude CLI returned empty response."

        return output

    except subprocess.TimeoutExpired:
        return f"[Error] Claude CLI timed out after {timeout}s."
    except Exception as e:
        return f"[Error] Failed to call Claude CLI: {e}"
