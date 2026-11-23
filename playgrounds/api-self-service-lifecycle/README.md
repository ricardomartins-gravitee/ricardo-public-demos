# API Self-Service & Credential Lifecycle

Developer self-service for one shared REST API, then the same API as tools for an approved agent. The developer creates an application in the Developer Portal and requests an API key. The service owner approves it, and can revoke it. The same API also accepts a token that lasts two minutes. After that, MCPJam Inspector calls the tool endpoint.

The playground publishes into the platform DEFAULT environment and its Developer Portal. Before starting it, stop another playground that publishes into that same portal with **Delete what it created**.

Consumer App A is created live, during the guide, and is absent from the seed.

Revoke, renew, and expiration are separate operations:

- Revoke stops an existing key. That is the live deny step.
- Renew issues another key. Overlap depends on the product: the previous key can remain valid until it is revoked or it expires.
- Expiration is a validity end. This demo leaves keys without an expiry.

## What it teaches

- How a shared REST API is published on the gateway with an API Key plan that waits for approval, and how a call with no key is refused.
- How the developer finds that API in the Developer Portal, reads its OpenAPI page, and tries a call from that page once the service owner has approved a key.
- How the developer creates Consumer App A and requests a subscription.
- How the service owner, the built-in user `api1`, approves the subscription and how the platform issues the key. Another team owns its own API, and this sign-in is refused that API. That part is said during the approval. The platform administrator can open every API.
- How Consumer App A calls the API with that key.
- How revoking Consumer App A's key rejects the next call, and how consumption shows that application's traffic.
- How Access Management issues a token that lasts two minutes, and how the Access token plan on the same API asks Access Management whether that token is still valid. The plan requires the scope `shared-services`.
- How a subscribed application is limited: reads only, 60 calls a minute, and 5000 calls a day. Those controls are one shared policy group. Shared Services API 1.0, Shared Services API 2.0, and Platform Notices API all use it. Version 1.0 stays published while 2.0 adds `channel`.
- How an approved agent calls the same API as tools, with a rate limit, a daily quota, a request size limit and a response stamp, and how a tool that was not granted is refused.

## Prerequisites

- A Lab with API Management 4.13 or later, and Docker.
- The platform admin account, the built-in service owner `api1`, and the built-in Developer Portal user `user`.
- A license that includes the Gamma MCP studio modules.

The Shared Services API image and Call Stage are published with this catalog and pulled at start. A pull that is refused builds that image here. MCPJam Inspector comes from the Gravitee public catalog. Plan about 6 minutes.

| Setting | What it controls |
|---|---|
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_APIM_PASSWORD` | Password of admin in API Management. Match the platform admin password. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_OWNER_PASSWORD` | Password of the platform user named `api1`, who acts as Service owner. Match that user's password. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_DEVELOPER_A_PASSWORD` | Password of the platform user named `user`, who acts as Developer. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_AGENT_KEY` | API key of Audit agent. MCPJam sends it as `X-Gravitee-Api-Key`. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_TOOL_KEY` | API key Gravitee uses when a tool calls the Shared Services API. It is not pasted. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_ENV_ID` | API Management environment to publish into. The default publishes into DEFAULT. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_PULL_POLICY` | `always` pulls the published API image. `build` builds it here at each start. A refused pull builds it here. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_AM_PASSWORD` | Password of admin in Access Management. Match the platform AM password. |
| `RICARDO_PUBLIC_DEMOS_API_SELF_SERVICE_LIFECYCLE_TOKEN_SECRET` | Secret of the Shared Services caller application. |

Set a value in the playground's settings, or in the shell, before the first start when the platform password should differ from the demo default in `compose.yml`. The catalog does not record a tested version set for this playground.

## Quick start

1. Open the Lab UI and select Ricardo's public demos.
2. Open **API Self-Service Lifecycle** and choose **Start**. The catalog row uses that name so it matches the folder `api-self-service-lifecycle`.

| Surface | Address |
|---|---|
| Gamma console | http://localhost:8086 |
| Call stage | http://localhost:8155 |
| MCPJam Inspector | http://localhost:6274/#token=gravitee-lab-local-inspector |
| Developer Portal | http://localhost:8085/next/ |
| Gateway | http://localhost:8082/shared-services/v1/services |
| Tool endpoint | http://localhost:8082/shared-services-tools/ |
| Shared Services API | http://localhost:8140/v1/services |

Follow `guide.md` beside the consoles. Each lesson links to the console it uses, and that link opens in the matching tab. The Call Stage tab sends the REST calls and draws the path of each one. MCPJam Inspector calls the tool endpoint. The pass takes about 25 minutes.

## Accounts

Copy usernames, passwords, and keys from **Details → Accounts**. The values there follow the settings, so a password changed for this Lab stays out of the guide.

- **Platform administrator.** Username `admin`, for the Gamma console.
- **Service owner.** The platform's built-in user `api1`, for the Gamma console. The seed makes this account the owner of Shared Services API and Shared Services tools. This account approves and revokes Consumer App A's key.
- **Developer.** The platform's built-in user `user`, shown as Developer Portal: Developer.
- **Audit agent.** The API key MCPJam sends to the tool endpoint. Shared Services gateway is the application Gravitee uses when a tool calls the API. Its key is not an account.
- **AM Console.** Username `admin`. This is the Access Management password, separate from the API Management administrator.
- **Shared Services caller.** The client secret of the Access Management application whose access token lasts 120 seconds.
- **MCPJam Inspector.** Included from the public catalog, on port 6274. The session token is in the console link. The default is the public demo value `gravitee-lab-local-inspector`.

## Reset

In the Gamma console, open **Applications**, open **Consumer App A**, close its subscription, and delete the application. Then re-seed this playground in the Lab UI.

Re-seed runs the playground seed again and republishes Shared Services API, Shared Services API 2.0, Platform Notices API, the subscriber controls, the Access token plan, the tool endpoint, and this demo's Developer Portal content into DEFAULT. Audit agent, Shared Services gateway, and Shared Services caller stay. The APIs stay. Consumer App A is absent after you delete it.

A **Containers Reset** deletes the whole lab. Leave it unused while other demos still have data.

## Troubleshooting

**Provisioning.** The seed service is `api-self-service-lifecycle-seed`. It must finish successfully. If the Shared Services API is missing, start the playground or re-seed it. The API container is healthy when its own `http://localhost:8000/health` check succeeds. The calls in the guide use `http://localhost:8140/v1/services`.

**A subscription stays pending.** The API Key plan uses manual approval. Sign in as the service owner, open Shared Services API, then **Consumers**, and accept the pending subscription for Consumer App A.

**401 or 403.** The gateway rejects a call with no key, a wrong key, or a revoked key. A valid key for Consumer App A returns 200. Either 401 or 403 is a rejection from this gateway. The backend on port 8140 does not check the key. The gateway does.

**Portal or gateway.** Sign in to the Developer Portal at http://localhost:8085/next/ as user `user`. Call the gateway at http://localhost:8082/shared-services/v1/services. This playground publishes into the DEFAULT Developer Portal. Stop another playground that uses that portal with **Delete what it created** before starting this one. Re-seed refreshes this playground's portal content.

`collections/shared-services.http` holds REST Client calls. Fill `{{consumerKey}}` and `{{revokedKey}}` locally. Keep real key values out of git.
