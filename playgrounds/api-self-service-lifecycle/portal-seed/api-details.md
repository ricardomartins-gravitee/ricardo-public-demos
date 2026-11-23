# $${api.name}

Version $${api.version}.

$${api.description}

## Operations

- `GET /v1/services` lists the shared services. The response has `count` and `services`.
- `GET /v1/services/{id}` returns one service. An unknown id responds with 404 and an error object.
- `GET /v1/health` reports whether the API is up.

Send the header `X-Gravitee-Api-Key` with the key of the subscribed application.
