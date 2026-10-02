-- Nullable, no default: a catalog-only change.
BEGIN;
SET LOCAL lock_timeout = '2s';
ALTER TABLE customers ADD COLUMN email text;
COMMIT;
