"""Recipe operations: add, get, search, scale, and pantry-aware shopping lists.

Pure logic, no I/O: every function takes/returns plain dicts so it is easy to
unit-test offline and to drive from the MCP layer.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from .quantities import describe_ingredient, format_amount, normalize_unit, parse_amount, scale_amount
from .service_shopping import CATEGORY_ORDER, categorize, group_pantry_aware

STOP_TOKENS = {"canned", "minced", "diced", "grated", "fresh", "large", "small", "sliced",
               "shredded", "chopped", "optional", "peeled", "thinly", "room", "temperature",
               "low", "sodium"}

# Words that change what an ingredient IS ('garlic powder' is not garlic).
# If an ingredient carries one of these and the pantry entry does not, no match.
QUALIFIER_TOKENS = {"powder", "salt", "sauce", "broth", "juice", "extract", "flakes",
                    "seasoning", "syrup", "paste", "stock", "mix", "chilies", "pepper"}


def _clean_text(value, field: str, *, max_len: int = 200) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    text = unicodedata.normalize("NFKC", value).strip()
    if not text:
        raise ValueError(f"{field} must not be empty")
    if len(text) > max_len:
        raise ValueError(f"{field} is too long (max {max_len} characters)")
    return text


def normalize_recipe(raw: dict) -> dict:
    """Validate + normalize a recipe dict for storage. Raises ValueError."""
    if not isinstance(raw, dict):
        raise ValueError("recipe must be an object")

    title = _clean_text(raw.get("title"), "title", max_len=120)
    servings = raw.get("servings", 2)
    if isinstance(servings, bool) or not isinstance(servings, (int, float)) or servings <= 0:
        raise ValueError("servings must be a positive number")
    if not float(servings).is_integer():
        raise ValueError("servings must be a whole number")

    ingredients_raw = raw.get("ingredients")
    if not isinstance(ingredients_raw, list) or not ingredients_raw:
        raise ValueError("ingredients must be a non-empty list")
    ingredients = []
    for entry in ingredients_raw:
        if isinstance(entry, str):
            entry = {"item": entry}
        if not isinstance(entry, dict) or "item" not in entry:
            raise ValueError("each ingredient needs an 'item'")
        item = _clean_text(entry.get("item"), "ingredient item", max_len=120).lower()
        amount = parse_amount(entry.get("amount", 1))
        unit = normalize_unit(entry.get("unit")) if entry.get("unit") else None
        ingredients.append({"item": item, "amount": amount, "unit": unit})

    steps = raw.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("steps must be a list")
    steps = [_clean_text(s, "step", max_len=1000) for s in steps]

    tags_raw = raw.get("tags", [])
    if isinstance(tags_raw, str):
        tags_raw = [tags_raw]
    if not isinstance(tags_raw, list):
        raise ValueError("tags must be a list")
    tags = sorted({t.strip().lower() for t in tags_raw if isinstance(t, str) and t.strip()})

    recipe = {
        "id": _slug(title),
        "title": title,
        "servings": int(servings),
        "tags": tags,
        "ingredients": ingredients,
        "steps": steps,
    }
    source = raw.get("source")
    if isinstance(source, str) and source.strip():
        recipe["source"] = source.strip()[:120]
    return recipe


def _slug(title: str) -> str:
    slug = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    return slug or "recipe"


def ingredient_tokens(item: str) -> set[str]:
    """Searchable tokens for an ingredient name (drops prep words)."""
    tokens = {
        t for t in re.findall(r"[a-z0-9]+", item.lower())
        if t not in STOP_TOKENS
    }
    # Collapse simple plurals so 'tomatoes' matches 'tomato'.
    return {t[:-1] if t.endswith("ies") else (t[:-1] if t.endswith("s") and len(t) > 3 else t) for t in tokens}


def pantry_match(item: str, pantry: list[str]) -> str | None:
    """Return the pantry entry that covers this ingredient, if any.

    Matching is token based with two guards:
      - prep words are ignored ('garlic, minced' matches 'garlic')
      - qualifier words must agree ('garlic powder' does NOT match 'garlic')
    """
    have = ingredient_tokens(item)
    have_qualifiers = have & QUALIFIER_TOKENS
    for pantry_item in pantry:
        want = ingredient_tokens(str(pantry_item))
        if not want:
            continue
        token_match = want <= have or have <= want or bool(want & have)
        qualifier_ok = have_qualifiers <= want
        if token_match and qualifier_ok:
            return pantry_item
    return None


# ---- public API ---------------------------------------------------------


class RecipeService:
    def __init__(self, store) -> None:
        self.store = store

    # -- add / get --------------------------------------------------------

    def add_recipe(self, raw: dict) -> dict:
        recipe = normalize_recipe(raw)
        base_id = recipe["id"]
        existing = {r["id"] for r in self.store.recipes}
        n = 2
        while recipe["id"] in existing:
            recipe["id"] = f"{base_id}-{n}"
            n += 1
        self.store.recipes.append(recipe)
        self.store.save()
        return recipe

    def get_recipe(self, recipe_id: str) -> dict:
        for r in self.store.recipes:
            if r["id"] == recipe_id or r["id"] == _slug(str(recipe_id)):
                return r
        raise KeyError(f"no recipe with id {recipe_id!r}")

    def delete_recipe(self, recipe_id: str) -> bool:
        for i, r in enumerate(self.store.recipes):
            if r["id"] == recipe_id:
                del self.store.recipes[i]
                self.store.save()
                return True
        return False

    def list_recipes(self) -> list[dict]:
        return [
            {"id": r["id"], "title": r["title"], "servings": r["servings"], "tags": r["tags"]}
            for r in self.store.recipes
        ]

    # -- search -----------------------------------------------------------

    def search(
        self,
        ingredients_on_hand: list[str] | None = None,
        tags: list[str] | None = None,
        query: str = "",
    ) -> list[dict]:
        """Rank recipes by how much of what you have they'd use up."""
        on_hand = [h.strip().lower() for h in (ingredients_on_hand or []) if h.strip()]
        wanted_tags = {t.strip().lower() for t in (tags or []) if t.strip()}
        q = query.strip().lower()

        results = []
        for r in self.store.recipes:
            if wanted_tags and not wanted_tags.issubset(set(r["tags"])):
                continue
            if q and q not in r["title"].lower() and not any(q in t for t in r["tags"]):
                continue
            matched, missing = [], []
            for ing in r["ingredients"]:
                if on_hand and pantry_match(ing["item"], on_hand):
                    matched.append(ing["item"])
                else:
                    missing.append(ing["item"])
            coverage = (len(matched) / len(r["ingredients"])) if on_hand else 0.0
            results.append({
                "id": r["id"],
                "title": r["title"],
                "servings": r["servings"],
                "tags": r["tags"],
                "ingredient_count": len(r["ingredients"]),
                "matched_ingredients": matched,
                "missing_ingredients": missing,
                "you_have_ratio": round(coverage, 2) if on_hand else None,
            })
        if on_hand:
            results.sort(key=lambda x: (-x["you_have_ratio"], x["ingredient_count"], x["title"]))
        return results

    # -- scaling ----------------------------------------------------------

    def scale(self, recipe_id: str, target_servings: int) -> dict:
        if isinstance(target_servings, bool) or not isinstance(target_servings, (int, float)):
            raise ValueError("target_servings must be a number")
        if target_servings <= 0 or not float(target_servings).is_integer():
            raise ValueError("target_servings must be a positive whole number")
        recipe = self.get_recipe(recipe_id)
        factor = float(target_servings) / recipe["servings"]
        lines = [
            {
                "item": ing["item"],
                "amount": scale_amount(ing["amount"], factor),
                "unit": ing["unit"],
                "display": describe_ingredient(ing["item"], ing["amount"], ing["unit"], factor),
            }
            for ing in recipe["ingredients"]
        ]
        return {
            "id": recipe["id"],
            "title": recipe["title"],
            "base_servings": recipe["servings"],
            "target_servings": int(target_servings),
            "scale_factor": round(factor, 4),
            "ingredients": lines,
            "steps": recipe["steps"],
            "note": "Seasoning to taste (salt, pepper, oils, spices) may need more than a linear cut for small batches." if factor < 1 else None,
        }

    # -- shopping list -----------------------------------------------------

    def shopping_list(
        self,
        recipe_ids: list[str],
        servings: dict | None = None,
        pantry: list[str] | None = None,
    ) -> dict:
        """Grouped shopping list with pantry-aware gaps.

        servings: optional {recipe_id: target_servings}; defaults to each
        recipe's base serving count. pantry: items you already have.
        """
        if not isinstance(recipe_ids, list) or not recipe_ids:
            raise ValueError("recipe_ids must be a non-empty list")
        pantry = list(pantry or [])
        servings = dict(servings or {})

        recipes = []
        for rid in recipe_ids:
            recipe = self.get_recipe(rid)
            target = servings.get(rid, recipe["servings"])
            if isinstance(target, bool) or not isinstance(target, (int, float)) or target <= 0:
                raise ValueError(f"servings for {rid!r} must be a positive number")
            recipes.append((recipe, float(target)))

        # Aggregate scaled amounts, keyed by (item, unit, category).
        buckets: dict[tuple, dict] = {}
        for recipe, target in recipes:
            factor = target / recipe["servings"]
            for ing in recipe["ingredients"]:
                key = (ing["item"], ing["unit"], categorize(ing["item"]))
                entry = buckets.setdefault(
                    key, {"amount": 0.0, "unit": ing["unit"], "categories": set()}
                )
                entry["amount"] = scale_amount(entry["amount"], 1.0) + ing["amount"] * factor

        have_list, shop = {}, defaultdict(list)
        for (item, unit, category), entry in buckets.items():
            amount = round(entry["amount"], 4)
            pretty = describe_ingredient(item, amount, unit)
            match = pantry_match(item, pantry)
            line = {
                "item": item,
                "amount": amount,
                "unit": unit,
                "display": pretty,
                "used_in": [r["title"] for r, _ in recipes if any(
                    i["item"] == item for i in r["ingredients"]
                )],
            }
            if match is not None:
                line["covered_by"] = match
                have_list[item] = line
            else:
                shop[category].append(line)

        groups = []
        for category in CATEGORY_ORDER:
            if category not in shop:
                continue
            items = sorted(shop[category], key=lambda x: x["item"])
            groups.append({
                "category": category,
                "items": items,
                "count": len(items),
            })

        return {
            "recipes": [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "servings": int(target),
                    "base_servings": r["servings"],
                }
                for r, target in recipes
            ],
            "shop_for": groups,
            "total_items_to_buy": sum(g["count"] for g in groups),
            "already_have": sorted(have_list.values(), key=lambda x: x["item"]),
            "note": group_pantry_aware(len(recipe_ids)),
        }
