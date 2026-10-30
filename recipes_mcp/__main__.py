"""Command-line entry: `python -m recipes_mcp` or `recipes-mcp-server` if installed."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .server import serve
from .storage import RecipeStore, StorageError


def default_data_dir() -> Path:
    """recipes.json lives next to the package unless RECIPE_MCP_DATA overrides it."""
    env = os.environ.get("RECIPE_MCP_DATA")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recipe-mcp-server",
        description="Offline MCP server (stdio) for your recipe collection. "
        "Made by Asdale Dynamics, LLC.",
    )
    parser.add_argument(
        "--data-dir",
        default=str(default_data_dir()),
        help="Directory holding recipes.json and its backups "
        "(default: recipes_mcp/data, or $RECIPE_MCP_DATA)",
    )
    parser.add_argument(
        "--keep-backups",
        type=int,
        default=3,
        help="How many rotating backups of recipes.json to keep (default 3)",
    )
    args = parser.parse_args(argv)

    try:
        RecipeStore.validate_data_dir(args.data_dir)
    except StorageError as exc:
        parser.exit(2, f"recipe-mcp-server: {exc}\n")

    serve(args.data_dir, keep_backups=args.keep_backups)
    return 0


if __name__ == "__main__":
    sys.exit(main())
