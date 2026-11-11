// Seller payouts for the marketplace. Every amount is in integer cents.

// The platform fee kept from each payout, as a share of the order's gross amount.
const PLATFORM_FEE_RATE = 0.029;

export function orderGrossCents(order) {
  return order.items.reduce((sum, item) => sum + item.priceCents * item.quantity, 0);
}

export function payoutFor(order) {
  const grossCents = orderGrossCents(order);
  const feeCents = Math.round(grossCents * PLATFORM_FEE_RATE);
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
