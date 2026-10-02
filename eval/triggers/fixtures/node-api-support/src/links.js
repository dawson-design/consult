import url from "node:url";

// Host and path of a pasted link, for the link preview card.
export function describeLink(link) {
  const parsed = url.parse(link);
  return { host: parsed.hostname, path: parsed.pathname };
}
