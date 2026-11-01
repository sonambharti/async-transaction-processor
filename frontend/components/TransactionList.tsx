"use client";

import type { TrackedRow } from "@/lib/storage";

const EXPECTED_SECONDS = 30;

type TransactionListProps = {
  rows: TrackedRow[];
  now: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function truncateMiddle(id: string): string {
  return id.length > 20 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}

function finalSeconds(row: TrackedRow): number | null {
  const { transaction } = row;
  if (!transaction?.processed_at) return null;
  return Math.round(
    (Date.parse(transaction.processed_at) - Date.parse(transaction.created_at)) / 1000,
  );
}

function StatusBadge({ row }: { row: TrackedRow }) {
  if (row.missing) return <span className="badge badge-error">Not found</span>;
  return row.transaction?.status === "PROCESSED" ? (
    <span className="badge badge-processed">PROCESSED</span>
  ) : (
    <span className="badge badge-processing">PROCESSING</span>
  );
}

export function TransactionList({ rows, now, selectedId, onSelect }: TransactionListProps) {
  return (
    <section className="panel" aria-label="Transactions">
      <h2>Transactions</h2>
      {rows.length === 0 ? (
        <p className="muted">No transactions yet. Send a webhook to start tracking one.</p>
      ) : (
        <ul className="rows">
          {rows.map((row) => {
            const final = finalSeconds(row);
            const elapsed = Math.max(0, Math.floor((now - row.sentAt) / 1000));
            const inProgress = final === null && !row.missing;
            return (
              <li key={row.id}>
                <button
                  type="button"
                  className="row"
                  aria-pressed={row.id === selectedId}
                  onClick={() => onSelect(row.id)}
                >
                  <span className="mono" title={row.id}>
                    {truncateMiddle(row.id)}
                  </span>
                  <span className="row-amount mono muted">
                    {row.transaction
                      ? `${row.transaction.amount} ${row.transaction.currency}`
                      : ""}
                  </span>
                  <StatusBadge row={row} />
                  <span className="row-time mono">
                    {row.missing ? "" : `${final ?? elapsed}s`}
                  </span>
                </button>
                {inProgress && (
                  <div className="progress" aria-hidden="true">
                    <span
                      style={{
                        transform: `scaleX(${Math.min(elapsed / EXPECTED_SECONDS, 1)})`,
                      }}
                    />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
