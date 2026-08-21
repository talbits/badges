# Badges

The Badges extension lets an LNbits user create independent NIP-58 badge definitions and issue awards to passport public keys.

The companion passport/scanner application is outside this extension. It uses the public claim API:

- `GET /badges/api/v1/public/claims/{claim_token}`
- `POST /badges/api/v1/public/claims/{claim_token}`
- `GET /badges/api/v1/public/passports/{passport_pubkey}/badges`

Configure one issuer `nsec` per LNbits user. The extension stores it encrypted, does not return it, and does not support key rotation. Relay configuration and publication are handled by the `nostrclient` extension.
