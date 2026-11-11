// The shop front's view of a commission: money as decimal strings in the
// requested currency, and only the fields the commission's state has.
import { convert, type Currency } from "../rates/rates.ts";
import { balanceDuePence, type Commission, depositPence, discountPence } from "./commission.ts";

function decimal(minor: number): string {
  return (minor / 100).toFixed(2);
}

/** The JSON body for a commission, converted at `rate` (1 for GBP). */
export function present(commission: Commission, currency: Currency, rate: number) {
  const money = (pence: number) => decimal(convert(pence, rate));
  const shown = {
    id: commission.id,
    status: commission.status,
    pieces: commission.pieces.map(({ design, quantity }) => ({ design, quantity })),
    currency,
    total: money(commission.totalPence),
    discount: money(discountPence(commission)),
    deposit: money(depositPence(commission)),
    balanceDue: money(balanceDuePence(commission)),
  };
  switch (commission.status) {
    case "dispatched":
    case "delivered":
      return { ...shown, consignment: commission.consignment };
    case "withdrawn":
      return {
        ...shown,
        reason: commission.reason,
        restockingFee: money(commission.restockingFeePence),
        refund: money(commission.refundPence),
      };
    default:
      return shown;
  }
}
