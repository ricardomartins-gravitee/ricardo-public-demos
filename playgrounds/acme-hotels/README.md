# 🏨 ACME Hotels

ACME Hotels built three agents. The concierge answers a guest on the hotel website, it asks a booking desk to search hotels, and it asks a loyalty desk for an offer. The loyalty desk is registered as a Bedrock AgentCore runtime in a local AWS account. Gravitee calls the desk, and the desk calls back through the gateway for its model and its tools. In this playground you put all three behind the Gravitee gateway: the gateway caches questions, limits tokens, blocks risky prompts, and, with Access Management and Authorization Management, decides which bookings a guest may see. The agents call `gemma4:12b`. If that call fails, the LLM proxy tries `qwen3:1.7b`. `qwen3:0.6b` stays listed and is not that retry. Agent Management also lists the tools, the booking desk's prompts and resources, a studio, a workspace and a dashboard. Gemini, OpenAI and Anthropic join that catalog when their keys are set. It takes about 45 minutes.

This is the copy in Ricardo's public demos, taken from Gravitee public's ACME Hotels so further lessons can be added here. The hotel website, the hotels' REST API and the concierge and booking-desk processes are still built from the [Gravitee AI Agent Workshop](https://github.com/gravitee-io-labs/Gravitee-AI-Agent-Workshop), at the same fixed commit. The booking desk is that agent a second time, with its own instructions. The loyalty desk and the small bridge that lets the concierge call the other agents are in this playground. All of ACME Hotels' data is invented: its hotels, bookings, guest and loyalty offers.

Start Gravitee public's ACME Hotels or this playground, and turn the other off first. Both create the same APIs and the Access Management domain `acme-hotels`.

## What you need

