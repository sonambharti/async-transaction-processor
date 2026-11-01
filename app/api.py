import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from app import repository
from app.log import log_event
from app.models import (
    HealthOut,
    TransactionOut,
    WebhookAck,
    WebhookIn,
    format_timestamp,
    to_json_number,
)

router = APIRouter()


@router.get("/", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status="HEALTHY", current_time=format_timestamp(datetime.now(UTC)))


@router.post(
    "/v1/webhooks/transactions",
    response_model=WebhookAck,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_webhook(webhook: WebhookIn, request: Request) -> WebhookAck:
    state = request.app.state
    async with asyncio.timeout(state.settings.db_command_timeout_seconds):
        result = await repository.insert_transaction(state.api_pool, webhook)

    if result.is_new:
        log_event(logging.INFO, "transaction.received", transaction_id=webhook.transaction_id)
    else:
        log_event(
            logging.WARNING if result.payload_differs else logging.INFO,
            "transaction.duplicate",
            transaction_id=webhook.transaction_id,
            payload_differs=result.payload_differs,
        )
    return WebhookAck(transaction_id=webhook.transaction_id)


@router.get("/v1/transactions/{transaction_id}", response_model=list[TransactionOut])
async def get_transaction(transaction_id: str, request: Request) -> list[TransactionOut]:
    state = request.app.state
    row = None
    if "\x00" not in transaction_id:
        async with asyncio.timeout(state.settings.db_command_timeout_seconds):
            row = await repository.get_transaction(state.api_pool, transaction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return [
        TransactionOut(
            transaction_id=row["transaction_id"],
            source_account=row["source_account"],
            destination_account=row["destination_account"],
            amount=to_json_number(row["amount"]),
            currency=row["currency"],
            status=row["status"],
            created_at=format_timestamp(row["created_at"]),
            processed_at=format_timestamp(row["processed_at"]) if row["processed_at"] else None,
        )
    ]
