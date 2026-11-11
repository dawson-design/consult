// Local stand-in for the mail relay client: same signature, same latency, and
// every message it would have sent is kept in `sentEmails`. Leave it as is;
// production swaps in the real client.
const RELAY_LATENCY_MS = 300;

export const sentEmails = [];

export async function sendEmail({ to, subject, text }) {
  await new Promise((resolve) => setTimeout(resolve, RELAY_LATENCY_MS));
  sentEmails.push({ to, subject, text });
}
