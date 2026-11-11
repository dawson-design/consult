import { createServer } from "node:http";

// The checkout page asks this service how many days delivery to a postcode
// takes. The answer comes from the carrier's estimates API at `carrierUrl`.
export function createApp({ carrierUrl = process.env.CARRIER_URL } = {}) {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "GET" && url.pathname === "/delivery-estimate") {
        return await deliveryEstimate(url, res, carrierUrl);
      }
      send(res, 404, { error: "not found" });
    } catch (error) {
      console.error(error);
      send(res, 500, { error: "internal error" });
    }
  });
}

async function deliveryEstimate(url, res, carrierUrl) {
  const postcode = url.searchParams.get("postcode")?.trim();
  if (!postcode) return send(res, 400, { error: "postcode is required" });
  const estimate = await fetchEstimate(carrierUrl, postcode);
  send(res, 200, { postcode, days: estimate.days });
}

async function fetchEstimate(carrierUrl, postcode) {
  const response = await fetch(`${carrierUrl}/estimates?postcode=${encodeURIComponent(postcode)}`);
  return response.json();
}

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}
