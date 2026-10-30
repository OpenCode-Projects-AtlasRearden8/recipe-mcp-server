"""Minimal MCP server over stdio: newline-delimited JSON-RPC 2.0.

Implements the parts of the Model Context Protocol a tools-only server needs:
initialize, notifications/initialized, ping, tools/list, tools/call. No
third-party dependencies; every message is a single JSON line.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from . import __version__
from .quantities import describe_ingredient
from .storage import RecipeStore, StorageError
from .service import RecipeService

PROTOCOL_VERSION = "2024-11-05"
JSONRPC = "2.0"

SERVER_INFO = {
    "name": "recipe-mcp-server",
    "title": "Recipe Collection MCP",
    "version": __version__,
}


# ---------------------------------------------------------------------------
# Tool registry: name -> (description, input schema, handler)
# ---------------------------------------------------------------------------


async def _handle_add_recipe(args: dict, service: RecipeService) -> str:
    recipe = service.add_recipe(args)
    return (
        f"Saved '{recipe['title']}' (id: {recipe['id']}) — "
        f"{recipe['servings']} servings, {len(recipe['ingredients'])} ingredients, "
        f"tags: {', '.join(recipe['tags']) or 'none'}."
    )


def _handle_get_recipe(args: dict, service: RecipeService) -> str:
    r = service.get_recipe(args["recipe_id"])
    lines = [f"# {r['title']} — {r['servings']} servings", f"tags: {', '.join(r['tags']) or 'none'}", ""]
    lines.append("Ingredients:")
    lines.extend(f"  - {describe_ingredient(i['item'], i['amount'], i['unit'])}" for i in r["ingredients"])
    if r["steps"]:
        lines.append("")
        lines.append("Steps:")
        lines.extend(f"  {n}. {s}" for n, s in enumerate(r["steps"], 1))
    return "\n".join(lines)


def _handle_list_recipes(args: dict, service: RecipeService) -> str:
    items = service.list_recipes()
    if not items:
        return "Recipe library is empty."
    lines = [f"{len(items)} recipe(s):"]
    lines.extend(
        f"  - {r['id']} — {r['title']} ({r['servings']} servings)"
        + (f" [{', '.join(r['tags'])}]" if r["tags"] else "")
        for r in items
    )
    return "\n".join(lines)


def _handle_search(args: dict, service: RecipeService) -> str:
    results = service.search(
        ingredients_on_hand=args.get("ingredients_on_hand"),
        tags=args.get("tags"),
        query=args.get("query", ""),
    )
    if not results:
        return "No recipes matched."
    lines = [f"{len(results)} match(es):"]
    for r in results[:12]:
        ratio = r["you_have_ratio"]
        lines.append(
            f"  - {r['title']} (id: {r['id']}, serves {r['servings']})"
            + (f" — you have {int(ratio * 100)}% of ingredients" if ratio is not None else "")
        )
        for miss in r["missing_ingredients"]:
            lines.append(f"      · need: {miss}")
    return "\n".join(lines)


def _handle_scale(args: dict, service: RecipeService) -> str:
    s = service.scale(args["recipe_id"], args["target_servings"])
    lines = [
        f"# {s['title']} — scaled from {s['base_servings']} to {s['target_servings']} servings "
        f"(x{s['scale_factor']:g})",
        "",
        "Ingredients:",
    ]
    lines.extend(f"  - {line['display']}" for line in s["ingredients"])
    if s.get("note"):
        lines += ["", f"Note: {s['note']}"]
    return "\n".join(lines)


def _handle_shopping_list(args: dict, service: RecipeService) -> str:
    li = service.shopping_list(
        args["recipe_ids"],
        servings=args.get("servings"),
        pantry=args.get("pantry"),
    )
    lines = [f"Shopping list — combined from {len(li['recipes'])} recipe(s):"]
    lines.extend(
        f"  * {r['title']} (serves {r['servings']}, was {r['base_servings']})"
        for r in li["recipes"]
    )
    lines.append("")
    lines.append("BUY (grouped):")
    for group in li["shop_for"]:
        lines.append(f"  {group['category'].upper()}:")
        lines.extend(f"    [ ] {i['display']}" for i in group["items"])
    lines.append("")
    lines.append(f"ALREADY HAVE ({len(li['already_have'])} — skip these):")
    lines.extend(f"  - {i['display']}" for i in li["already_have"])
    return "\n".join(lines)


def _handle_delete_recipe(args: dict, service: RecipeService) -> str:
    if service.delete_recipe(args["recipe_id"]):
        return f"Deleted recipe {args['recipe_id']!r}."
    raise KeyError(f"no recipe with id {args['recipe_id']!r}")


RECIPES_SCHEMA_ITEM = {
    "type": "object",
    "properties": {
        "item": {"type": "string", "description": "Ingredient name, e.g. 'chickpeas, canned'"},
        "amount": {
            "type": ["number", "string"],
            "description": "Amount as number or string like '1 1/2'",
        },
        "unit": {"type": ["string", "null"], "description": "Optional unit, e.g. cups"},
    },
    "required": ["item"],
}

TOOLS = [
    {
        "name": "add_recipe",
        "description": "Add a recipe to the collection with ingredients, steps, servings and tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "servings": {"type": "integer", "description": "How many people the recipe serves"},
                "ingredients": {
                    "type": "array",
                    "items": RECIPES_SCHEMA_ITEM,
                    "description": "At least one ingredient",
                },
                "steps": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "servings", "ingredients"],
        },
    },
    {
        "name": "list_recipes",
        "description": "List every recipe in the collection (id, title, servings, tags).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_recipe",
        "description": "Fetch one recipe in full, formatted for a cook to read.",
        "inputSchema": {
            "type": "object",
            "properties": {"recipe_id": {"type": "string"}},
            "required": ["recipe_id"],
        },
    },
    {
        "name": "delete_recipe",
        "description": "Delete a recipe by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"recipe_id": {"type": "string"}},
            "required": ["recipe_id"],
        },
    },
    {
        "name": "search_recipes",
        "description": "Find recipes by ingredients on hand, tags, or a title/keyword query. "
        "With ingredients_on_hand, results are ranked by how much you'd already have.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ingredients_on_hand": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "e.g. ['chickpeas', 'garlic', 'rice']",
                },
                "tags": {"type": "array", "items": {"type": "string"}},
                "query": {"type": "string"},
            },
        },
    },
    {
        "name": "scale_recipe",
        "description": "Scale a recipe to a new serving count for a cook-date; amounts rescaled.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "recipe_id": {"type": "string"},
                "target_servings": {"type": "integer"},
            },
            "required": ["recipe_id", "target_servings"],
        },
    },
    {
        "name": "shopping_list",
        "description": "Combine recipes into one grouped shopping list. Items matched against "
        "your pantry move to 'already_have'; the rest are grouped by store section showing "
        "the scaled amounts you still need to buy.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "recipe_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recipe ids to combine",
                },
                "servings": {
                    "type": "object",
                    "description": "Optional: {recipe_id: servings} to scale per recipe",
                    "additionalProperties": {"type": "integer"},
                },
                "pantry": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ingredients you already have, e.g. ['olive oil', 'rice']",
                },
            },
            "required": ["recipe_ids"],
        },
    },
]

_HANDLERS: dict[str, Callable[..., str]] = {
    "add_recipe": _handle_add_recipe,
    "list_recipes": _handle_list_recipes,
    "get_recipe": _handle_get_recipe,
    "delete_recipe": _handle_delete_recipe,
    "search_recipes": _handle_search,
    "scale_recipe": _handle_scale,
    "shopping_list": _handle_shopping_list,
}


# ---------------------------------------------------------------------------
# JSON-RPC plumbing
# ---------------------------------------------------------------------------


def _response(req_id: Any, result: dict[str, Any]) -> dict:
    return {"jsonrpc": JSONRPC, "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": JSONRPC, "id": req_id, "error": {"code": code, "message": message}}


class MCPServer:
    """Dispatch JSON-RPC messages against a recipe service."""

    def __init__(self, service: RecipeService) -> None:
        self.service = service

    def handle_message(self, message: dict) -> dict | None:
        """Return a response dict, or None for notifications/an error reply."""
        if not isinstance(message, dict):
            return _error(None, -32600, "request must be an object")
        method = message.get("method")
        req_id = message.get("id")
        params = message.get("params") or {}
        notification = req_id is None

        if method == "initialize":
            return _response(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
                "instructions": (
                    "Tools for storing, searching and scaling your recipes. "
                    "Add recipes with add_recipe, search by what's on hand with "
                    "search_recipes, scale for a cook-date with scale_recipe, and "
                    "build pantry-aware shopping lists with shopping_list."
                ),
            })
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return _response(req_id, {})
        if method == "tools/list":
            return _response(req_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._call_tool(req_id, params)
        if method == "resources/list":
            return _response(req_id, {"resources": []})
        if method == "prompts/list":
            return _response(req_id, {"prompts": []})

        code = -32601 if method else -32600
        text = f"method not found: {method}" if method else "request must have a 'method'"
        if notification:
            return None if code == -32601 else _error(None, code, text)
        return _error(req_id, code, text)

    def _call_tool(self, req_id: Any, params: Any) -> dict:
        if not isinstance(params, dict):
            return _error(req_id, -32602, "params must be an object")
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = _HANDLERS.get(name)
        if handler is None:
            return _error(req_id, -32602, f"unknown tool: {name!r}")
        try:
            text = handler(args, self.service)
            return _response(req_id, {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            })
        except KeyError as exc:
            return self._tool_error(req_id, str(exc.args[0] if exc.args else exc))
        except (ValueError, StorageError) as exc:
            return self._tool_error(req_id, str(exc))
        except Exception as exc:  # last-resort so stdio never dies mid-call
            return self._tool_error(req_id, f"internal error: {exc}")

    @staticmethod
    def _tool_error(req_id: Any, message: str) -> dict:
        return _response(req_id, {
            "content": [{"type": "text", "text": f"Error: {message}"}],
            "isError": True,
        })


def build_server(data_dir: str, keep_backups: int = 3) -> tuple[MCPServer, RecipeStore]:
    store = RecipeStore(data_dir, keep_backups=keep_backups)
    return MCPServer(RecipeService(store)), store


def serve(data_dir: str, keep_backups: int = 3, stdin=None, stdout=None) -> None:
    """Blocking stdio loop: one JSON-RPC message per input line."""
    server, _store = build_server(data_dir, keep_backups)
    reader = stdin or sys.stdin
    writer = stdout or sys.stdout
    for raw in reader:
        line = raw.strip()
        if not line:
            continue
        try:
            incoming = json.loads(line)
        except json.JSONDecodeError:
            response = _error(None, -32700, "parse error: invalid JSON")
        else:
            response = server.handle_message(incoming)
        if response is not None:
            writer.write(json.dumps(response, separators=(",", ":")) + "\n")
            writer.flush()
