import pytest

from app.interpreter import RuleInterpreter


@pytest.mark.parametrize(
    "text",
    [
        "Zwei Handtücher und eine Pizza",
        "Ich hätte gerne zwei Handtücher und eine Pizza.",
        "Bitte 2 Handtücher, 1 Pizza",
        "2 Handtuecher und eine Pizza Margherita bitte",
    ],
)
def test_recognized(text):
    result = RuleInterpreter().interpret(text)
    assert not result.questions
    assert {i.kind: i.quantity for i in result.items} == {"towel": 2, "pizza": 1}


@pytest.mark.parametrize(
    "text",
    [
        "Handtücher",
        "Pizza",
        "zwei Handtücher und Wein",
        "zwei Handtücher ohne Pizza",
        "zwei Handtücher morgen",
        "zwei Handtücher und eine Pizza Salami",
        "-2 Handtücher",
        "0 Handtücher",
        "21 Handtücher",
        "2.5 Handtücher",
        "2,5 Handtücher",
        "",
        "Keine Pizza",
        "20 Handtücher und 2 Handtücher",
        "<script>alert(1)</script>",
    ],
)
def test_ambiguous_or_unsupported_text_requires_clarification(text):
    assert RuleInterpreter().interpret(text).questions


def test_repeated_item_is_aggregated():
    result = RuleInterpreter().interpret("2 Handtücher und 3 Handtücher")
    assert not result.questions
    assert len(result.items) == 1 and result.items[0].quantity == 5
