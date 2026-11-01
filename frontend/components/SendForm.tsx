"use client";

import { useState, type FormEvent } from "react";
import type { WebhookPayload } from "@/lib/api";

export type FieldErrors = Record<string, string>;

type SendFormProps = {
  errors: FieldErrors;
  summary: string | null;
  onSend: (payload: WebhookPayload) => Promise<boolean>;
  onSendDuplicates: (payload: WebhookPayload, count: number) => Promise<boolean>;
};

type TextFieldProps = {
  name: string;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
  inputMode?: "text" | "decimal";
};

function newTransactionId(): string {
  return `txn_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
}

function TextField({ name, label, value, error, onChange, inputMode = "text" }: TextFieldProps) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        className="mono"
        value={value}
        inputMode={inputMode}
        spellCheck={false}
        autoComplete="off"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error && (
        <span id={`${name}-error`} className="field-error">
          {error}
        </span>
      )}
    </div>
  );
}

export function SendForm({ errors, summary, onSend, onSendDuplicates }: SendFormProps) {
  const [transactionId, setTransactionId] = useState(newTransactionId);
  const [sourceAccount, setSourceAccount] = useState("acc_user_789");
  const [destinationAccount, setDestinationAccount] = useState("acc_merchant_456");
  const [amount, setAmount] = useState("1500");
  const [currency, setCurrency] = useState("INR");
  const [duplicateCount, setDuplicateCount] = useState("10");
  const [sending, setSending] = useState(false);

  const payload = (): WebhookPayload => ({
    transaction_id: transactionId,
    source_account: sourceAccount,
    destination_account: destinationAccount,
    amount: Number(amount),
    currency,
  });

  const run = async (action: () => Promise<boolean>) => {
    setSending(true);
    const accepted = await action();
    if (accepted) setTransactionId(newTransactionId());
    setSending(false);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    run(() => onSend(payload()));
  };

  const count = Math.min(Math.max(Number.parseInt(duplicateCount, 10) || 2, 2), 50);

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Send webhook</h2>

      <div className="field">
        <label htmlFor="transaction_id">transaction_id</label>
        <div className="input-row">
          <input
            id="transaction_id"
            className="mono"
            value={transactionId}
            spellCheck={false}
            autoComplete="off"
            aria-invalid={Boolean(errors.transaction_id)}
            aria-describedby={errors.transaction_id ? "transaction_id-error" : undefined}
            onChange={(event) => setTransactionId(event.target.value)}
          />
          <button
            type="button"
            className="button"
            onClick={() => setTransactionId(newTransactionId())}
          >
            Regenerate
          </button>
        </div>
        {errors.transaction_id && (
          <span id="transaction_id-error" className="field-error">
            {errors.transaction_id}
          </span>
        )}
      </div>

      <TextField
        name="source_account"
        label="source_account"
        value={sourceAccount}
        error={errors.source_account}
        onChange={setSourceAccount}
      />
      <TextField
        name="destination_account"
        label="destination_account"
        value={destinationAccount}
        error={errors.destination_account}
        onChange={setDestinationAccount}
      />

      <div className="field-pair">
        <TextField
          name="amount"
          label="amount"
          value={amount}
          error={errors.amount}
          inputMode="decimal"
          onChange={setAmount}
        />
        <TextField
          name="currency"
          label="currency"
          value={currency}
          error={errors.currency}
          onChange={setCurrency}
        />
      </div>

      <div className="actions">
        <button type="submit" className="button button-primary" disabled={sending}>
          {sending ? "Sending" : "Send webhook"}
        </button>
        <div className="duplicates">
          <button
            type="button"
            className="button"
            disabled={sending}
            onClick={() => run(() => onSendDuplicates(payload(), count))}
          >
            Send duplicates: {count}
          </button>
          <input
            className="mono"
            type="number"
            min={2}
            max={50}
            value={duplicateCount}
            aria-label="Number of duplicates"
            onChange={(event) => setDuplicateCount(event.target.value)}
          />
        </div>
      </div>

      {summary && <p className="result mono">{summary}</p>}
    </form>
  );
}
