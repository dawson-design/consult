// Exchange rates from the FX provider at RATES_URL, and conversion of pence
// into another currency's minor units. fetchRates owns the timeout, retry, and
// failure behavior together; convert is pure.
import { z } from "zod";
import { err, ok, type Result } from "../result.ts";

export const CURRENCIES = ["GBP", "EUR", "USD"] as const;
export type Currency = (typeof CURRENCIES)[number];

/** GBP to each other currency. */
export type Rates = Readonly<Record<string, number>>;

/** The provider did not answer usefully: down, slow, refusing, or sending garbage. */
export type RatesUnavailable = { readonly kind: "rates_unavailable"; readonly detail: string };

const RatesBody = z.object({ base: z.literal("GBP"), rates: z.record(z.string(), z.number().positive()) });

const ATTEMPTS = 3;
const TIMEOUT_MS = 2000;
const BACKOFF_MS = 150;
const BACKOFF_CAP_MS = 1000;

type Failure = RatesUnavailable & { readonly transient: boolean };
type Attempt = Result<Rates, Failure>;

function isTransientStatus(status: number): boolean {
  return status === 429 || status >= 500;
}

function failure(detail: string, transient: boolean): Attempt {
  return err({ kind: "rates_unavailable", detail, transient });
}

async function attempt(url: string): Promise<Attempt> {
  let response: Response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (error) {
    return failure(String(error), true);
  }
  if (!response.ok) return failure(`status ${response.status}`, isTransientStatus(response.status));
  const body = RatesBody.safeParse(await response.json().catch(() => null));
  return body.success ? ok(body.data.rates) : failure("malformed body", false);
}

function backoff(attemptNumber: number): Promise<void> {
  const delay = Math.min(BACKOFF_CAP_MS, BACKOFF_MS * 2 ** attemptNumber) * (0.5 + Math.random() / 2);
  return new Promise((resolve) => setTimeout(resolve, delay));
}

/** GBP rates, retrying only timeouts, network errors, 429, and 5xx, up to three attempts with jittered backoff. */
export async function fetchRates(baseUrl: string): Promise<Result<Rates, RatesUnavailable>> {
  const url = new URL("/rates?base=GBP", baseUrl).toString();
  let last = failure("not tried", true);
  for (let n = 0; n < ATTEMPTS; n += 1) {
    if (n > 0) await backoff(n);
    last = await attempt(url);
    const settled = last.ok || !last.error.transient;
    if (settled) break;
  }
  return last.ok ? last : err({ kind: "rates_unavailable", detail: last.error.detail });
}

/** Pence in another currency's minor units, rounded to the nearest unit. */
export function convert(pence: number, rate: number): number {
  return Math.round(pence * rate);
}
