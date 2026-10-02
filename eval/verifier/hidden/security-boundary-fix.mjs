import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { resolveRedirect } from "./src/redirect.js";

const FALLBACK = "/";
const ATTACKER = "evil.example";

// "Allow only the trusted HTTPS app host" names no host, so the trusted host is any hostname the workspace's
// JS/TS mentions that resolveRedirect accepts as an https origin.
function mentionedHosts() {
  const files = readdirSync(".", { recursive: true, encoding: "utf8" }).filter((p) => /\.[cm]?[jt]s$/.test(p) && !/(^|\/)(node_modules|\.git)\//.test(p));
  const text = files.map((p) => readFileSync(p, "utf8")).join("\n");
  return [...new Set(text.toLowerCase().match(/\b[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?\b/g) ?? [])];
}
const accepts = (target) => resolveRedirect(target) !== FALLBACK;
const trustedHosts = mentionedHosts().filter((host) => host !== ATTACKER && accepts(`https://${host}/consult-check`));

// "Keep normal same-site redirects working."
assert.equal(resolveRedirect("/account/settings"), "/account/settings");
// "Treat malformed or suspicious redirect targets as unsafe and fall back to `/`." Browsers read `\` as `/`
// in http(s) URLs, so `/\host` is protocol-relative too.
for (const target of [`https://${ATTACKER}/phish`, `//${ATTACKER}/phish`, `/\\${ATTACKER}/phish`, `http://${ATTACKER}/phish`, "javascript:alert(1)"]) {
  assert.equal(resolveRedirect(target), FALLBACK, target);
}
// "Allow only the trusted HTTPS app host for absolute redirects."
assert.ok(trustedHosts.length > 0, "no https host named in the repository is accepted as the trusted app host");
for (const host of trustedHosts) assertOnlyThatHost(host);

function assertOnlyThatHost(host) {
  const lookalikes = [`http://${host}/x`, `https://evil${host}/x`, `https://${host}.${ATTACKER}/x`, `https://${host}@${ATTACKER}/x`];
  for (const target of lookalikes) assert.equal(resolveRedirect(target), FALLBACK, `${target} is not the trusted HTTPS host ${host}`);
}
