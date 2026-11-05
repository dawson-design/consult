// HTTP handlers for orders: validates request bodies and calls OrderService.
import { ValidationError } from "../errors.ts";
import type { OrderService } from "../services/orderService.ts";

export class OrderController {
  private readonly service: OrderService;

  constructor(service: OrderService) {
    this.service = service;
  }

  create(body: unknown) {
    const items = (body as { items?: unknown })?.items;
    if (!Array.isArray(items)) throw new ValidationError("items must be an array");
    return { status: 201, body: this.service.placeOrder(items) };
  }

  show(id: string) {
    return { status: 200, body: this.service.getOrder(id) };
  }

  pay(id: string, body: unknown) {
    const amount = (body as { amountPence?: unknown })?.amountPence;
    if (!Number.isInteger(amount) || (amount as number) <= 0) throw new ValidationError("amountPence must be a positive integer");
    return { status: 200, body: this.service.pay(id, amount as number) };
  }
}
