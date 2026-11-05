// Saves and loads commissions in SQLite. Rows are flat; fromRow rebuilds the
// state variant so the rest of the code never sees nullable columns.
import type { DatabaseSync } from "node:sqlite";
import type { Commission, Piece } from "./commission.ts";

type Row = {
  id: string;
  patron_id: string | null;
  pieces: string;
  total_pence: number;
  status: Commission["status"];
  consignment: string | null;
  reason: string | null;
  restocking_fee_pence: number | null;
  refund_pence: number | null;
};

/** The state variant a row holds. Rows come only from save, so their columns match their status. */
export function fromRow(row: Row): Commission {
  const placed = {
    id: row.id,
    patronId: row.patron_id,
    pieces: JSON.parse(row.pieces) as Piece[],
    totalPence: row.total_pence,
  };
  switch (row.status) {
    case "dispatched":
    case "delivered":
      return { ...placed, status: row.status, consignment: row.consignment ?? "" };
    case "withdrawn":
      return {
        ...placed,
        status: "withdrawn",
        reason: row.reason,
        restockingFeePence: row.restocking_fee_pence ?? 0,
        refundPence: row.refund_pence ?? 0,
      };
    default:
      return { ...placed, status: row.status };
  }
}

function toRow(c: Commission): Row {
  return {
    id: c.id,
    patron_id: c.patronId,
    pieces: JSON.stringify(c.pieces),
    total_pence: c.totalPence,
    status: c.status,
    consignment: "consignment" in c ? c.consignment : null,
    reason: c.status === "withdrawn" ? c.reason : null,
    restocking_fee_pence: c.status === "withdrawn" ? c.restockingFeePence : null,
    refund_pence: c.status === "withdrawn" ? c.refundPence : null,
  };
}

/** Insert or replace a commission. */
export function save(db: DatabaseSync, commission: Commission): void {
  const row = toRow(commission);
  db.prepare(
    `INSERT OR REPLACE INTO commissions
       (id, patron_id, pieces, total_pence, status, consignment, reason, restocking_fee_pence, refund_pence)
     VALUES (:id, :patron_id, :pieces, :total_pence, :status, :consignment, :reason, :restocking_fee_pence, :refund_pence)`,
  ).run(row);
}

/** The commission with this id, or undefined. */
export function find(db: DatabaseSync, id: string): Commission | undefined {
  const row = db.prepare("SELECT * FROM commissions WHERE id = ?").get(id) as Row | undefined;
  return row && fromRow(row);
}

/** A patron's commissions, oldest first. */
export function listFor(db: DatabaseSync, patronId: string): Commission[] {
  const rows = db.prepare("SELECT * FROM commissions WHERE patron_id = ? ORDER BY rowid").all(patronId) as Row[];
  return rows.map(fromRow);
}
