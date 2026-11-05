// HTTP handlers for gift cards: validates request bodies and calls GiftCardService.
import { ValidationError } from "../errors.ts";
import type { GiftCardService } from "../services/giftCardService.ts";

export class GiftCardController {
  private readonly service: GiftCardService;

  constructor(service: GiftCardService) {
    this.service = service;
  }

  issue(body: unknown) {
    const balance = (body as { balancePence?: unknown })?.balancePence;
    if (typeof balance !== "number") throw new ValidationError("balancePence must be a number");
    return { status: 201, body: this.service.issue(balance) };
  }

  payOrder(orderId: string, body: unknown) {
    const { code, amountPence } = (body ?? {}) as { code?: unknown; amountPence?: unknown };
    if (typeof code !== "string") throw new ValidationError("code must be a string");
    if (!Number.isInteger(amountPence) || (amountPence as number) <= 0) throw new ValidationError("amountPence must be a positive integer");
    const card = this.service.payOrder(orderId, code, amountPence as number);
    return { status: 201, body: { code: card.code, balancePence: card.balancePence } };
  }
}
