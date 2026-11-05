// HTTP routes for commissions: the shop front's place, show, list, and
// withdrawal (bearer token, own commissions only), and the workshop tool's
// start, dispatch, and deliver. Bodies are parsed here, once, with Zod.
import { randomUUID } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import { z } from "zod";
import { problem, reply, type Reply, type Request, type Route } from "../http/server.ts";
import { bearerPatron } from "../patrons/routes.ts";
import { CURRENCIES, fetchRates } from "../rates/rates.ts";
import type { Result } from "../result.ts";
import { type Catalogue, price } from "./catalogue.ts";
import { type Commission, deliver, dispatch, place, startBench, type WrongStatus, withdraw } from "./commission.ts";
import { present } from "./present.ts";
import { find, listFor, save } from "./store.ts";

const PlaceBody = z.object({
  pieces: z.array(z.object({ design: z.string().min(1), quantity: z.number().int().positive().max(100) })).min(1),
});
const DispatchBody = z.object({ consignment: z.string().trim().min(1).max(100) });
const WithdrawalBody = z.object({ reason: z.string().trim().max(500).optional() }).optional();
const CurrencyQuery = z.enum(CURRENCIES).default("GBP");

export type Deps = { readonly db: DatabaseSync; readonly catalogue: Catalogue; readonly ratesUrl: string };

const unauthenticated = () => problem(401, "unauthenticated", "Log in to see your commissions.");
const notFound = () => problem(404, "not_found", "No such commission.");
const wrongStatus = (e: WrongStatus) => problem(409, "wrong_status", `Not allowed while the commission is ${e.status}.`);

/** The caller's own commission, or the reply that refuses it. */
function ownCommission(deps: Deps, request: Request): Result<Commission, Reply> {
  const patronId = bearerPatron(deps.db, request.headers);
  if (!patronId) return { ok: false, error: unauthenticated() };
  const commission = find(deps.db, request.params.id);
  if (commission?.patronId !== patronId) return { ok: false, error: notFound() };
  return { ok: true, value: commission };
}

function placeCommission(deps: Deps, request: Request): Reply {
  const patronId = bearerPatron(deps.db, request.headers);
  if (!patronId) return unauthenticated();
  const body = PlaceBody.safeParse(request.body);
  if (!body.success) return problem(400, "invalid_request", "Pieces need a design and a whole, positive quantity.");
  const pieces = price(deps.catalogue, body.data.pieces);
  if (!pieces.ok) return problem(422, "unknown_design", `The catalogue has no design "${pieces.error.design}".`);
  const commission = place(randomUUID(), patronId, pieces.value);
  save(deps.db, commission);
  return reply(201, present(commission, "GBP", 1));
}

async function showCommission(deps: Deps, request: Request): Promise<Reply> {
  const own = ownCommission(deps, request);
  if (!own.ok) return own.error;
  const currency = CurrencyQuery.safeParse(request.query.get("currency") ?? undefined);
  if (!currency.success) return problem(400, "unsupported_currency", `Currency must be one of ${CURRENCIES.join(", ")}.`);
  if (currency.data === "GBP") return reply(200, present(own.value, "GBP", 1));
  const rates = await fetchRates(deps.ratesUrl);
  const rate = rates.ok ? rates.value[currency.data] : undefined;
  if (rate === undefined) return problem(502, "rates_unavailable", "Prices in that currency are unavailable right now.");
  return reply(200, present(own.value, currency.data, rate));
}

function listCommissions(deps: Deps, request: Request): Reply {
  const patronId = bearerPatron(deps.db, request.headers);
  if (!patronId) return unauthenticated();
  return reply(200, { commissions: listFor(deps.db, patronId).map((c) => present(c, "GBP", 1)) });
}

function withdrawCommission(deps: Deps, request: Request): Reply {
  const own = ownCommission(deps, request);
  if (!own.ok) return own.error;
  const body = WithdrawalBody.safeParse(request.body);
  if (!body.success) return problem(400, "invalid_request", "A reason, when given, is text of up to 500 characters.");
  return saved(deps, withdraw(own.value, body.data?.reason ?? null));
}

function saved(deps: Deps, moved: Result<Commission, WrongStatus>): Reply {
  if (!moved.ok) return wrongStatus(moved.error);
  save(deps.db, moved.value);
  return reply(200, present(moved.value, "GBP", 1));
}

/** A workshop step: load by id, apply the transition, save. */
function workshopStep(deps: Deps, move: (c: Commission, request: Request) => Result<Commission, WrongStatus> | Reply) {
  return (request: Request): Reply => {
    const commission = find(deps.db, request.params.id);
    if (!commission) return notFound();
    const moved = move(commission, request);
    return "status" in moved ? moved : saved(deps, moved);
  };
}

function dispatchWith(commission: Commission, request: Request): Result<Commission, WrongStatus> | Reply {
  const body = DispatchBody.safeParse(request.body);
  if (!body.success) return problem(400, "invalid_request", "A consignment number is required.");
  return dispatch(commission, body.data.consignment);
}

/** Every commission route. */
export function commissionRoutes(deps: Deps): Route[] {
  return [
    { method: "POST", path: "/commissions", handle: (r) => placeCommission(deps, r) },
    { method: "GET", path: "/commissions", handle: (r) => listCommissions(deps, r) },
    { method: "GET", path: "/commissions/:id", handle: (r) => showCommission(deps, r) },
    { method: "POST", path: "/commissions/:id/withdrawal", handle: (r) => withdrawCommission(deps, r) },
    { method: "POST", path: "/commissions/:id/start", handle: workshopStep(deps, startBench) },
    { method: "POST", path: "/commissions/:id/dispatch", handle: workshopStep(deps, dispatchWith) },
    { method: "POST", path: "/commissions/:id/deliver", handle: workshopStep(deps, deliver) },
  ];
}
