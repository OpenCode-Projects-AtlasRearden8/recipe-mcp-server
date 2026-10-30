# STATUS — recipe-mcp-server

Last updated: 2026-10-30

## What was built

A small, offline **MCP (Model Context Protocol) server over stdio** that holds
a personal recipe collection and gives AI agents cooking-help tools. Pure
Python standard library (Python 3.10+, no third-party dependencies), JSON
storage with path safety, atomic writes, corrupt-file recovery, and automatic
rotating backups. Ships with a 5-recipe starter set so it works immediately.

Built by **Asdale Dynamics, LLC** (MIT licensed).

Tools exposed to the agent:

1. `add_recipe` — title, servings, ingredients (item/amount/unit), steps, tags
2. `list_recipes` — whole collection overview
3. `get_recipe` — one recipe formatted to read while cooking
4. `search_recipes` — by ingredients on hand (ranked by how much you'd use up), tags, or keyword
5. `scale_recipe` — rescale all amounts for a target serving count
6. `shopping_list` — combine recipes, scale per recipe, group by store section, pull pantry matches out as "already have"
7. `delete_recipe` — remove by id

Notable behaviors:

- Pantry matching ignores prep words (`garlic, minced` ← `garlic`) but
  deliberately refuses lookalikes (`garlic powder` ≠ `garlic`, `beef broth` ≠ `beef`).
- Amounts accept strings (`"1 1/2"`) and render as mixed fractions (`2 1/2`),
  with sensible singular/plural units (`1 can` / `2 cans`).
- Security: store must be `recipes.json` directly inside the data directory;
  traversal and symlink escapes rejected on every operation.
- Reliability: atomic writes (temp + rename), rotating backups
  (`recipes.json.bak-1..3`), recovery from the newest readable backup if the
  main file corrupts.

## How to run it

```bash
python3 -m recipes_mcp                                  # stdio JSON-RPC server
python3 -m recipes_mcp --data-dir ~/recipes-data        # custom data dir
pip install . && recipe-mcp-server                      # installed entry point
```

Data override: `RECIPE_MCP_DATA=/path/to/dir`.
Tests: `python3 -m unittest discover -s tests`
Full instructions, MCP-client config snippet, and hand smoke-tests: see `README.md`.

## Verification results (all passing on 2026-10-30)

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests` | **38/38 OK** (~0.04 s, offline, mktemp dirs) |
| stdio handshake (`initialize` → `notifications/initialized` suppressed → `tools/list`) | PASS — protocolVersion 2024-11-05, serverInfo `recipe-mcp-server` 1.0.0, 7 tools with schemas |
| Tool calls over real pipe (search / scale / shopping_list) | PASS — search ranks by pantry coverage; scale 2→5 correct (x2.5: 20 oz pasta, 7 1/2 tbsp butter); pantry-aware grouped list correct |
| `pip install .` in fresh venv + `recipe-mcp-server` entry point + `RECIPE_MCP_DATA` | PASS |
| Data-dir security cases (traversal, symlink escape, wrong name, `/` root, file-as-dir) | PASS (stored as unit tests) |
| Corrupt-store recovery from backup | PASS |
| No network access, no secrets, no personal data in any file | Verified by inspection; tests use temp dirs only |

## Known gaps / future ideas

- Ingredient categorization is keyword-based; unusual ingredient names may
  land in "other" (still included in the list, just ungrouped).
- No unit conversion across incompatible units (e.g. two "1 cup flour" +
  "12 g flour" stay separate lines rather than merging grams/cups).
- Edges: `pantry` matching is name-based only — no quantity awareness, so
  a pantry entry always covers a recipe need regardless of amount on hand.
- No recipe editing tool (delete + re-add is the current path).
- MCP resources/prompts are advertised as empty lists; only tools are implemented.
- Single-user design: no locking for concurrent servers sharing one data dir
  (use one server per client, or point clients at distinct data dirs).

## Files

```
README.md  LICENSE (MIT)  pyproject.toml  .gitignore
recipes_mcp/ (server.py, service.py, service_shopping.py, quantities.py,
              storage.py, starter_recipes.py, __main__.py)
tests/test_recipes.py
```