| Need | Details |
|---|---|
| An Enterprise license | It must include the AI features of API Management (the LLM, A2A and MCP tool server proxies, semantic caching, PII filtering and the AI models), Gamma Agent Management (the module, the MCP studio and the MCP tools endpoint), Gamma Authorization Management (the module, the policy engine and its AuthZEN endpoint), and the TCP reporter of the AI Agent Inspector. Add it from the **CE** chip of the Lab UI's Containers page. To get one, see [What needs a license](https://github.com/gravitee-io-labs/gravitee-lab/blob/main/docs/installation.md#what-needs-a-license). |
| API Management and Access Management 4.13 or later | Agent Management is seeded from 4.13. The playground's page checks the versions before you start. |
| Ollama on your machine, with `gemma4:12b` | See [Start it](#start-it). ACME Hotels on Windows is untested; the Ollama setup for it is not verified. |
| Internet access | The first start builds the apps from GitHub, with their packages from PyPI, and downloads the plugin `gravitee-policy-interrupt` from download.gravitee.io. The gateway downloads its AI models (129 MB) from huggingface.co the first time it deploys the LLM proxy. Without that access the seed, a one-time job that creates the playground's sample APIs and guest, ends with a timeout. |
| 10 GB of memory for Docker | |

The Lab UI checks the license features before you start: those in the `requires` block of [`compose.yml`](compose.yml), and those of the plugins that the APIs use.

## Start it

1. Install Ollama from [ollama.com/download](https://ollama.com/download), then pull the model:

   ```bash
   ollama pull gemma4:12b
   ```

   The containers must be able to reach Ollama. On Linux and WSL 2 it listens on `127.0.0.1` only by default, which they cannot reach: [Troubleshooting](https://github.com/gravitee-io-labs/gravitee-lab/blob/main/docs/troubleshooting.md#ollama-is-not-reachable-from-the-containers) has the steps. If Ollama runs somewhere else, set `OLLAMA_URL`.

2. Run `make ui`, open **Playgrounds** > **🏨 ACME Hotels**, and fix the warnings under **Before you start**.
3. Click **Start**. The first start takes about 12 minutes after the images are pulled: it builds the apps, installs the `gravitee-policy-interrupt` plugin, starts the platform, the local AWS account and the add-ons the playground brings, and runs the seed. When the start ends, the page shows the guide next to the APIM Console and Gamma.

The apps are built here from the workshop repository at each start. Set `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_PULL_POLICY` to `always` to pull the images that CI builds instead: [Built here, or pulled](https://github.com/gravitee-io-labs/gravitee-lab/blob/main/docs/configuration.md#built-here-or-pulled) has the details.

## Ports and URLs

| Port | What it is | Login |
|---|---|---|
| 8130 | The ACME Hotels website, http://localhost:8130 | The guest below |
| 8131 | The hotels' REST API, unprotected: calling it skips the gateway. Documentation: http://localhost:8131/docs | None |
| 8166 | The local AWS account, http://localhost:8166 | Access key `test`, secret key `test` |

Every port binds `127.0.0.1`. The agent's card is behind the gateway's A2A proxy, at http://localhost:8082/hotel-agent/.well-known/agent-card.json. The lessons also use the consoles of the platform:

| Port | Console | Login |
|---|---|---|
| 8084 | APIM Console, http://localhost:8084 | `admin` / `admin` |
| 8086 | Gamma, http://localhost:8086 | `admin` / `admin` |
| 8081 | Access Management console, http://localhost:8081 | `admin` / `adminadmin` |

The add-ons the playground brings come from Gravitee public. They have their own ports and logins: [AI Agent Inspector](https://github.com/gravitee-io-labs/gravitee-lab-public-catalog/blob/main/addons/ai-agent-inspector/README.md) (9002), [RedisInsight](https://github.com/gravitee-io-labs/gravitee-lab-public-catalog/blob/main/addons/redisinsight/README.md) (5540) and [MCPJam Inspector](https://github.com/gravitee-io-labs/gravitee-lab-public-catalog/blob/main/addons/mcpjam-inspector/README.md) (6274).

## Logins and secrets

Everything here is a public demo value, for your machine only. The playground's **Details** tab lists the accounts with copy buttons; a password there is the value of its setting now.

| Account | Sign-in | Password | Setting |
|---|---|---|---|
| John Doe, guest of the website | `john.doe@gravitee.io` | `HelloWorld@123` | `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_DEMO_PASSWORD` |
| Gamma and APIM consoles | `admin` | `admin` | `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_APIM_PASSWORD` |
| Access Management console | `admin` | `adminadmin` | `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_AM_PASSWORD` |

The two admin settings are the passwords the seed signs in with: set them if you changed those passwords in a console.

| Secret | Value | Setting |
|---|---|---|
| Booking desk, and the booking MCP | `hotel-ai-agent`, `hotel-mcp` | `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_AGENT_CLIENT_SECRET`, `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_MCP_RESOURCE_SECRET` |

Set them before the first start. The seed writes the password and the secrets into Access Management when it creates them, and keeps what it finds on later runs, so on a lab that is already set up a new value needs a reset. Write `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_MCP_RESOURCE_SECRET` in letters, digits and dashes: the gateway's script for the bookings, which the seed also writes into the API, uses it in a string.

## Settings

Set them from the key button of the playground in the Lab UI. Compose reads a setting from the shell first, then the root `.env`, then the playground's own `.env`, then the default. The **Details** tab follows the same order.

| Setting | Default | Meaning |
|---|---|---|
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_PULL_POLICY` | `build` | `build` builds the apps and the seed here at each start, `always` pulls the published images and builds them here if a pull is refused |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_GATEWAY_READY_TIMEOUT` | `300` | Seconds the seed waits for the gateway to serve each API |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_APIM_PASSWORD` | `admin` | Password of user `admin` in API Management, which the seed signs in with. Set it if you changed that password in the console |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_AM_PASSWORD` | `adminadmin` | Password of user `admin` in Access Management, which the seed signs in with. Set it if you changed that password in the console |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Where Ollama listens, as the containers reach it |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_GEMINI_API_KEY` | empty | Optional Google AI Studio key. Empty skips the Gemini provider. The LLM proxy keeps a placeholder until this is set |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_OPENAI_API_KEY` | empty | Optional OpenAI key. Empty skips the OpenAI provider |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_ANTHROPIC_API_KEY` | empty | Optional Anthropic key. Empty skips the Anthropic provider |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_AWS_ACCESS_KEY_ID` | `test` | Access key of the local AWS account. MiniStack treats the key as the account id |
| `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_AWS_SECRET_ACCESS_KEY` | `test` | Secret key of the local AWS account |
| `MINISTACK_VERSION` | `full` | Tag of the MiniStack image that simulates the AWS account |

The playground's own settings start with `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_`. `OLLAMA_URL` names Ollama on this machine and keeps that name. The optional Gemini key is `RICARDO_PUBLIC_DEMOS_ACME_HOTELS_PLUS_GEMINI_API_KEY`.

The demo secrets and passwords are settings too: they are in [Logins and secrets](#logins-and-secrets).

## What you learn

| Lesson | What the gateway does |
|---|---|
| 1 Cache similar questions | Answers a question close in meaning to an earlier one from its cache, without calling the model |
| 2 Limit tokens | Stops a caller that spent its tokens before the model is reached |
| 3 Block risky prompts | Reads each prompt with a small model and rejects the malicious ones |
| 4 Sign in and authorize | Accepts only the token the booking desk got by exchange, and filters the bookings with Authorization Management |
| 5 Look at the agent's tools | Turns the hotels' REST API into MCP tools that any MCP client finds |
| 6 Ask the booking desk | The concierge has no hotel search. A hotel question calls the booking desk, through the gateway |
| 7 Walk the Agent Management catalog | Shows the agents, the local models, the tools, the prompts and resources, the studio, the workspace and the dashboard |
| 8 Ask the loyalty desk in AWS | The concierge calls the loyalty desk through the gateway. The desk is registered in the local AWS account and calls back for the model and the hotel tools |

The lessons are in [`guide.md`](guide.md). The Lab UI shows it next to the running consoles.

## Start the lessons over

The lessons can be done again as they are: the cache forgets an entry after a minute and the token limit starts over every 15 seconds. *Re-seed* runs the seed again: it changes nothing that is already as the files say.

## What stays after a removal

**Stop** with **Delete what it created** removes what the seed created in Gravitee: the APIs and the application of API Management, the Agent Management catalog of this playground, the authorization entities and policy, and the domain `acme-hotels` of Access Management, with its guest, its applications and its MCP server. A few things stay:

- the gateway's models volume, `data-acme-hotels-plus-gateway-models`, so that the next start does not download the AI models again
- the history of the calls in Elasticsearch, and the cache and the counters in Redis
- the plugin `gravitee-policy-interrupt`, in `plugins/apim` on your machine
- the volumes of the add-ons the playground brings, such as `data-mcp-inspector`
- the images built here
- two files on your machine: the record of what the seed created, which is empty after a removal, and your settings

**Reset**, in the Containers page's menu, deletes every container and volume, and empties the record. It leaves the plugin, the images and your settings.

## More

- [`guide.md`](guide.md): the lessons and "If something does not work".
- [The Gravitee AI Agent Workshop](https://github.com/gravitee-io-labs/Gravitee-AI-Agent-Workshop), where the apps come from.
- [Writing a playground](https://github.com/gravitee-io-labs/gravitee-lab/blob/main/docs/playgrounds.md).
