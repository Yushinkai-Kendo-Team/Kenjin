"""Stop all running YKC Kenjin servers (uvicorn, streamlit).

Usage:
    python scripts/stop_servers.py
"""

import os
import subprocess
import sys

KEYWORDS = ["uvicorn", "streamlit run"]
MY_PID = os.getpid()


def get_server_pids():
    """Find Python processes running uvicorn or streamlit."""
    result = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get",
         "ProcessId,CommandLine", "/format:csv"],
        capture_output=True, text=True,
    )

    pids = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("Node"):
            continue

        parts = line.split(",")
        if len(parts) < 3:
            continue

        cmdline = ",".join(parts[1:-1])
        pid_str = parts[-1].strip()
        if not pid_str.isdigit():
            continue

        pid = int(pid_str)
        if pid == MY_PID:
            continue

        # Skip the stop script itself
        if "stop_servers" in cmdline:
            continue

        cmd_lower = cmdline.lower()
        for kw in KEYWORDS:
            if kw in cmd_lower:
                desc = "uvicorn" if "uvicorn" in cmd_lower else "streamlit"
                pids.append((pid, desc, cmdline.strip()[:120]))
                break

    return pids


def main():
    pids = get_server_pids()

    if not pids:
        print("No running YKC Kenjin servers found.")
        return

    print(f"Found {len(pids)} server process(es):\n")
    for pid, desc, cmd in pids:
        print(f"  PID {pid:>6}  [{desc}]  {cmd}")

    print()
    for pid, desc, _ in pids:
        result = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"  Stopped PID {pid} ({desc})")
        else:
            print(f"  Failed to stop PID {pid}: {result.stderr.strip()}")

    # Also kill any orphaned child processes (e.g. streamlit spawns children)
    remaining = get_server_pids()
    for pid, desc, _ in remaining:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        print(f"  Stopped orphan PID {pid} ({desc})")

    final = get_server_pids()
    if final:
        print(f"\nWarning: {len(final)} process(es) still running.")
    else:
        print("\nAll servers stopped.")


if __name__ == "__main__":
    main()
