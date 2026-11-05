// Result values for expected failures; every module returns these instead of throwing.

/** Success with a value, or an expected failure with an error. */
export type Result<T, E> = { readonly ok: true; readonly value: T } | { readonly ok: false; readonly error: E };

/** Wrap a success. */
export const ok = <T>(value: T): Result<T, never> => ({ ok: true, value });

/** Wrap an expected failure. */
export const err = <E>(error: E): Result<never, E> => ({ ok: false, error });
