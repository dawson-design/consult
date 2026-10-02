BEGIN;
SET LOCAL lock_timeout = '2s';
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_index WHERE indexrelid = 'customers_email_idx'::regclass AND indisvalid) THEN
    RAISE EXCEPTION 'customers_email_idx is invalid; drop it and rerun 002';
  END IF;
END
$$;
ALTER TABLE customers ADD CONSTRAINT customers_email_key UNIQUE USING INDEX customers_email_idx;
COMMIT;
