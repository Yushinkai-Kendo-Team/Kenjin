"""Run the full ingestion pipeline to populate the knowledge base.

Usage:
    python scripts/ingest_all.py [--reset]
"""

import sys
from pathlib import Path

# Add src to path so we can import kendocenter
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from kendocenter.ingestion.ingest_pipeline import run_ingestion


def main():
    reset = "--reset" in sys.argv
    if reset:
        print("WARNING: This will wipe and rebuild all data.\n")

    run_ingestion(reset=reset)


if __name__ == "__main__":
    main()
