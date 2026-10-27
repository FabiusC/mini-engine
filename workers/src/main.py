"""Entry point: python workers/src/main.py [ARTIFACT_DIR] [--worker pandas|polars]."""

from workers.__main__ import main

if __name__ == "__main__":
	raise SystemExit(main())
