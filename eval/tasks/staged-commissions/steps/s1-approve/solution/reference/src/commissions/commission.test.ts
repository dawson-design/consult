// Business rules of the commission lifecycle: order of steps, restocking fee, deposit, refund.
import assert from "node:assert/strict";
import test from "node:test";
import { balanceDuePence, type Commission, deliver, depositPence, dispatch, place, startBench, withdraw } from "./commission.ts";

const bench = () => place("c1", "p1", [{ design: "oak-bench", quantity: 1, unitPence: 45000 }]);

function moved(result: { ok: true; value: Commission } | { ok: false }): Commission {
  assert.ok(result.ok);
  return result.value;
}

test("steps run only in order: start, dispatch, deliver", () => {
  assert.equal(dispatch(bench(), "HJ-1").ok, false);
  const started = moved(startBench(bench()));
  const sent = moved(dispatch(started, "HJ-1"));
  assert.deepEqual([sent.status, "consignment" in sent && sent.consignment], ["dispatched", "HJ-1"]);
  assert.equal(moved(deliver(sent)).status, "delivered");
});

test("withdrawing before the bench is free and refunds the whole deposit", () => {
  const withdrawn = moved(withdraw(bench(), "changed my mind"));
  assert.ok(withdrawn.status === "withdrawn");
  assert.deepEqual([withdrawn.restockingFeePence, withdrawn.refundPence], [0, 13500]);
});

test("withdrawing on the bench keeps a 20% restocking fee out of the deposit", () => {
  const withdrawn = moved(withdraw(moved(startBench(bench())), null));
  assert.ok(withdrawn.status === "withdrawn");
  assert.deepEqual([withdrawn.restockingFeePence, withdrawn.refundPence], [9000, 4500]);
});

test("no withdrawal after dispatch", () => {
  const sent = moved(dispatch(moved(startBench(bench())), "HJ-1"));
  assert.equal(withdraw(sent, null).ok, false);
});

test("a 30% deposit, with the balance due until dispatch", () => {
  assert.deepEqual([depositPence(bench()), balanceDuePence(bench())], [13500, 31500]);
  const sent = moved(dispatch(moved(startBench(bench())), "HJ-1"));
  assert.equal(balanceDuePence(sent), 0);
});
