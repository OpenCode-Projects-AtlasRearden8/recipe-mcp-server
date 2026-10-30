"""Starter recipe set: small, realistic, and free of any personal data."""

from __future__ import annotations


def starter_recipes() -> list[dict]:
    return [
        {
            "title": "Weeknight Chickpea Curry",
            "servings": 4,
            "tags": ["vegetarian", "weeknight", "curry"],
            "source": "starter set",
            "ingredients": [
                {"item": "chickpeas, canned (15 oz), drained", "amount": 2, "unit": "cans"},
                {"item": "onion, diced", "amount": 1, "unit": "medium"},
                {"item": "garlic, minced", "amount": 3, "unit": "cloves"},
                {"item": "ginger, grated", "amount": 1, "unit": "tbsp"},
                {"item": "curry powder", "amount": 2, "unit": "tbsp"},
                {"item": "diced tomatoes", "amount": 1, "unit": "can"},
                {"item": "coconut milk", "amount": 1, "unit": "cup"},
                {"item": "spinach", "amount": 2, "unit": "cups"},
                {"item": "olive oil", "amount": 2, "unit": "tbsp"},
            ],
            "steps": [
                "Warm the oil over medium heat and cook the onion until soft, about 5 minutes.",
                "Add garlic, ginger and curry powder; cook 1 minute until fragrant.",
                "Stir in tomatoes, chickpeas and coconut milk. Simmer 15 minutes.",
                "Fold in the spinach until wilted, season with salt, and serve over rice.",
            ],
        },
        {
            "title": "Garlic Butter Pasta",
            "servings": 2,
            "tags": ["weeknight", "pasta", "quick"],
            "source": "starter set",
            "ingredients": [
                {"item": "spaghetti", "amount": 8, "unit": "oz"},
                {"item": "butter", "amount": 3, "unit": "tbsp"},
                {"item": "garlic, thinly sliced", "amount": 4, "unit": "cloves"},
                {"item": "parmesan, grated", "amount": 0.5, "unit": "cup"},
                {"item": "black pepper", "amount": 0.5, "unit": "tsp"},
                {"item": "lemon zest", "amount": 1, "unit": "tsp"},
            ],
            "steps": [
                "Cook spaghetti in salted water until al dente; reserve 1/2 cup pasta water.",
                "Melt butter with garlic over low heat until golden, about 3 minutes.",
                "Toss pasta with the garlic butter, adding pasta water to loosen.",
                "Finish with parmesan, pepper and lemon zest off the heat.",
            ],
        },
        {
            "title": "Sheet-Pan Salmon and Potatoes",
            "servings": 3,
            "tags": ["weeknight", "fish", "one-pan"],
            "source": "starter set",
            "ingredients": [
                {"item": "salmon fillets", "amount": 3, "unit": "fillets"},
                {"item": "baby potatoes, halved", "amount": 1, "unit": "lb"},
                {"item": "lemon, sliced", "amount": 1, "unit": "whole"},
                {"item": "olive oil", "amount": 3, "unit": "tbsp"},
                {"item": "dijon mustard", "amount": 1, "unit": "tbsp"},
                {"item": "thyme", "amount": 1, "unit": "tsp"},
            ],
            "steps": [
                "Heat oven to 425 F and toss potatoes with oil, salt and thyme on a sheet pan.",
                "Roast potatoes 20 minutes, then add salmon and lemon slices.",
                "Return to oven 10-12 minutes until salmon flakes easily.",
                "Whisk remaining oil with dijon and spoon over the salmon to serve.",
            ],
        },
        {
            "title": "Black Bean Tacos",
            "servings": 2,
            "tags": ["vegetarian", "weeknight", "mexican"],
            "source": "starter set",
            "ingredients": [
                {"item": "black beans, canned (15 oz), drained", "amount": 1, "unit": "can"},
                {"item": "corn tortillas", "amount": 6, "unit": "tortillas"},
                {"item": "avocado", "amount": 1, "unit": "whole"},
                {"item": "lime", "amount": 1, "unit": "whole"},
                {"item": "red cabbage, shredded", "amount": 1, "unit": "cup"},
                {"item": "cumin", "amount": 1, "unit": "tsp"},
                {"item": "smoked paprika", "amount": 1, "unit": "tsp"},
                {"item": "olive oil", "amount": 1, "unit": "tbsp"},
            ],
            "steps": [
                "Saute black beans with cumin and smoked paprika in the oil for 5 minutes.",
                "Warm tortillas in a dry pan until soft and lightly charred.",
                "Shred the cabbage and toss with lime juice and a pinch of salt.",
                "Build tacos with beans, cabbage and sliced avocado.",
            ],
        },
        {
            "title": "Sunday Night Chili",
            "servings": 6,
            "tags": ["batch", "beef", "comfort", "freezer"],
            "source": "starter set",
            "ingredients": [
                {"item": "ground beef", "amount": 1.5, "unit": "lb"},
                {"item": "onion, diced", "amount": 1, "unit": "whole"},
                {"item": "garlic, minced", "amount": 4, "unit": "cloves"},
                {"item": "chili powder", "amount": 3, "unit": "tbsp"},
                {"item": "diced tomatoes", "amount": 2, "unit": "cans"},
                {"item": "red kidney beans, canned (15 oz), drained", "amount": 2, "unit": "cans"},
                {"item": "beef broth", "amount": 1, "unit": "cup"},
                {"item": "cocoa powder", "amount": 1, "unit": "tsp"},
            ],
            "steps": [
                "Brown the beef with onion and garlic in a Dutch oven.",
                "Add chili powder and cocoa; cook 30 seconds.",
                "Add tomatoes, beans and broth. Simmer uncovered 45 minutes, stirring now and then.",
                "Rest 10 minutes before serving. Makes great leftovers and freezes well.",
            ],
        },
    ]
