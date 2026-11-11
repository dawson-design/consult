// Seller payouts for the marketplace. Every amount is in integer cents.

export function orderGrossCents(order) {
  return order.items.reduce((sum, item) => sum + item.priceCents * item.quantity, 0);
}

export function payoutFor(order) {
  const grossCents = orderGrossCents(order);
  return { orderId: order.id, sellerId: order.sellerId, grossCents, netCents: grossCents };
}

export function payoutsBySeller(orders) {
  const totals = new Map();
  for (const order of orders) {
    const payout = payoutFor(order);
    totals.set(payout.sellerId, (totals.get(payout.sellerId) ?? 0) + payout.netCents);
  }
  return Object.fromEntries(totals);
}
