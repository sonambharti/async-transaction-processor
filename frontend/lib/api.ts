const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const WEBHOOK_PATH = "/v1/webhooks/transactions";

export type WebhookPayload = {
  transaction_id: string;
  source_account: string;
  destination_account: string;
  amount: number;
  currency: string;
};

export type Transaction = WebhookPayload & {
  status: "PROCESSING" | "PROCESSED";
  created_at: string;
  processed_at: string | null;
};

export type Health = {
  status: string;
  current_time: string;
};

export type WebhookResult = {
  status: number;
  latencyMs: number;
  body: unknown;
};

export async function sendWebhook(payload: WebhookPayload): Promise<WebhookResult> {
  const started = performance.now();
  const response = await fetch(`${API_URL}${WEBHOOK_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const latencyMs = performance.now() - started;
  const body: unknown = await response.json().catch(() => null);
  return { status: response.status, latencyMs, body };
}

export async function fetchTransaction(id: string): Promise<Transaction[] | null> {
  const response = await fetch(`${API_URL}/v1/transactions/${encodeURIComponent(id)}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Query failed with ${response.status}`);
  return response.json();
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch(`${API_URL}/`);
  if (!response.ok) throw new Error(`Health check failed with ${response.status}`);
  return response.json();
}
