"""Offline unit tests: run with `python -m unittest discover -s tests`."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recipes_mcp.quantities import (  # noqa: E402
    describe_ingredient,
    format_amount,
    parse_amount,
    scale_amount,
)
from recipes_mcp.storage import (  # noqa: E402
    RecipeStore,
    StorageError,
    validate_store_path,
)
from recipes_mcp.service import RecipeService, pantry_match  # noqa: E402
from recipes_mcp.server import build_server  # noqa: E402


def fresh_store(seed=True, keep=3):
    tmp = tempfile.mkdtemp(prefix="recipe-test-")
    store = RecipeStore(tmp, seed=seed, keep_backups=keep)
    return store, tmp


class QuantityTests(unittest.TestCase):
    def test_parse_amount_numbers(self):
        self.assertEqual(parse_amount(2), 2.0)
        self.assertEqual(parse_amount(1.5), 1.5)

    def test_parse_amount_strings(self):
        self.assertEqual(parse_amount("2"), 2.0)
        self.assertEqual(parse_amount("0.5"), 0.5)
        self.assertEqual(parse_amount("1/2"), 0.5)
        self.assertAlmostEqual(parse_amount("1 1/2"), 1.5)

    def test_parse_amount_rejects_junk(self):
        for bad in ("abc", "", None, "1 2 3", 0, -3, True):
            with self.assertRaises(ValueError, msg=str(bad)):
                parse_amount(bad)

    def test_scale_amount_factor(self):
        self.assertAlmostEqual(scale_amount(2.0, 2.5), 5.0)
        self.assertAlmostEqual(scale_amount(0.5, 3.0), 1.5)
        self.assertAlmostEqual(scale_amount(1.5, 1.0 / 3.0), 0.5, places=4)

    def test_scale_amount_rejects_bad_factor(self):
        with self.assertRaises(ValueError):
            scale_amount(2, 0)
        with self.assertRaises(ValueError):
            scale_amount(2, -1)

    def test_format_amount_fractions(self):
        self.assertEqual(format_amount(2.0), "2")
        self.assertEqual(format_amount(0.5), "1/2")
        self.assertEqual(format_amount(1.25), "1 1/4")
        self.assertEqual(format_amount(0.75), "3/4")

    def test_describe_ingredient_drops_unit_in_name(self):
        text = describe_ingredient("corn tortillas", 6, "tortillas")
        self.assertEqual(text, "6 corn tortillas")

    def test_describe_ingredient_pluralizes_cup(self):
        self.assertEqual(describe_ingredient("rice", 2, "cup"), "2 cups rice")
        self.assertEqual(describe_ingredient("rice", 0.5, "cup"), "1/2 cup rice")


PANTRY = ["chickpeas", "garlic", "olive oil", "onion", "coconut milk"]


class PantryMatchTests(unittest.TestCase):
    def test_exact_and_substring(self):
        self.assertEqual(pantry_match("garlic, minced", PANTRY), "garlic")
        self.assertEqual(pantry_match("olive oil", PANTRY), "olive oil")

    def test_plural_forms(self):
        self.assertEqual(pantry_match("chickpeas, canned (15 oz), drained", PANTRY), "chickpeas")
        self.assertEqual(pantry_match("onions", PANTRY), "onion")

    def test_prep_words_ignored(self):
        self.assertEqual(pantry_match("diced onion", PANTRY), "onion")

    def test_no_false_positive_similar_names(self):
        # 'garlic powder' / 'garlic salt' should NOT count as having garlic.
        self.assertIsNone(pantry_match("garlic powder", ["garlic"]))
        self.assertIsNone(pantry_match("garlic salt", ["garlic powder"]))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.store, self.dir = fresh_store()
        self.service = RecipeService(self.store)

    def test_add_recipe_normalizes_and_dedupes_ids(self):
        r1 = self.service.add_recipe({"title": "Snack Mix", "servings": 2,
                                      "ingredients": [{"item": "pretzels", "amount": 2, "unit": "cups"}]})
        r2 = self.service.add_recipe({"title": "Snack Mix", "servings": 4,
                                      "ingredients": [{"item": "pretzels", "amount": 4, "unit": "cups"}]})
        self.assertEqual(r1["id"], "snack-mix")
        self.assertEqual(r2["id"], "snack-mix-2")
        self.assertEqual(r1["ingredients"][0]["item"], "pretzels")
        self.assertEqual(r2["servings"], 4)

    def test_add_recipe_rejects_bad_input(self):
        for bad in (
            {"title": "", "servings": 2, "ingredients": [{"item": "x"}]},
            {"title": "Y", "servings": 0, "ingredients": [{"item": "x"}]},
            {"title": "Y", "servings": 2.5, "ingredients": [{"item": "x"}]},
            {"title": "Y", "servings": 2, "ingredients": []},
            {"title": "Y", "servings": 2},
            {"title": "Y", "servings": 2, "ingredients": [{"item": "x", "amount": -1}]},
            {"title": "Y", "servings": 2, "ingredients": [{"amount": 1}]},
        ):
            with self.assertRaises(ValueError, msg=json.dumps(bad)):
                self.service.add_recipe(bad)

    def test_persistence_across_stores(self):
        title = "Test Pie " + "z" * 20
        self.service.add_recipe({"title": title, "servings": 1, "ingredients": [{"item": "crust", "amount": 1}]})
        store2 = RecipeStore(self.dir, seed=False)
        service2 = RecipeService(store2)
        found = service2.search(query="test pie")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], "test-pie" + "-" + "z" * 20)

    def test_search_ranking_by_ingredients_on_hand(self):
        results = self.service.search(ingredients_on_hand=["garlic", "olive oil", "onion"])
        self.assertEqual(results[0]["id"], "weeknight-chickpea-curry")
        self.assertLessEqual(results[0]["you_have_ratio"], 1.0)
        self.assertGreaterEqual(results[-1]["you_have_ratio"], 0.0)
        self.assertGreaterEqual(results[0]["you_have_ratio"], results[-1]["you_have_ratio"])

    def test_search_tags_and_query(self):
        tag_results = self.service.search(tags=["vegetarian"])
        self.assertTrue({"weeknight-chickpea-curry", "black-bean-tacos"} <=
                        {r["id"] for r in tag_results})
        combo = self.service.search(tags=["vegetarian"], query="taco")
        self.assertEqual([r["id"] for r in combo], ["black-bean-tacos"])
        self.assertEqual(self.service.search(query="zzznope"), [])

    def test_search_missing_ingredients_listed(self):
        results = self.service.search(ingredients_on_hand=["garlic"])
        chili = next(r for r in results if r["id"] == "sunday-night-chili")
        self.assertIn("ground beef", chili["missing_ingredients"])
        self.assertIn("garlic, minced", chili["matched_ingredients"])

    def test_scale_recipe_up_and_down(self):
        scaled = self.service.scale("garlic-butter-pasta", 5)
        self.assertEqual(scaled["scale_factor"], 2.5)
        amounts = {i["item"]: i["amount"] for i in scaled["ingredients"]}
        self.assertEqual(amounts["spaghetti"], 20.0)
        self.assertEqual(amounts["butter"], 7.5)
        self.assertEqual(amounts["parmesan, grated"], 1.25)
        down = self.service.scale("sunday-night-chili", 2)
        self.assertLess(down["scale_factor"], 1)
        self.assertIn("note", down)

    def test_scale_rejects_bad_servings(self):
        for bad in (0, -2, 1.5, "3", None, True):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.service.scale("garlic-butter-pasta", bad)

    def test_shopping_list_grouping_and_pantry(self):
        from recipes_mcp.service_shopping import CATEGORY_ORDER
        order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
        li = self.service.shopping_list(
            ["weeknight-chickpea-curry", "garlic-butter-pasta"],
            servings={"weeknight-chickpea-curry": 2},
            pantry=["olive oil", "garlic", "coconut milk", "spinach", "curry powder", "ginger", "onion", "tomatoes"],
        )
        categories = [g["category"] for g in li["shop_for"]]
        self.assertEqual(categories, sorted(categories, key=lambda c: order[c]))
        buy_items = {i["item"] for g in li["shop_for"] for i in g["items"]}
        self.assertIn("spaghetti", buy_items)
        self.assertIn("butter", buy_items)
        have_items = {i["item"] for i in li["already_have"]}
        # chickpeas: 2 cans x (2/4 factor) = 1 can to buy, so it stays on the list
        self.assertIn("chickpeas, canned (15 oz), drained", buy_items)
        self.assertNotIn("garlic, minced", buy_items)
        self.assertIn("garlic, minced", have_items)
        labels = [i["display"] for g in li["shop_for"] for i in g["items"]]
        self.assertIn("1 can chickpeas, canned (15 oz), drained", labels)
        self.assertIn("8 oz spaghetti", labels)
        self.assertIn("3 tablespoons butter", labels)

    def test_shopping_list_requires_recipes(self):
        with self.assertRaises(ValueError):
            self.service.shopping_list([])
        with self.assertRaises(KeyError):
            self.service.shopping_list(["nonexistent"])

    def test_delete_recipe(self):
        self.assertTrue(self.service.delete_recipe("black-bean-tacos"))
        self.assertFalse(self.service.delete_recipe("black-bean-tacos"))
        with self.assertRaises(KeyError):
            self.service.get_recipe("black-bean-tacos")


class StorageSecurityTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="recipe-sec-"))

    def test_starts_with_five_starter_recipes(self):
        store = RecipeStore(self.base, seed=True)
        self.assertEqual(len(store.recipes), 5)
        self.assertTrue((self.base / "recipes.json").exists())

    def test_store_path_must_be_inside_base(self):
        with self.assertRaises(StorageError):
            validate_store_path(self.base / "sub" / "recipes.json", self.base)

    def test_store_path_must_be_named_recipes_json(self):
        with self.assertRaises(StorageError):
            validate_store_path(self.base / "other.json", self.base)

    def test_traversal_rejected(self):
        evil = self.base / ".." / "elsewhere" / "recipes.json"
        with self.assertRaises(StorageError):
            validate_store_path(evil, self.base)

    def test_symlink_escape_rejected(self):
        outside = Path(tempfile.mkdtemp(prefix="outside-")) / "recipes.json"
        outside.write_text("{}", encoding="utf-8")
        inside = self.base / "recipes.json"
        try:
            inside.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unsupported")
        with self.assertRaises(StorageError):
            validate_store_path(inside, self.base)

    def test_corrupt_file_recovers_from_backup(self):
        store = RecipeStore(self.base, seed=True)
        (self.base / "recipes.json").write_text("{corrupt", encoding="utf-8")
        recovered = RecipeStore(self.base, seed=False)
        # Recovery must fall back to the pre-corruption backup (5 starters),
        # never crash and never seed silently over a corrupt file.
        self.assertEqual(len(recovered.recipes), 5)

    def test_backups_rotate(self):
        store = RecipeStore(self.base, seed=True, keep_backups=2)
        service = RecipeService(store)
        for n in range(5):
            service.add_recipe({"title": f"Rotate {n}", "servings": 1,
                                "ingredients": [{"item": "a", "amount": 1}]})
        backups = store.list_backups()
        self.assertLessEqual(len(backups), 2)
        self.assertTrue(all(b.name.startswith("recipes.json.bak-") for b in backups))
        newest = backups[0]
        data = json.loads(newest.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["recipes"]), 6)

    def test_root_data_dir_rejected(self):
        with self.assertRaises(StorageError):
            RecipeStore.validate_data_dir("/")

    def test_file_as_data_dir_rejected(self):
        f = self.base / "notadir"
        f.write_text("x", encoding="utf-8")
        with self.assertRaises(StorageError):
            RecipeStore.validate_data_dir(str(f))


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.server, self.store = build_server(tempfile.mkdtemp(prefix="recipe-proto-"))

    def rpc(self, method, params=None, req_id=1, **overrides):
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        msg.update(overrides)
        return self.server.handle_message(msg)

    def test_initialize_handshake(self):
        r = self.rpc("initialize", {})
        self.assertEqual(r["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("tools", r["result"]["capabilities"])
        self.assertEqual(r["result"]["serverInfo"]["name"], "recipe-mcp-server")

    def test_notification_gets_no_response(self):
        self.assertIsNone(self.rpc("notifications/initialized", req_id=None))
        self.assertIsNone(self.rpc("this-does-not-exist", req_id=None))

    def test_unknown_method_is_error(self):
        r = self.rpc("no/such/method")
        self.assertEqual(r["error"]["code"], -32601)

    def test_tools_list_and_call(self):
        tools = self.rpc("tools/list")["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertTrue({"add_recipe", "search_recipes", "scale_recipe", "shopping_list",
                         "get_recipe", "list_recipes", "delete_recipe"} <= names)
        each_schema = all("inputSchema" in t for t in tools)
        self.assertTrue(each_schema)
        r = self.rpc("tools/call", {"name": "list_recipes", "arguments": {}})
        self.assertIn("weeknight-chickpea-curry", r["result"]["content"][0]["text"])
        self.assertFalse(r["result"]["isError"])

    def test_tool_errors_are_flagged_not_raised(self):
        r = self.rpc("tools/call", {"name": "get_recipe", "arguments": {"recipe_id": "nope"}})
        self.assertTrue(r["result"]["isError"])
        self.assertIn("Error", r["result"]["content"][0]["text"])
        r = self.rpc("tools/call", {"name": "unknown_tool", "arguments": {}})
        self.assertEqual(r["error"]["code"], -32602)

    def test_ping_and_malformed(self):
        self.assertEqual(self.rpc("ping")["result"], {})
        self.assertEqual(self.server.handle_message({"id": 1, "method": None})["error"]["code"], -32600)
        self.assertEqual(
            self.server.handle_message("not a dict")["error"]["code"], -32600
        )


if __name__ == "__main__":
    unittest.main()
