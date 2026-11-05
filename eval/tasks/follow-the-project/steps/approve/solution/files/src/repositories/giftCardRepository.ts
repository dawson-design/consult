// In-memory storage for gift cards, keyed by code.
import { randomBytes } from "node:crypto";

export interface GiftCard {
  code: string;
  balancePence: number;
}

export class GiftCardRepository {
  private readonly cards = new Map<string, GiftCard>();

  create(balancePence: number): GiftCard {
    const card = { code: randomBytes(8).toString("hex"), balancePence };
    this.cards.set(card.code, card);
    return card;
  }

  findByCode(code: string): GiftCard | undefined {
    return this.cards.get(code);
  }

  save(card: GiftCard): void {
    this.cards.set(card.code, card);
  }
}
