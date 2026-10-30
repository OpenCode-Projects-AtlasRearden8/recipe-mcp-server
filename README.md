# Recipe MCP Server

A small, offline **MCP server** (Model Context Protocol, stdio transport) that
holds a personal recipe collection and gives AI agents the tools to help you
actually cook: search by what's in your fridge, scale recipes for a cook-date,
and turn a week of meals into a grouped shopping list — with the items you
already have pulled out as "already have".

Plain Python standard library only. No dependencies, no network, no accounts.
Your recipes live in one JSON file with automatic rotating backups.

Built with beginner-friendly, local-first principles in mind by
**Asdale Dynamics, LLC** — the same spirit behind *The Massive AI Manual* and
[dylanasdale.github.io](https://dylanasdale.github.io): AI explained like a
friend would, never condescending.

---

## What it does

| Tool | What your agent can do with it |
| --- | --- |
| `add_recipe` | Store a recipe: ingredients (with amounts + units), steps, servings, tags |
| `list_recipes` | List the whole collection (id, title, servings, tags) |
| `get_recipe` | Fetch one recipe formatted for a cook to read |
| `search_recipes` | Find recipes by ingredients on hand (ranked by how much you'd use up), tags, or a title/keyword query |
| `scale_recipe` | Rescale every ingredient for a target serving count (e.g. cooking for 5 instead of 2) |
| `shopping_list` | Combine recipes into one list, scaled per recipe, grouped by store section, with pantry-aware gaps |
| `delete_recipe` | Remove a recipe by id |

The starter set ships with 5 recipes (chickpea curry, garlic butter pasta,
sheet-pan salmon, black bean tacos, chili) so everything works immediately.

## How your data is stored

- Everything lives in **`recipes.json`** inside a data directory
  (default: `recipes_mcp/data/`, override with `--data-dir` or `RECIPE_MCP_DATA`).
- Before **every** change, backups rotate automatically: `recipes.json.bak-1`
  (newest) through `recipes.json.bak-3` are kept.
- If `recipes.json` is ever corrupted, the server recovers from the newest
  readable backup instead of crashing or losing your library.
- Writes are atomic (temp file + rename), so a crash mid-save can't leave a
  half-written file.
- **Path safety:** the store file must be a file named `recipes.json` directly
  inside the data directory; directory traversal and symlink escapes are
  rejected on every operation.

## Requirements

Python **3.10+**. That's it.

## Run it

```bash
# straight from this folder
python3 -m recipes_mcp

# optional: choose where recipes.json lives
python3 -m recipes_mcp --data-dir /home/you/recipes-data --keep-backups 5

# or install the `recipe-mcp-server` command
pip install .
recipe-mcp-server
```

## Connect it to an MCP client (Claude Desktop, etc.)

Add a server entry pointing at the Python entry point, e.g. on Linux/macOS:

```json
{
  "mcpServers": {
    "recipes": {
      "command": "python3",
      "args": ["-m", "recipes_mcp"],
      "cwd": "/path/to/recipe-mcp-server"
    }
  }
}
```

(If you installed with `pip`, use `"command": "recipe-mcp-server"`, `"args": []`.)

## Smoke-test it by hand (no client needed)

The server speaks newline-delimited JSON-RPC on stdin/stdout. Try:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_recipes","arguments":{"query":"curry"}}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"scale_recipe","arguments":{"recipe_id":"garlic-butter-pasta","target_servings":5}}}' \
  | python3 -m recipes_mcp
```

You should see: an `initialize` result with `serverInfo.name =
"recipe-mcp-server"`, then the curry recipe match, then the pasta recipe
scaled 2 → 5 servings (x2.5: 20 oz spaghetti, 7 1/2 tablespoons butter, ...).

A pantry-aware shopping list example:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"shopping_list","arguments":{"recipe_ids":["black-bean-tacos","weeknight-chickpea-curry"],"pantry":["olive oil","garlic","onion","curry powder"]}}}' \
  | python3 -m recipes_mcp
```

Items matching your pantry move to `ALREADY HAVE`; everything else is
`BUY`-grouped by produce / protein / dairy / spices / pantry / frozen.

## Run the tests

```bash
python3 -m unittest discover -s tests
```

38 offline tests cover amount parsing, fraction formatting, scaling math,
ingredient search + ranking, pantry matching (including "garlic powder" ≠
"garlic"), shopping-list grouping, persistence, backup rotation, corrupt-file
recovery, and the path-safety security cases (`..` traversal, symlink escape,
wrong filename, root and non-directory data dirs).

## Example agent flow

1. **"What can I make tonight?"** — agent calls `search_recipes` with
   `ingredients_on_hand: ["chickpeas", "coconut milk", "spinach"]`.
2. **"Cook it for 5 people"** — agent calls `scale_recipe` with
   `target_servings: 5` and every amount is rescaled.
3. **"Make a list for both dinners"** — agent calls `shopping_list` with both
   recipe ids, per-recipe `servings`, and your pantry items; items you have
   are separated from what to buy, grouped by store section.

## Project layout

```
recipes_mcp/
  __main__.py          # CLI entry (argparse + stdio loop)
  server.py            # JSON-RPC 2.0 / MCP protocol + tool registry
  service.py           # add / get / search / scale / shopping-list logic
  service_shopping.py  # ingredient categorization (store sections)
  quantities.py        # amount parsing, scaling, fraction formatting
  storage.py           # JSON store, path safety, rotating backups
  starter_recipes.py   # the 5 included starter recipes
tests/test_recipes.py  # 38 offline unit tests
```

## Design notes for the curious

- Pantry matching understands prep words (`diced`, `minced`, `canned`) and
  deliberately refuses wrong-item matches: `garlic powder` does **not** count
  as `garlic`, `beef broth` is not `beef`.
- Amounts accept strings like `"1 1/2"` and are scaled to friendly mixed
  fractions (`2.5 × 2.5 = 6.25` displays as `6 1/4`).
- Seasoning to taste (salt, pepper, oils, spices) doesn't always scale
  linearly, so `scale_recipe` adds a small note when shrinking a recipe.

## License & credit

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Asdale Dynamics, LLC.
Made by Asdale Dynamics, LLC as part of a suite of beginner-friendly,
local-first tools. Learn more at [dylanasdale.github.io](https://dylanasdale.github.io).

Sibling projects to know about (this server deliberately does *not* do these
jobs): a pantry-*inventory* MCP server tracks stock levels and spoilage; a
meal-rotation planner webapp handles week-by-week meal scheduling.
