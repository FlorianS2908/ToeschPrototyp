"""Validated contracts shared by API, interpreter and service adapters."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ItemKind = Literal["towel", "pizza"]
ServiceName = Literal["housekeeping", "kitchen"]
FaultMode = Literal["normal", "offline", "lose_response_once"]
ITEMS = {
    "towel": {"label": "Handtücher", "service": "housekeeping"},
    "pizza": {"label": "Pizza Margherita", "service": "kitchen"},
}
STATUS_LABELS = {
    "saved": "Gespeichert",
    "uncertain": "Rückmeldung unklar",
    "transmitted": "Übermittelt",
    "in_progress": "In Bearbeitung",
    "completed": "Erledigt",
}
STATUS_RANK = {key: i for i, key in enumerate(STATUS_LABELS)}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Item(Contract):
    kind: ItemKind
    quantity: int = Field(strict=True, ge=1, le=20)


class InterpretInput(Contract):
    stay_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=500)


class Interpretation(Contract):
    items: list[Item]
    questions: list[str]
    source: str = "Regelbasierter Simulator · kein Sprachmodell"


class OrderInput(Contract):
    stay_id: str = Field(min_length=1, max_length=80)
    items: list[Item] = Field(min_length=1, max_length=2)
    allow_additional: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def unique_items(self):
        if len({item.kind for item in self.items}) != len(self.items):
            raise ValueError("Jeden Artikel nur einmal mit seiner Gesamtmenge angeben.")
        return self


class ModeInput(Contract):
    mode: FaultMode


class AdvanceInput(Contract):
    status: Literal["in_progress", "completed"]


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, **details):
        self.status = status
        self.detail = {"code": code, "message": message, **details}
        super().__init__(message)
