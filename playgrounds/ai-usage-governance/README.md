# AI Usage Governance — Claude Code

A Gravitee LLM proxy in front of Anthropic for Claude Code. The gateway checks a subscription API key. Claude Code keeps its own OAuth login, and that token is not stored in the playground.

## What it teaches

- How Claude Code sends `POST /v1/messages` through the gateway context path `/ai-usage-governance/`.
- How an API key plan reads `X-Gravitee-Api-Key` and leaves `Authorization` for Anthropic.
- How a missing key is rejected, and how a model outside `claude-*` is rejected.
- How analytics attributes an accepted call to the application **Claude Code developers**.

## Prerequisites

- Gravitee Lab with API Management 4.12 or later. The LLM proxy entrypoint and endpoint must be in the running gateway. That needs the enterprise license installed on the Lab.
- Docker, and the Lab platform up.
- Claude Code on this machine, signed in with `/login`, for the genuine Anthropic answer.
- macOS, for the Edge daemon. Install it once from Gamma, **Edge Management**, **Daemon deployment**. The playground does not install it. Power it with `scripts/edge up` and `scripts/edge down`, described under Edge.

The first start publishes one API. Plan about 4 minutes when the seeder image is already present. A cold seeder build takes longer.

| Setting | What it controls |
|---|---|
| `RICARDO_PUBLIC_DEMOS_AI_USAGE_GOVERNANCE_APIM_PASSWORD` | Password of admin in API Management. Match the platform admin password. |
| `RICARDO_PUBLIC_DEMOS_AI_USAGE_GOVERNANCE_API_KEY` | API key of the Claude Code developers subscription. |
| `RICARDO_PUBLIC_DEMOS_AI_USAGE_GOVERNANCE_GATEWAY_URL` | Gateway as a browser on this machine reaches it. The shared platform default is `http://localhost:8082`. An independent runtime uses the gateway port shown on its page. |
| `RICARDO_PUBLIC_DEMOS_AI_USAGE_GOVERNANCE_ENV_ID` | API Management environment to publish into. The default is `DEFAULT`. |
| `RICARDO_PUBLIC_DEMOS_AI_USAGE_GOVERNANCE_GATEWAY_READY_TIMEOUT` | Seconds the seed waits until the gateway serves the API. |
| `RICARDO_PUBLIC_DEMOS_AI_USAGE_GOVERNANCE_PULL_POLICY` | `build` builds the seeder here at each start. `never` uses the image already present. `always` pulls it, and builds it here when the pull fails. |

Set a value in the playground's settings, or in the shell, before the first start when the platform password or the gateway address should differ from the demo defaults.

## Start

1. Open the Lab UI and select **Ricardo's public demos**.
2. Open **AI Usage Governance**.
3. To run it beside another demo, create an independent runtime from this playground and start that runtime. A start on the shared platform stops the playground that is already on. The dialog asks before it does that.
4. Choose **Start**.
5. From the catalog folder, run `playgrounds/ai-usage-governance/scripts/edge up`. That powers the daemon with interception off.

| Surface | Address |
|---|---|
| Gamma console | http://localhost:8086 |
| LLM proxy | http://localhost:8086/environments/default/aim/llm-proxy/a1c0de00-0000-4000-8000-000000000001 |
| Gateway | http://localhost:8082/ai-usage-governance/v1/messages |

On an independent runtime, use the gateway and console addresses on that runtime's page. The context path stays `/ai-usage-governance/`.

Follow `guide.md` beside the console. The pass takes about 15 minutes.

## Accounts

Copy the username, password, and key from **Details → Accounts**.

- **Gamma console.** Username `admin`.
- **Claude Code developers.** The subscription key sent as `X-Gravitee-Api-Key`. The demo default is a public value, `ai-usage-governance-demo`. Change it in the setting above and re-seed when the meeting should use another key.

Do not put a Claude OAuth token, an Anthropic API key, or a license in this folder or in git.

## Edge

The seed publishes the Edge configuration. The daemon is installed on the Mac from Gamma, **Edge Management**, **Daemon deployment**. The seed does not start it, and **Stop** does not stop it.

From the catalog folder:

```bash
playgrounds/ai-usage-governance/scripts/edge up
playgrounds/ai-usage-governance/scripts/edge down
playgrounds/ai-usage-governance/scripts/edge status
```

`up` starts the daemon after the reactor on `127.0.0.1:18093` is up, and it does not hijack `api.anthropic.com`. `down` stops it, removes that DNS override, and keeps it from starting at the next boot. `status` reports the daemon, the interception, and the reactor.

Shadow AI watches `api.anthropic.com`. Interception starts off (`unused.invalid`). The pass starts with Claude Code talking to Anthropic. Edge Management shows that direct use. Replacing the DNS domain with `api.anthropic.com` turns interception on, and the next prompt lands on the one LLM proxy, **Governed models**. AI routing sends it to local `gemma4:12b` on Ollama. If that call fails, failover retries the same route on local `qwen3:1.7b`. The Anthropic endpoint on that same proxy keeps the Claude models visible. Prompt guard rails, PII filtering and a token limit run on the message. Other Anthropic calls land on **Anthropic passthrough**, which records the call and does not store the body. The daemon is macOS only. Ollama must be running on this machine with `gemma4:12b` and `qwen3:1.7b` pulled. The gateway reaches it at `OLLAMA_URL`, which defaults to `http://host.docker.internal:11434`.

## Reset

From the catalog folder, run `playgrounds/ai-usage-governance/scripts/edge down`. Then, on this playground's page or on its independent runtime, choose **Re-seed**.

`down` stops the daemon and clears the DNS override. Re-seed puts interception back to off and keeps shadow AI watching `api.anthropic.com`. It also republishes the LLM proxy. Local Gemma stays the default route, Qwen stays the failover, and the Anthropic endpoint stays configured. The gateway and reactor addresses cannot change after the first save.

**Stop → Delete what it created** removes only what this seed recorded. **Reset** on the Containers page deletes the whole lab. Do not use it while another demo is running.

The same seed is safe to run again. It replaces this LLM proxy because that API type cannot be updated in place, then subscribes the same application with the same key.
