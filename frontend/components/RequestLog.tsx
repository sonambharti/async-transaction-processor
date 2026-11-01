const LATENCY_LIMIT_MS = 500;

export type LogEntry = {
  id: number;
  time: string;
  method: string;
  path: string;
  status: number;
  latencyMs: number;
};

export function RequestLog({ entries }: { entries: LogEntry[] }) {
  return (
    <section className="panel" aria-label="Request log">
      <h2>Request log</h2>
      {entries.length === 0 ? (
        <p className="muted">Webhooks you send appear here with their response time.</p>
      ) : (
        <ul className="log mono">
          {entries.map((entry) => (
            <li key={entry.id}>
              <span className="log-time muted">{entry.time}</span>
              <span className="log-path">
                {entry.method} {entry.path}
              </span>
              <span className={entry.status >= 400 ? "is-error" : undefined}>{entry.status}</span>
              <span
                className={`log-latency${entry.latencyMs >= LATENCY_LIMIT_MS ? " is-error" : ""}`}
              >
                {Math.round(entry.latencyMs)} ms
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
