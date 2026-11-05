// In-memory storage for orders.

export interface Order {
  id: string;
  items: { sku: string; quantity: number; unitPence: number }[];
  totalPence: number;
  paidPence: number;
}

export class OrderRepository {
  private readonly orders = new Map<string, Order>();
  private nextId = 1;

  create(order: Omit<Order, "id">): Order {
    const saved = { ...order, id: `o_${this.nextId++}` };
    this.orders.set(saved.id, saved);
    return saved;
  }

  findById(id: string): Order | undefined {
    return this.orders.get(id);
  }

  save(order: Order): void {
    this.orders.set(order.id, order);
  }
}
