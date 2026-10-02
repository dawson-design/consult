import { readFileSync } from "node:fs";

const html = readFileSync("public/index.html", "utf8");
const markup = html.replace(/<!--[\s\S]*?-->/g, "");
const ATTR = /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
const parseAttrs = (text) => Object.fromEntries(Array.from(text.matchAll(ATTR), (m) => [m[1].toLowerCase(), (m[2] ?? m[3] ?? m[4] ?? "").toLowerCase()]));
const startTags = Array.from(markup.matchAll(/<([a-z][a-z0-9-]*)\b([^>]*)>/gi), (m) => ({ tag: m[1].toLowerCase(), attrs: parseAttrs(m[2]) }));
const textOf = (fragment) => (fragment ?? "").replace(/<[^>]+>/g, "").trim();

const emailInput = startTags.find(({ tag, attrs }) => tag === "input" && attrs.id === "email");
const explicitLabel = html.match(/<label\b[^>]*\bfor=["']?email(?=["'\s>])[^>]*>([\s\S]*?)<\/label>/i)?.[1];
// "Use native HTML semantics where they fit." A <label> wrapping the input labels it as well as for= does.
const wrappingLabel = html.match(/<label\b[^>]*>((?:(?!<\/label>)[\s\S])*<input\b[^>]*\bid=["']?email(?=["'\s/>])(?:(?!<\/label>)[\s\S])*)<\/label>/i)?.[1];
const labelText = textOf(explicitLabel) || textOf(wrappingLabel);

// "Use native HTML semantics where they fit." <input type="submit"> is as native as <button>.
const isSubmitControl = ({ tag, attrs }) =>
  (tag === "button" && !["button", "reset"].includes(attrs.type ?? "submit")) || (tag === "input" && attrs.type === "submit");

// "Make the ... success feedback work for ... assistive technology." role="status" and <output> are polite
// live regions by default; an explicit aria-live overrides either.
const isPoliteRegion = ({ tag, attrs }) => (attrs["aria-live"] ? attrs["aria-live"] === "polite" : attrs.role === "status" || tag === "output");

const VOID_TAGS = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);
const closeElement = (open, tag) => {
  const index = open.findLastIndex((element) => element.tag === tag);
  if (index >= 0) open.length = index;
};

// The page writes its success text into #status: that element and its ancestors, root first.
function statusElementPath() {
  const open = [];
  for (const [, closing, name, rest] of markup.matchAll(/<(\/?)([a-z][a-z0-9-]*)\b([^>]*)>/gi)) {
    const element = { tag: name.toLowerCase(), attrs: parseAttrs(rest) };
    if (closing) closeElement(open, element.tag);
    else if (element.attrs.id === "status") return [...open, element];
    else if (!VOID_TAGS.has(element.tag) && !rest.endsWith("/")) open.push(element);
  }
  return undefined;
}
// A page that renamed #status leaves no element to tie the success text to, so any polite region counts.
const statusPath = statusElementPath();
const successIsAnnounced = statusPath ? statusPath.some(isPoliteRegion) : startTags.some(isPoliteRegion);

const checks = [
  ["email input has an explicit text label", labelText.length > 0],
  ["email input is not placeholder-only", emailInput?.attrs.placeholder === undefined || labelText.length > 0],
  ["submit control is a native submit button", startTags.some(isSubmitControl)],
  ["status region is announced politely", successIsAnnounced],
  ["does not use a clickable div submit", !/<div\b[^>]*(onclick|role=["']button["'])[^>]*>[\s\S]*subscribe/i.test(html)],
];
const failed = checks.filter(([, ok]) => !ok).map(([label]) => label);
if (failed.length > 0) {
  console.error("subscription form: failed checks: " + failed.join(", "));
  process.exit(1);
}
