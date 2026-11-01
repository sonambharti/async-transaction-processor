CREATE TABLE IF NOT EXISTS transactions (
    transaction_id      TEXT PRIMARY KEY,
    source_account      TEXT NOT NULL,
    destination_account TEXT NOT NULL,
    amount              NUMERIC NOT NULL CHECK (amount > 0),
    currency            CHAR(3) NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PROCESSING'
                        CHECK (status IN ('PROCESSING', 'PROCESSED')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at        TIMESTAMPTZ,
    lease_token         UUID,
    lease_expires_at    TIMESTAMPTZ,
    attempts            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_transactions_pending
    ON transactions (lease_expires_at)
    WHERE status = 'PROCESSING';

-- Supabase can expose public tables through its Data API. The service connects
-- as the table owner, which bypasses row level security.
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
