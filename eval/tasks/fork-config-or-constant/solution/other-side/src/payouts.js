// Seller payouts for the marketplace. Every amount is in integer cents.

// The platform fee kept from each payout, as a share of the order's gross
// amount. Set PLATFORM_FEE_RATE to change it without a code change.
const DEFAULT_PLATFORM_FEE_RATE = 0.029;

function platformFeeRate() {
  const configured = process.env.PLATFORM_FEE_RATE;
  if (configured === undefined || configured === "") return DEFAULT_PLATFORM_FEE_RATE;
  const rate = Number(configured);
  if (!Number.isFinite(rate) || rate < 0 || rate >= 1) {
    throw new RangeError(`PLATFORM_FEE_RATE must be a number in [0, 1), got ${configured}`);
  }
  return rate;
}

export function orderGrossCents(order) {
  return order.items.reduce((sum, item) => sum + item.priceCents * item.quantity, 0);
}

export function payoutFor(order) {
  const grossCents = orderGrossCents(order);
  const feeCents = Math.round(grossCents * platformFeeRate());
  return { orderId: order.id, sellerId: order.sellerId, grossCents, feeCents, netCents: grossCents - feeCents };
}

export function payoutsBySeller(orders) {
  const totals = new Map();
  for (const order of orders) {
    const payout = payoutFor(order);
    totals.set(payout.sellerId, (totals.get(payout.sellerId) ?? 0) + payout.netCents);
  }
  return Object.fromEntries(totals);
}
