// Business rules for orders: pricing from the price list and taking payment.
import { ConflictError, NotFoundError, ValidationError } from "../errors.ts";
import type { Order, OrderRepository } from "../repositories/orderRepository.ts";

const PRICES: Record<string, number> = { "tea-1kg": 1200, "mug": 800, "biscuits": 350 };

export class OrderService {
  private readonly orders: OrderRepository;

  constructor(orders: OrderRepository) {
    this.orders = orders;
  }

  placeOrder(items: { sku: string; quantity: number }[]): Order {
    if (items.length === 0) throw new ValidationError("an order needs at least one item");
    const priced = items.map(({ sku, quantity }) => {
      const unitPence = PRICES[sku];
      if (unitPence === undefined) throw new ValidationError(`unknown sku ${sku}`);
      return { sku, quantity, unitPence };
    });
    const totalPence = priced.reduce((sum, i) => sum + i.unitPence * i.quantity, 0);
    return this.orders.create({ items: priced, totalPence, paidPence: 0 });
  }

  getOrder(id: string): Order {
    const order = this.orders.findById(id);
    if (!order) throw new NotFoundError(`order ${id} not found`);
    return order;
  }

  pay(id: string, amountPence: number): Order {
    const order = this.getOrder(id);
    if (order.paidPence + amountPence > order.totalPence) throw new ConflictError("payment exceeds the amount due");
    order.paidPence += amountPence;
    this.orders.save(order);
    return order;
  }
}
