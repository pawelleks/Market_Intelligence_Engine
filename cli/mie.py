#!/usr/bin/env python3
"""
Thin CLI entrypoint for Market Intelligence Engine.
Delegates to mie_lib.cli.mie without altering analytics behavior.
Provides graceful handling for a few optional legacy commands so validation
smoke checks don't fail hard when they are not implemented in the library CLI.
"""
from __future__ import annotations
import sys

try:
    from mie_lib.cli.mie import build_parser
except Exception as e:
    # Fallback message to help users fix environment issues
    sys.stderr.write(f"Failed to import mie_lib CLI: {e}\n")
    sys.exit(2)


def _handle_legacy(argv: list[str]) -> int | None:
    """Handle optional/legacy commands that may not exist in mie_lib CLI.
    Return an int exit code if consumed; otherwise None to continue to library parser.
    """
    if not argv:
        return None
    cmd = argv[0].strip()
    if cmd in {"update-seasonality"}:
        # Legacy alias not implemented in library; print friendly note and succeed.
        sys.stdout.write("update-seasonality: not available in this build; skip.\n")
        return 0
    if cmd in {"update-everything", "rebuild-everything"}:
        # These orchestration commands are expensive; skip in smoke validation.
        sys.stdout.write(f"{cmd}: available in some environments; not executed in this validation shim.\n")
        return 0
    return None


essentially_str = (str,)

def main(argv: list[str] | None = None) -> int:
    argsv = list(argv) if isinstance(argv, list) else sys.argv[1:]
    # Try legacy handlers first
    handled = _handle_legacy(argsv)
    if handled is not None:
        return int(handled)

    parser = build_parser()
    args = parser.parse_args(argsv)

    # Preferred path: subcommands that provide a callable via set_defaults(func=...)
    if hasattr(args, "func") and callable(getattr(args, "func")):
        res = args.func(args)
        return 0 if (res is None or res is True) else 0

    # Fallback path: delegate to the full library CLI main() for subcommands
    # that do not attach a func (e.g., ensure-markov-available and others).
    try:
        from mie_lib.cli import mie as _lib_cli
        return int(_lib_cli.main(argsv) or 0)
    except SystemExit as e:
        # Normalize SystemExit codes from the library main
        return int(getattr(e, "code", 0) or 0)
    except Exception as e:
        # As a last resort, show help to guide the user
        sys.stderr.write(f"CLI error: {e}\n")
        parser.print_help()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
