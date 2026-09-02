# Badges

The Badges extension lets an LNbits user create independent NIP-58 badge definitions and issue awards to passport public keys.

The companion passport/scanner flow is an unauthenticated public dynamic page
inside this extension. It reads a public `nostr://naddr...` QR, fetches the
definition from Nostr, optionally requests browser location, sends an encrypted
NIP-04 claim DM to the issuer, and discovers the resulting passport awards from
Nostr. It does not use LNbits APIs or receive an admin/wallet key.

Configure one issuer `nsec` per LNbits user. The extension stores it encrypted,
does not return it, and does not support key rotation. Relay configuration and
publication are handled by the `nostrclient` extension. The authenticated
issuer page can use the existing wallet admin key to obtain configured relay
URLs and include them as relay hints in the public `naddr` QR.
