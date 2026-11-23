# Call Stage

A page that sends the HTTP calls a file names and draws the path of each one. The browser asks this page. This page calls the target, so the gateway does not need a CORS policy.

Open it at http://localhost:8155, or as the **Call Stage** tab of a playground that lists `call-stage-ui`.

## Calls

Mount a JSON file over `/app/calls.json`. Each call is a tab. A tab that asks for a key, or has a hint, opens a panel between the tabs and the diagram.

| Field | What it is |
|---|---|
| `title` | The heading of the page |
| `id` | The name the page uses to send that call |
| `name` | The label of the tab |
| `panel` | Heading of the panel that opens under the tabs. Used when this call has a key to paste or a hint |
| `hint` | Text in that panel when there is nothing to type |
| `method` | The HTTP method. `GET` when omitted |
| `url` | The address this container calls |
| `show` | The address the page shows. Use the address a person on this machine would call |
| `headers` | Headers sent with the call. `${NAME}` is read from the container's environment |
| `keyFrom` | `input` when the person pastes a key. The field opens in the panel under the tabs |
| `keyHeader` | The header that receives that key. `X-Gravitee-Api-Key` when omitted |
| `token` | `{url, clientId, clientSecret, scope}`. The page asks that token endpoint for a client-credentials token and sends it as `Authorization: Bearer`. `clientSecret` may be `${NAME}`. The secret and the token stay on this page |

A call id that is not in the file is refused. A credential header is masked in the result. The pasted key is not stored.

The diagram is not in the file. It is read from the response after the call runs. A Gravitee header puts Gravitee on the path. A JSON body puts the API on the path. The response is drawn back along the participants that answered. Click a box to read the request and the response.

When the management API settings are set, the page also reads Gravitee's own log for that call. The diagram box stays short. Click it to read the plan, the application, how long the gateway took, and the reason Gravitee recorded. The log is written just after the call, so it appears in that detail a few seconds later. A refresh does not keep it.

## Settings

| Setting | What it controls |
|---|---|
| `RICARDO_PUBLIC_DEMOS_CALL_STAGE_PULL_POLICY` | `build` builds the page here at each start. `always` pulls it, and builds it here when the pull fails. |
| `CALL_STAGE_MANAGEMENT_URL` | Management API to read a call's log from. The log is left out when this is empty |
| `CALL_STAGE_MANAGEMENT_USERNAME` | User that can read API logs |
| `CALL_STAGE_MANAGEMENT_PASSWORD` | Password of that user |
| `CALL_STAGE_MANAGEMENT_ORG` | Organization. `DEFAULT` when omitted |
| `CALL_STAGE_MANAGEMENT_ENV` | Environment. `DEFAULT` when omitted |

Put a secret the calls need in the environment of `call-stage-ui`, and name it from the calls file as `${NAME}`.
