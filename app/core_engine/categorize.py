from __future__ import annotations

import re

CATEGORY_RULES: dict[str, list[str]] = {
    "Rent & Utilities": [
        "rent",
        "lease",
        "landlord",
        "electricity",
        "power bill",
        "water bill",
        "gas bill",
        "utility",
        "utilities",
        "broadband",
        "internet",
        "wifi",
        "housing",
        "maintenance",
        "society",
        "bsnl",
        "jio fiber",
        "airtel broadband",
    ],
    "Payroll": [
        "salary",
        "payroll",
        "wages",
        "compensation",
        "bonus",
        "stipend",
        "provident fund",
        "pf contribution",
        "esi",
        "employee",
    ],
    "Software & Tools": [
        "aws",
        "amazon web services",
        "azure",
        "gcp",
        "google cloud",
        "github",
        "gitlab",
        "slack",
        "notion",
        "figma",
        "adobe",
        "microsoft",
        "office 365",
        "zoom",
        "dropbox",
        "saas",
        "heroku",
        "digitalocean",
        "openai",
        "cursor",
        "software",
        "subscription",
    ],
    "Travel": [
        "uber",
        "ola",
        "irctc",
        "makemytrip",
        "goibibo",
        "cleartrip",
        "indigo",
        "spicejet",
        "air india",
        "vistara",
        "hotel",
        "flight",
        "travel",
        "taxi",
        "cab",
        "petrol",
        "fuel",
        "parking",
        "toll",
    ],
    "Food": [
        "zomato",
        "swiggy",
        "dominos",
        "pizza",
        "restaurant",
        "cafe",
        "food",
        "lunch",
        "dinner",
        "breakfast",
        "mcdonalds",
        "kfc",
        "starbucks",
    ],
    "Taxes & Compliance": [
        "gst",
        "tax",
        "tds",
        "itr",
        "income tax",
        "compliance",
        "chartered accountant",
        "ca fees",
        "vat",
        "professional tax",
    ],
}

NOISE_TOKENS = frozenset(
    {
        "upi",
        "neft",
        "imps",
        "rtgs",
        "cr",
        "dr",
        "txn",
        "ref",
        "inr",
        "payment",
        "transfer",
        "bank",
        "acct",
        "account",
    }
)

_SPLIT_PATTERN = re.compile(r"[-/_]+")
_ID_LIKE_PATTERN = re.compile(r"^[a-z0-9@.]{6,}$", re.IGNORECASE)


def clean_description(description: str) -> str:
    """Strip UPI/NEFT/banking noise and return text ready for keyword matching."""
    parts = _SPLIT_PATTERN.split(description.strip())
    meaningful: list[str] = []

    for part in parts:
        token = part.strip()
        if not token:
            continue
        if token.casefold() in NOISE_TOKENS:
            continue
        if _is_id_like(token):
            continue
        meaningful.append(token)

    return " ".join(meaningful).casefold()


def _is_id_like(segment: str) -> bool:
    if segment.isdigit():
        return True

    digit_count = sum(character.isdigit() for character in segment)
    if digit_count == len(segment):
        return True

    if len(segment) >= 8 and digit_count / len(segment) >= 0.6:
        return True

    if _ID_LIKE_PATTERN.match(segment) and digit_count >= 4:
        return True

    return False


def categorize_transaction(description: str, direction: str) -> str:
    """Assign a category based on cleaned description and transaction direction."""
    cleaned = clean_description(description)

    for category, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            if keyword.casefold() in cleaned:
                return category

    normalized_direction = direction.strip().casefold()
    if normalized_direction == "credit":
        return "Revenue"
    return "Uncategorized"


def categorize_transactions_batch(transactions: list[dict]) -> list[dict]:
    """Categorize a batch of transactions, adding a category field to each."""
    return [
        {
            **transaction,
            "category": categorize_transaction(
                transaction["description"],
                transaction["direction"],
            ),
        }
        for transaction in transactions
    ]


if __name__ == "__main__":
    test_cases = [
        (
            "UPI noise with food delivery keyword",
            {"description": "UPI-987654321-ZOMATO", "direction": "debit"},
            "Food",
        ),
        (
            "Payroll keyword",
            {"description": "NEFT/CR/SALARY JAN 2026", "direction": "debit"},
            "Payroll",
        ),
        (
            "Software subscription",
            {"description": "DR/AMAZON WEB SERVICES INDIA", "direction": "debit"},
            "Software & Tools",
        ),
        (
            "Credit with no keyword match",
            {"description": "UPI/CR/123456789/CUSTOMER PAYMENT", "direction": "credit"},
            "Revenue",
        ),
        (
            "Debit with no keyword match",
            {"description": "UPI/DR/789012345/MISC", "direction": "debit"},
            "Uncategorized",
        ),
        (
            "Travel keyword",
            {"description": "IMPS_UBER TRIP MUMBAI", "direction": "debit"},
            "Travel",
        ),
    ]

    for label, transaction, expected in test_cases:
        category = categorize_transaction(
            transaction["description"],
            transaction["direction"],
        )
        print(f"=== {label} ===")
        print(f"description: {transaction['description']}")
        print(f"direction:   {transaction['direction']}")
        print(f"cleaned:     {clean_description(transaction['description'])}")
        print(f"category:    {category}")
        print(f"expected:    {expected}")
        print(f"pass:        {category == expected}")
        print()

    batch_result = categorize_transactions_batch(
        [transaction for _, transaction, _ in test_cases]
    )
    print("=== Batch categorization ===")
    for item in batch_result:
        print(item)
