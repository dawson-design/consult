// The commission lifecycle as data and pure functions: placing, bench time,
// dispatch, delivery, withdrawal with its restocking fee and refund, and the
// returning patron's discount.
// store.ts persists these values; routes.ts maps them to HTTP.
import { err, ok, type Result } from "../result.ts";

/** One catalogue design in a commission. */
export type Piece = { readonly design: string; readonly quantity: number; readonly unitPence: number };

type Placed = {
  readonly id: string;
  readonly patronId: string | null;
  readonly pieces: readonly Piece[];
  readonly totalPence: number;
};

/** A commission in exactly one state; each state carries only its own facts. */
export type Commission =
  | (Placed & { readonly status: "placed" })
  | (Placed & { readonly status: "on_bench" })
  | (Placed & { readonly status: "dispatched"; readonly consignment: string })
  | (Placed & { readonly status: "delivered"; readonly consignment: string })
  | (Placed & {
      readonly status: "withdrawn";
      readonly reason: string | null;
      readonly restockingFeePence: number;
      readonly refundPence: number;
    });

export type Status = Commission["status"];

/** A move the commission's current status does not allow. */
export type WrongStatus = { readonly kind: "wrong_status"; readonly status: Status };

const RESTOCKING_RATE = 0.2;
const DEPOSIT_RATE = 0.3;
const RETURNING_DISCOUNT_RATE = 0.1;

function cataloguePence(pieces: readonly Piece[]): number {
  return pieces.reduce((sum, p) => sum + p.unitPence * p.quantity, 0);
}

/** A new commission for priced pieces; a returning patron's total is 10% off, fixed when placed. */
export function place(id: string, patronId: string | null, pieces: readonly Piece[], returning: boolean): Commission {
  const listed = cataloguePence(pieces);
  const totalPence = listed - (returning ? Math.round(listed * RETURNING_DISCOUNT_RATE) : 0);
  return { id, patronId, pieces, totalPence, status: "placed" };
}

/** How far the total sits below the catalogue price of the pieces. */
export function discountPence(commission: Commission): number {
  return cataloguePence(commission.pieces) - commission.totalPence;
}

/** The deposit taken when the commission is placed, rounded to the penny. */
export function depositPence(commission: Commission): number {
  return Math.round(commission.totalPence * DEPOSIT_RATE);
}

/** What the patron still owes: the balance until dispatch takes it, nothing after. */
export function balanceDuePence(commission: Commission): number {
  const owesBalance = commission.status === "placed" || commission.status === "on_bench";
  return owesBalance ? commission.totalPence - depositPence(commission) : 0;
}

/** Building starts. */
export function startBench(commission: Commission): Result<Commission, WrongStatus> {
  if (commission.status !== "placed") return err({ kind: "wrong_status", status: commission.status });
  return ok({ ...commission, status: "on_bench" });
}

/** The carrier takes it, under their consignment number. */
export function dispatch(commission: Commission, consignment: string): Result<Commission, WrongStatus> {
  if (commission.status !== "on_bench") return err({ kind: "wrong_status", status: commission.status });
  return ok({ ...commission, status: "dispatched", consignment });
}

/** The carrier confirms delivery. */
export function deliver(commission: Commission): Result<Commission, WrongStatus> {
  if (commission.status !== "dispatched") return err({ kind: "wrong_status", status: commission.status });
  return ok({ ...commission, status: "delivered", consignment: commission.consignment });
}

/** The patron calls it off before dispatch; bench time costs the restocking fee, kept from the deposit. */
export function withdraw(commission: Commission, reason: string | null): Result<Commission, WrongStatus> {
  const beforeDispatch = commission.status === "placed" || commission.status === "on_bench";
  if (!beforeDispatch) return err({ kind: "wrong_status", status: commission.status });
  const fee = commission.status === "on_bench" ? Math.round(commission.totalPence * RESTOCKING_RATE) : 0;
  const refundPence = depositPence(commission) - fee;
  return ok({ ...commission, status: "withdrawn", reason, restockingFeePence: fee, refundPence });
}
