// Builds the monthly revenue report shown on the export page.
export function buildReport(customers, orders) {
  const rows = customers.map((customer) => {
    const mine = orders.filter((order) => order.customerId === customer.id);
    const skus = mine.reduce((seen, order) => (seen.includes(order.sku) ? seen : [...seen, order.sku]), []);
    const totalCents = mine.reduce((sum, order) => sum + order.totalCents, 0);
    return { customer: customer.name, orders: mine.length, totalCents, distinctSkus: skus.length };
  });
  return rows.sort((a, b) => b.totalCents - a.totalCents || a.customer.localeCompare(b.customer));
}
