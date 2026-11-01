from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

BoundedString = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class WebhookIn(BaseModel):
    transaction_id: BoundedString
    source_account: BoundedString
    destination_account: BoundedString
    amount: Decimal = Field(gt=0, max_digits=30, allow_inf_nan=False)
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$")]

    @field_validator("transaction_id", "source_account", "destination_account")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        # PostgreSQL text cannot store NUL, so this would otherwise surface as a 503.
        if "\x00" in value:
            raise ValueError("must not contain NUL characters")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class WebhookAck(BaseModel):
    status: str = "ACCEPTED"
    transaction_id: str


class TransactionOut(BaseModel):
    transaction_id: str
    source_account: str
    destination_account: str
    amount: int | float
    currency: str
    status: str
    created_at: str
    processed_at: str | None


class HealthOut(BaseModel):
    status: str
    current_time: str


def format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_json_number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)
