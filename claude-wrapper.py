import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLAUDE_BIN = os.path.join(SCRIPT_DIR, "claude.bin")

if __name__ == "__main__":
    if not os.path.exists(CLAUDE_BIN):
        print(f"[ERROR] claude.bin not found at {CLAUDE_BIN}", file=sys.stderr)
        sys.exit(1)

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    p = subprocess.Popen(
        [CLAUDE_BIN] + sys.argv[1:],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    sys.exit(p.wait())
