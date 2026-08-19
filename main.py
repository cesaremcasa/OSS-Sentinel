import sys

from src.cli import main as cli_main

if __name__ == "__main__":
    raise SystemExit(cli_main(["run", *sys.argv[1:]]))
