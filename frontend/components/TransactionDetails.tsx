"use client";

import { useState } from "react";
import type { WebhookPayload } from "@/lib/api";
import type { TrackedRow } from "@/lib/storage";

type TransactionDetailsProps = {
  row: TrackedRow;
  onResend: (payload: WebhookPayload) => Promise<boolean>;
};

export function TransactionDetails({ row, onResend }: TransactionDetailsProps) {
  const [sending, setSending] = useState(false);
  const { transaction } = row;

  const resend = async () => {
    if (!transaction) return;
    setSending(true);
    await onResend({
      transaction_id: transaction.transaction_id,
      source_account: transaction.source_account,
      destination_account: transaction.destination_account,
      amount: transaction.amount,
      currency: transaction.currency,
    });
    setSending(false);
  };

  return (
    <section className="panel" aria-label="Transaction details">
      <div className="panel-title">
        <h2 className="mono">{row.id}</h2>
        {transaction && (
          <button type="button" className="button" disabled={sending} onClick={resend}>
            {sending ? "Sending" : "Resend"}
          </button>
        )}
      </div>
      {transaction ? (
        <pre className="code mono">{JSON.stringify([transaction], null, 2)}</pre>
      ) : (
        <p className="muted">
          {row.missing ? "The service has no record of this transaction." : "Loading"}
        </p>
      )}
    </section>
  );
}
