// Rule probe: prints {"api.2", "api.3", "domain-modeling.11": 0|1} as its last line.
import { createServer } from "./src/server.js";

const items = [{ sku: "sku-mug", quantity: 1 }, { sku: "sku-tee", quantity: 1 }];
const json = { "content-type": "application/json" };

function hasMoney(value, currency, amounts) {
  if (!value || typeof value !== "object") return false;
  const entries = Object.entries(value);
  const currencyMatch = entries.some(([k, v]) => /currency/i.test(k) && v === currency);
  const amountMatch = entries.some(([k, v]) => /amount|minor|cents|value|total/i.test(k) && amounts.includes(v));
  return (currencyMatch && amountMatch) || Object.values(value).some((v) => hasMoney(v, currency, amounts));
}

const post = (base, body) => fetch(`${base}/orders`, { method: "POST", headers: json, body: typeof body === "string" ? body : JSON.stringify(body) });

async function readBack(base, body) {
  const res = await post(base, body);
  if (res.status !== 201) return null;
  return (await fetch(`${base}/orders/${(await res.json()).id}`)).json();
}

const readCad = async (base) =>
  (await readBack(base, { customerId: "c_ca", items, currency: "CAD" })) ?? (await readBack(base, { customerId: "c_ca", items }));

// api.2: the shipped fields keep name and type for USD orders, and CAD orders say their currency.
async function compatible(base) {
  const usd = await readBack(base, { customerId: "c_us", items });
  const shipped = usd && usd.total === 37 && typeof usd.items?.[0]?.unitPrice === "number" && typeof usd.status === "string";
  const cad = await readCad(base);
  return Boolean(shipped && cad && hasMoney(cad, "CAD", [4900, 49, "49.00", "49"]));
}

// domain-modeling.11 (references/money.md): the CAD amount sits beside its currency as
// integer minor units or a decimal string, never a float.
async function preciseMoney(base) {
  const cad = await readCad(base);
  return Boolean(cad && hasMoney(cad, "CAD", [4900, "49.00", "49"]));
}

// api.3: caller mistakes on the new surface get a 4xx (or are ignored), never a 5xx.
const is4xx = (status) => status >= 400 && status < 500;

async function callerErrors(base) {
  const badCurrency = await post(base, { customerId: "c_us", items, currency: "XYZ" });
  const text = await badCurrency.text();
  const currencyOk = is4xx(badCurrency.status) || (badCurrency.status === 201 && !text.includes("XYZ"));
  const wrongType = await post(base, { customerId: "c_us", items, currency: 5 });
  const malformed = await post(base, "{not json");
  const empty = await post(base, { customerId: "c_ca", items: [] });
  return currencyOk && wrongType.status < 500 && is4xx(malformed.status) && is4xx(empty.status);
}

const server = createServer().listen(0);
await new Promise((resolve) => server.once("listening", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const result = { "api.2": 0, "api.3": 0, "domain-modeling.11": 0 };
try {
  result["api.2"] = (await compatible(base)) ? 1 : 0;
  result["domain-modeling.11"] = (await preciseMoney(base)) ? 1 : 0;
  result["api.3"] = (await callerErrors(base)) ? 1 : 0;
} catch (error) {
  console.error(error);
} finally {
  server.close();
  console.log(JSON.stringify(result));
}
