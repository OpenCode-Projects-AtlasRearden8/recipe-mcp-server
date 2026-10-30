"""Ingredient categorization for grouped shopping lists."""

from __future__ import annotations

from collections import OrderedDict

# Ordered keyword -> category map; first keyword hit wins, checked top to bottom.
_PRODUCE = ["avocado", "lemon", "lime", "onion", "garlic", "ginger", "spinach", "cabbage",
            "potato", "tomato", "lettuce", "carrot", "celery", "apple", "banana", "zucchini",
            "pepper", "mushroom", "broccoli", "herb", "basil", "cilantro", "parsley", "thyme",
            "zest", "produce"]
_PROTEIN = ["beef", "chicken", "salmon", "fish", "shrimp", "pork", "turkey", "egg", "tofu",
            "sausage", "meat", "steak", "chickpea", "black bean", "kidney", "lentils", "beans"]
_DAIRY = ["milk", "butter", "cheese", "parmesan", "yogurt", "cream", "mozzarella", "dairy"]
_SPICES = ["powder", "paprika", "cumin", "cinnamon", "oregano", "salt", "pepper flakes",
           "seasoning", "spice", "curry", "turmeric", "cocoa", "vanilla"]
_PANTRY = ["oil", "olive oil", "rice", "pasta", "spaghetti", "noodle", "flour", "sugar",
           "broth", "stock", "tortilla", "vinegar", "soy sauce", "tomatoes", "honey",
           "oat", "canned", "mustard", "pantry"]
_FREEZER = ["frozen", "ice cream", "freezer"]

CATEGORY_ORDER = ["produce", "protein", "dairy", "spices & condiments", "pantry",
                  "frozen", "other"]
_ORDER_INDEX = {c: i for i, c in enumerate(CATEGORY_ORDER)}


def categorize(item: str) -> str:
    """Cheap keyword categorizer tuned for home-cooking ingredient names."""
    text = item.lower()
    if "pepper" in text:
        # Black/white/cayenne pepper & flakes = spice rack; peppers you chop = produce.
        if any(k in text for k in ("black", "white", "cayenne", "coriander", "flakes")):
            return "spices & condiments"
        if any(k in text for k in ("bell", "jalapen", "chipotle", "serrano")):
            return "produce"
    for category, keywords in (
        ("produce", _PRODUCE),
        ("protein", _PROTEIN),
        ("dairy", _DAIRY),
        ("spices & condiments", _SPICES),
        ("frozen", _FREEZER),
        ("pantry", _PANTRY),
    ):
        if any(k in text for k in keywords):
            return category
    return "other"


def group_pantry_aware(recipe_count: int) -> str:
    return (
        "Items under 'already_have' matched your pantry by name; double-check "
        f"quantities before cooking. Menu covers {recipe_count} recipe(s)."
    )
