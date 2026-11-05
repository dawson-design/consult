// Gift cards in the house style, ignoring the project's layers, classes, and errors.
export type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };
export type GiftCard = { readonly code: string; readonly balancePence: number };

export function spend(card: GiftCard, amountPence: number): Result<GiftCard, "insufficient"> {
  if (amountPence > card.balancePence) return { ok: false, error: "insufficient" };
  return { ok: true, value: { ...card, balancePence: card.balancePence - amountPence } };
}
