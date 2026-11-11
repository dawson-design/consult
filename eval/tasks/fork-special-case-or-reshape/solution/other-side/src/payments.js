// Payment methods saved on customer accounts. Amounts are integer cents.
//
// A saved method, as the payment gateway sends it:
//   { id, method: "card", cardBrand, cardLast4, expMonth, expYear }
//   { id, method: "bank_transfer", bankName, accountLast4 }

function isBankTransfer(payment) {
  return payment.method === "bank_transfer";
}

export function describePayment(payment) {
  if (isBankTransfer(payment)) return `${payment.bankName} account ending ${payment.accountLast4}`;
  return `${payment.cardBrand} ending ${payment.cardLast4}`;
}

/** A card can be charged through the last day of its expiry month; a bank account never expires. `today` is "YYYY-MM-DD". */
export function isChargeable(payment, today) {
  if (isBankTransfer(payment)) return true;
  const [year, month] = today.split("-").map(Number);
  return payment.expYear > year || (payment.expYear === year && payment.expMonth >= month);
}

/** The gateway's fee for a charge: 2.9% plus 30 cents for a card, 0.8% capped at 500 cents for a bank transfer. */
export function processingFeeCents(payment, amountCents) {
  if (isBankTransfer(payment)) return Math.min(Math.round(amountCents * 0.008), 500);
  return Math.round(amountCents * 0.029) + 30;
}

export function receiptLine(payment, amountCents) {
  const dollars = (amountCents / 100).toFixed(2);
  return `Charged $${dollars} to ${describePayment(payment)}`;
}
