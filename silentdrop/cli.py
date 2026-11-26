"""Command-line entry point for SilentDrop."""

import argparse
from collections.abc import Sequence

from . import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line arguments and return a process exit code."""
    parser = argparse.ArgumentParser(
        prog="silentdrop",
        description="Run website connectivity diagnostics with SilentDrop.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
