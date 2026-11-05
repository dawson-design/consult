// Business rules for gift cards: issuing, and paying for an order from a card.
import { ConflictError, NotFoundError, ValidationError } from "../errors.ts";
import type { GiftCard, GiftCardRepository } from "../repositories/giftCardRepository.ts";
import type { OrderService } from "./orderService.ts";

export class GiftCardService {
  private readonly cards: GiftCardRepository;
  private readonly orders: OrderService;

  constructor(cards: GiftCardRepository, orders: OrderService) {
    this.cards = cards;
    this.orders = orders;
  }

  issue(balancePence: number): GiftCard {
    if (!Number.isInteger(balancePence) || balancePence <= 0) throw new ValidationError("balancePence must be a positive integer");
    return this.cards.create(balancePence);
  }

  payOrder(orderId: string, code: string, amountPence: number): GiftCard {
    const card = this.cards.findByCode(code);
    if (!card) throw new NotFoundError(`gift card ${code} not found`);
    if (amountPence > card.balancePence) throw new ConflictError("the gift card balance is too low");
    this.orders.pay(orderId, amountPence);
    card.balancePence -= amountPence;
    this.cards.save(card);
    return card;
  }
}
