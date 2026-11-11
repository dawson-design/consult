// Business rules of the commission lifecycle: order of steps, restocking fee, deposit, refund, discount.
import assert from "node:assert/strict";
import test from "node:test";
import {
  balanceDuePence,
  type Commission,
  deliver,
  depositPence,
  discountPence,
  dispatch,
  place,
  startBench,
  withdraw,
} from "./commission.ts";

const oak = [{ design: "oak-bench", quantity: 1, unitPence: 45000 }];
const bench = () => place("c1", "p1", oak, false);

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

test("a returning patron's commission is 10% off, and the deposit, fee, and refund work from that total", () => {
  const returning = place("c2", "p1", oak, true);
  assert.deepEqual([returning.totalPence, discountPence(returning), depositPence(returning)], [40500, 4500, 12150]);
  assert.equal(discountPence(bench()), 0);
  const withdrawn = moved(withdraw(moved(startBench(returning)), null));
  assert.ok(withdrawn.status === "withdrawn");
  assert.deepEqual([withdrawn.restockingFeePence, withdrawn.refundPence], [8100, 4050]);
});
