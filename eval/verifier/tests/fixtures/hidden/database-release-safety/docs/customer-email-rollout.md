# Customer email rollout

Apply 001, 002, and 003 in order. Run 002 outside a transaction.

Validate that `customers_email_idx` is valid before running 003.

On failure, run the rollback files in `migrations/rollback/` in reverse order.
