"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchHealth,
  fetchTransaction,
  sendWebhook,
  WEBHOOK_PATH,
  type Health,
  type WebhookPayload,
  type WebhookResult,
} from "@/lib/api";
import { loadRows, loadTheme, saveRows, saveTheme, type Theme, type TrackedRow } from "@/lib/storage";
import { RequestLog, type LogEntry } from "@/components/RequestLog";
import { SendForm, type FieldErrors } from "@/components/SendForm";
import { TransactionDetails } from "@/components/TransactionDetails";
import { TransactionList } from "@/components/TransactionList";

const HEALTH_INTERVAL_MS = 10_000;
const STATUS_INTERVAL_MS = 2_000;
const MAX_LOG_ENTRIES = 50;

type Banner = "network" | "save" | null;

const BANNER_TEXT = {
  network: "Could not reach the service.",
  save: "The service could not save this transaction. Nothing was stored, so it is safe to send again.",
};

const FIELD_MESSAGES: Record<string, string> = {
  amount: "Enter a number greater than 0.",
  currency: "Enter a 3-letter currency code, such as INR.",
};

function isSettled(row: TrackedRow): boolean {
  return row.missing || row.transaction?.status === "PROCESSED";
}

function fieldErrorsFrom(body: unknown): FieldErrors {
  const errors: FieldErrors = {};
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (Array.isArray(detail)) {
    for (const item of detail as { loc?: unknown[]; msg?: string }[]) {
      const field = item.loc?.at(-1);
      if (typeof field === "string") {
        errors[field] = FIELD_MESSAGES[field] ?? item.msg ?? "Invalid value";
      }
    }
  }
  return errors;
}

export function Console() {
  const [rows, setRows] = useState<TrackedRow[]>(loadRows);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [health, setHealth] = useState<Health | null | "down">(null);
  const [banner, setBanner] = useState<Banner>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [summary, setSummary] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [now, setNow] = useState(Date.now);
  const [theme, setTheme] = useState<Theme | null>(loadTheme);
  const logId = useRef(0);

  useEffect(() => saveRows(rows), [rows]);

  useEffect(() => {
    if (theme) {
      document.documentElement.dataset.theme = theme;
      saveTheme(theme);
    }
  }, [theme]);

  useEffect(() => {
    const check = () =>
      fetchHealth()
        .then((result) => {
          setHealth(result);
          setBanner((current) => (current === "network" ? null : current));
        })
        .catch(() => setHealth("down"));
    check();
    const timer = setInterval(check, HEALTH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  const pendingKey = useMemo(
    () => rows.filter((row) => !isSettled(row)).map((row) => row.id).join(","),
    [rows],
  );

  useEffect(() => {
    if (!pendingKey) return;
    const ids = pendingKey.split(",");

    const poll = () =>
      ids.forEach(async (id) => {
        try {
          const result = await fetchTransaction(id);
          const transaction = result?.[0] ?? null;
          if (transaction?.status === "PROCESSED") {
            setAnnouncement(`${id} processed`);
          }
          setRows((current) =>
            current.map((row) =>
              row.id === id ? { ...row, transaction, missing: result === null } : row,
            ),
          );
          setBanner((current) => (current === "network" ? null : current));
        } catch {
          setBanner("network");
        }
      });

    poll();
    const pollTimer = setInterval(poll, STATUS_INTERVAL_MS);
    const clockTimer = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(pollTimer);
      clearInterval(clockTimer);
    };
  }, [pendingKey]);

  const record = useCallback((result: WebhookResult) => {
    logId.current += 1;
    const entry: LogEntry = {
      id: logId.current,
      time: new Date().toISOString().slice(11, 19),
      method: "POST",
      path: WEBHOOK_PATH,
      status: result.status,
      latencyMs: result.latencyMs,
    };
    setLog((current) => [entry, ...current].slice(0, MAX_LOG_ENTRIES));
  }, []);

  const track = useCallback((id: string) => {
    setRows((current) =>
      current.some((row) => row.id === id)
        ? current
        : [{ id, sentAt: Date.now(), transaction: null, missing: false }, ...current],
    );
    setSelectedId(id);
  }, []);

  const handleResult = useCallback(
    (result: WebhookResult, id: string) => {
      if (result.status === 202) {
        setBanner(null);
        setFieldErrors({});
        track(id);
      } else if (result.status === 422) {
        setFieldErrors(fieldErrorsFrom(result.body));
      } else {
        setBanner("save");
      }
    },
    [track],
  );

  const send = useCallback(
    async (payload: WebhookPayload): Promise<boolean> => {
      setSummary(null);
      try {
        const result = await sendWebhook(payload);
        record(result);
        handleResult(result, payload.transaction_id);
        return result.status === 202;
      } catch {
        setBanner("network");
        return false;
      }
    },
    [handleResult, record],
  );

  const sendDuplicates = useCallback(
    async (payload: WebhookPayload, count: number): Promise<boolean> => {
      setSummary(null);
      try {
        const results = await Promise.all(
          Array.from({ length: count }, () => sendWebhook(payload)),
        );
        results.forEach(record);
        const accepted = results.filter((result) => result.status === 202).length;
        const slowest = Math.max(...results.map((result) => result.latencyMs));
        handleResult(results.find((result) => result.status !== 202) ?? results[0], payload.transaction_id);
        if (accepted === 0) return false;

        const stored = await fetchTransaction(payload.transaction_id);
        setSummary(
          `${count} sent, ${accepted} accepted, ${stored?.length ?? 0} transaction, ` +
            `slowest ${Math.round(slowest)} ms`,
        );
        return true;
      } catch {
        setBanner("network");
        return false;
      }
    },
    [handleResult, record],
  );

  const toggleTheme = () => {
    const isDark =
      document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme &&
        matchMedia("(prefers-color-scheme: dark)").matches);
    setTheme(isDark ? "light" : "dark");
  };

  const selected = rows.find((row) => row.id === selectedId) ?? null;
  const reachable = health !== null && health !== "down";

  return (
    <main className="page">
      <header className="header">
        <h1>Webhook Console</h1>
        <div className="header-side">
          <span className="health" data-state={reachable ? "healthy" : health ? "down" : "checking"}>
            <span className="health-dot" />
            {reachable ? health.status : health ? "UNREACHABLE" : "CHECKING"}
          </span>
          {reachable && (
            <span className="mono muted">{health.current_time.slice(11, 19)} UTC</span>
          )}
          <button type="button" className="button" onClick={toggleTheme}>
            Theme
          </button>
        </div>
      </header>

      {banner && (
        <p className="banner" role="alert">
          {BANNER_TEXT[banner]}
        </p>
      )}

      <div className="workspace">
        <SendForm
          errors={fieldErrors}
          summary={summary}
          onSend={send}
          onSendDuplicates={sendDuplicates}
        />
        <div className="stack">
          <TransactionList
            rows={rows}
            now={now}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          {selected && <TransactionDetails row={selected} onResend={send} />}
        </div>
      </div>

      <RequestLog entries={log} />

      <footer className="footer">Use test data only.</footer>
      <div className="visually-hidden" aria-live="polite">
        {announcement}
      </div>
    </main>
  );
}
