# AI Usage Governance — Claude Code

A developer uses Claude Code the way they already do. Edge sees that direct use. You turn interception on, and the next prompt comes through Gravitee.

The pass takes about 15 minutes. Nothing here is a slide.

```mermaid
flowchart LR
  claude[Claude Code] --> direct[Anthropic, until Edge is on]
  claude --> gateway[Gravitee, once Edge is on]
  gateway --> gemma[Local gemma4:12b]
```

The daemon is installed once on this Mac from Gamma, **Edge Management**, **Daemon deployment**. Leave `ANTHROPIC_BASE_URL` unset. The daemon is macOS only. This demo does not show Windows, Linux, Microsoft Entra, browser traffic, or Microsoft Copilot.

## Power the daemon

Start this playground first, so the reactor on port 18093 is up. Then, from the catalog folder:

```bash
playgrounds/ai-usage-governance/scripts/edge up
```

The daemon runs, Shadow AI watches `api.anthropic.com`, and interception stays off: **DNS domains** is `unused.invalid`, a name nothing calls. `scripts/edge status` reports the daemon, the interception, and the reactor.

Starting or stopping the playground does not do this. The daemon starts at boot on its own.

## 1. Use Claude Code without a care

1. Start Claude Code and sign in with `/login` if it is not already signed in.
2. Send: `The checkout client gives up when the payment API times out. Can you add a retry with backoff?`

Claude Code talks to Anthropic. Gravitee is not on that path.

## 2. Show the shadow AI usage

1. In Gamma, open **Edge Management**.
2. Wait until the device reports a direct connection to `api.anthropic.com`. That can take about two minutes.
3. Show that row. It is the developer using Claude on their own. The row does not contain the prompt.

## 3. Turn Edge on

1. On the same page, under **DNS domains (interception mode)**, replace `unused.invalid` with `api.anthropic.com`.
2. Save. The routes are already there: `/v1/messages` goes to `/interception/claude`, and every other Anthropic call goes to `/interception/passthrough`. The daemon polls about every 15 seconds and applies the change.
3. Send a follow-up: `Also log each retry, including how long the payment API took.`

That prompt comes through Gravitee. On [Governed models](http://localhost:8086/environments/default/aim/llm-proxy/a1c0de00-0000-4000-8000-000000000002), the flow **Govern messages** has run: prompt guard rails, PII filtering, routing to local `gemma4:12b`, and the token limit. The answer comes from Gemma. If Gemma fails, failover retries the same route on local `qwen3:1.7b`. The log names the outcome. Headers are not stored. The payload is stored. The first answer can take a few seconds while Ollama loads the model.

## Put the demo back

1. From the catalog folder, run `playgrounds/ai-usage-governance/scripts/edge down`. The daemon stops, the DNS override for `api.anthropic.com` is removed, and the next boot does not start it again.
2. On this playground's page, choose **Re-seed**. That puts **DNS domains** back to `unused.invalid` for the next pass. It also republishes the LLM proxy, with local Gemma as the default route, Qwen as its failover, and the Anthropic endpoint configured.

Stopping the playground leaves the daemon running. Do not use **Reset** on the Containers page. That removes the whole lab, including other demos.
