"""A deliberately narrow grammar. Unknown text blocks the entire confirmation."""

import re
from typing import Protocol

from .models import Interpretation, Item


class Interpreter(Protocol):
    def interpret(self, text: str) -> Interpretation: ...


class RuleInterpreter:
    numbers = {
        "ein": 1,
        "eine": 1,
        "einen": 1,
        "eins": 1,
        "zwei": 2,
        "drei": 3,
        "vier": 4,
        "fünf": 5,
        "sechs": 6,
        "sieben": 7,
        "acht": 8,
        "neun": 9,
        "zehn": 10,
    }
    product = r"(?P<product>handtücher|handtuecher|handtuch|pizza(?: margherita)?|pizzen)"

    def interpret(self, text: str) -> Interpretation:
        normalized = re.sub(r"\s+", " ", text.lower().strip()).strip(".!? ")
        normalized = re.sub(
            r"^(?:ich (?:hätte gerne|hätte gern|möchte|brauche|bestelle)|bitte)\s+", "", normalized
        )
        normalized = re.sub(r"\s+bitte$", "", normalized)
        totals: dict[str, int] = {}
        questions: list[str] = []
        for part in re.split(r"\s+und\s+|,\s*", normalized):
            match = re.fullmatch(r"(?:(?P<qty>[0-9]+|[a-zäöü]+)\s+)?" + self.product, part)
            if not match:
                questions.append(
                    f"„{part}“ kann die Demo nicht eindeutig zuordnen. "
                    "Bitte nur Artikel und Menge angeben, z. B. „zwei Handtücher und eine Pizza“."
                )
                continue
            raw_quantity = match["qty"]
            quantity = (
                int(raw_quantity)
                if raw_quantity and raw_quantity.isdigit()
                else self.numbers.get(raw_quantity or "")
            )
            if quantity is None:
                questions.append(
                    f"Wie viele {match['product']}? Bitte eine Menge von 1 bis 20 nennen."
                )
                continue
            if not 1 <= quantity <= 20:
                questions.append("Bitte pro Artikel eine Menge von 1 bis 20 angeben.")
                continue
            kind = "towel" if match["product"].startswith("hand") else "pizza"
            totals[kind] = totals.get(kind, 0) + quantity
        if any(quantity > 20 for quantity in totals.values()):
            questions.append("Die Gesamtmenge je Artikel darf höchstens 20 betragen.")
        items = [Item(kind=kind, quantity=q) for kind, q in totals.items() if q <= 20]
        return Interpretation(items=items, questions=questions)
