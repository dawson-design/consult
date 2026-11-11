// Payment methods saved on customer accounts. Amounts are integer cents.
//
// A saved method, as the payment gateway sends it, by its `method`:
//   card:          { id, method: "card", cardBrand, cardLast4, expMonth, expYear }
//   bank_transfer: { id, method: "bank_transfer", bankName, accountLast4 }

const METHODS = {
  card: {
    describe: (payment) => `${payment.cardBrand} ending ${payment.cardLast4}`,
    // A card can be charged through the last day of its expiry month.
    isChargeable(payment, today) {
      const [year, month] = today.split("-").map(Number);
      return payment.expYear > year || (payment.expYear === year && payment.expMonth >= month);
    },
    // 2.9% plus 30 cents.
    feeCents: (amountCents) => Math.round(amountCents * 0.029) + 30,
  },
  bank_transfer: {
    describe: (payment) => `${payment.bankName} account ending ${payment.accountLast4}`,
    // Bank accounts do not expire.
    isChargeable: () => true,
    // 0.8%, capped at $5.
    feeCents: (amountCents) => Math.min(Math.round(amountCents * 0.008), 500),
  },
};

function methodOf(payment) {
  const method = METHODS[payment.method];
  if (!method) throw new RangeError(`unknown payment method: ${payment.method}`);
  return method;
}

export function describePayment(payment) {
  return methodOf(payment).describe(payment);
}

/** `today` is "YYYY-MM-DD". */
export function isChargeable(payment, today) {
  return methodOf(payment).isChargeable(payment, today);
}

/** The gateway's fee for a charge, rounded to the nearest cent. */
export function processingFeeCents(payment, amountCents) {
  return methodOf(payment).feeCents(amountCents);
}

export function receiptLine(payment, amountCents) {
  const dollars = (amountCents / 100).toFixed(2);
  return `Charged $${dollars} to ${describePayment(payment)}`;
}
