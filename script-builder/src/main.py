"""Entry point: python script-builder/src/main.py [DAG.json] [--framework pandas|polars]."""

from script_builder.__main__ import main

# Thin wrapper so the CLI can be run as a plain script (python src/main.py).
if __name__ == "__main__":
	main()
