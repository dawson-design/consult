// Prices pieces against catalogue.json. The file is read once at startup by
// loadCatalogue; pricing itself is pure.
import { readFileSync } from "node:fs";
import { err, ok, type Result } from "../result.ts";
import type { Piece } from "./commission.ts";

/** Design code to unit price in pence. */
export type Catalogue = ReadonlyMap<string, number>;

/** A requested design the catalogue does not list. */
export type UnknownDesign = { readonly kind: "unknown_design"; readonly design: string };

/** Read the catalogue file; a missing or malformed file is a deploy bug, so it throws. */
export function loadCatalogue(path: string): Catalogue {
  const entries = JSON.parse(readFileSync(path, "utf8")) as { design: string; pricePence: number }[];
  return new Map(entries.map((e) => [e.design, e.pricePence]));
}

/** Attach unit prices, or name the first design the catalogue lacks. */
export function price(
  catalogue: Catalogue,
  requested: readonly { design: string; quantity: number }[],
): Result<Piece[], UnknownDesign> {
  const pieces: Piece[] = [];
  for (const { design, quantity } of requested) {
    const unitPence = catalogue.get(design);
    if (unitPence === undefined) return err({ kind: "unknown_design", design });
    pieces.push({ design, quantity, unitPence });
  }
  return ok(pieces);
}
