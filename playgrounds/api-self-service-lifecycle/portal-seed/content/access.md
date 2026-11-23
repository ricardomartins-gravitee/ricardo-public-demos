# Request access

Create an application in the Developer Portal.

Subscribe that application to the API Key plan of the Shared Services API.

Wait for the service owner to approve the subscription.

Copy the API key from the application.

Call the gateway with the header X-Gravitee-Api-Key set to that key.

Revoking the key stops that key. The application needs a new approved key before it can call the API again.
