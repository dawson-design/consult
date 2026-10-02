const FACTORS = { metres: 1, feet: 0.3048, kilometres: 1000, miles: 1609.344, grams: 1, ounces: 28.3495 };

export class UnitError extends Error {}

export function convert(value, from, to) {
  if (!(from in FACTORS) || !(to in FACTORS)) throw new UnitError(`unknown unit ${from} or ${to}`);
  return (value * FACTORS[from]) / FACTORS[to];
}
