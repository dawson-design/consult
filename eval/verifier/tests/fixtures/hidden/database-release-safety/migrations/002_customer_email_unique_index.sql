-- Must run outside a transaction block.
SET lock_timeout = '2s';
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS customers_email_idx ON customers (email);
RESET lock_timeout;
