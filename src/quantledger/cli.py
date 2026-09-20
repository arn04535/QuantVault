"""Command-line entry point for QuantLedger."""

from __future__ import annotations

import argparse

from quantledger import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantledger",
        description="Local experiment ledger for quantitative research.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
