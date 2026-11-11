// Payment methods saved on customer accounts. Amounts are integer cents.
//
// A saved method, as the payment gateway sends it:
//   { id, method: "card", cardBrand, cardLast4, expMonth, expYear }

export function describePayment(payment) {
  return `${payment.cardBrand} ending ${payment.cardLast4}`;
}

/** A card can be charged through the last day of its expiry month. `today` is "YYYY-MM-DD". */
export function isChargeable(payment, today) {
  const [year, month] = today.split("-").map(Number);
  return payment.expYear > year || (payment.expYear === year && payment.expMonth >= month);
}

/** The gateway's fee for a charge: 2.9% plus 30 cents, rounded to the nearest cent. */
export function processingFeeCents(payment, amountCents) {
  return Math.round(amountCents * 0.029) + 30;
}

export function receiptLine(payment, amountCents) {
  const dollars = (amountCents / 100).toFixed(2);
  return `Charged $${dollars} to ${describePayment(payment)}`;
}
