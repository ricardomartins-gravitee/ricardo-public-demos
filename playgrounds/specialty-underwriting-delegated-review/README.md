# Specialty underwriting delegated review

A reviewer signs in, a hosted agent reads one synthetic cyber submission with a delegated token, and the gateway refuses that agent when it tries to mark the submission ready for quote. The same reviewer can mark it ready. The record is fixture data for the line `CYBER`. Marking it ready does not quote or bind coverage.

## What it needs

API Management and Access Management 4.13 or later, with Gamma's agent catalog, the MCP proxy, and Authorization Management. The license features the playground names are `gamma-aim-module` and `apim-mcp-proxy-reactor`.

No model, Ollama, or external issuer. Every token is from the domain `specialty-underwriting` on this lab.

## Start

Start it from its page in the Lab UI. The first start builds three images and seeds the domain, the agent, the proxy, and the policies. The review page is http://localhost:8170. Gamma is http://localhost:8086. Access Management is http://localhost:8081.

`/api/ready` answers when the agent and the submission service are up.

## Accounts

| Who | Username | Setting |
|---|---|---|
| Casey Hale, cyber underwriter | `casey.hale@specialty-underwriting.test` | `RICARDO_PUBLIC_DEMOS_SPECIALTY_UNDERWRITING_DELEGATED_REVIEW_DEMO_PASSWORD` |
| Jordan Clerk, not an underwriter | `jordan.clerk@specialty-underwriting.test` | the same password setting |
| Gamma and API Management | `admin` | `RICARDO_PUBLIC_DEMOS_SPECIALTY_UNDERWRITING_DELEGATED_REVIEW_APIM_PASSWORD` |
| Access Management | `admin` | `RICARDO_PUBLIC_DEMOS_SPECIALTY_UNDERWRITING_DELEGATED_REVIEW_AM_PASSWORD` |

The review page client is `specialty-underwriting-web`. The agent client is `cyber-review-agent`. The MCP resource client is `specialty-underwriting-mcp`. Their secrets are the `WEB_CLIENT_SECRET`, `AGENT_CLIENT_SECRET`, and `MCP_RESOURCE_SECRET` settings, with the catalog prefix `RICARDO_PUBLIC_DEMOS_SPECIALTY_UNDERWRITING_DELEGATED_REVIEW_`.

The underwriter access token is valid for 10 minutes. Reset drops the page session. It does not revoke a token already issued, and it says nothing about a token from another issuer.

## What stays

Deleting what the seed created removes the domain, the clients, the proxy, and the policies it recorded. Gamma's link to Access Management stays, because the platform has no API that removes it. A link that already points at another working domain is left as it is.

The submission service has no host port. Reset and observation are not MCP tools.
