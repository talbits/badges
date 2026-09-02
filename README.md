<a href="https://lnbits.com" target="_blank" rel="noopener noreferrer">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://i.imgur.com/QE6SIrs.png">
    <img src="https://i.imgur.com/fyKPgVT.png" alt="LNbits" style="width:280px">
  </picture>
</a>

[![License: MIT](https://img.shields.io/badge/License-MIT-success?logo=open-source-initiative&logoColor=white)](./LICENSE)
[![Built for LNbits](https://img.shields.io/badge/Built%20for-LNbits-4D4DFF?logo=lightning&logoColor=white)](https://github.com/lnbits/lnbits)

# Badges — [LNbits](https://github.com/lnbits/lnbits) extension

## Create collectible digital badges for events, meetups, places, and more

Badges lets you create collectible digital badges that visitors can claim and
keep in their own Nostr passport. Use it for event attendance, meetups,
communities, places, achievements, or loyalty programs.

As an issuer you work inside your LNbits account; your visitors only ever need
the badge's QR code.

## Usage

### For issuers

1. Enable Badges, then open it from your LNbits account.
2. Configure your issuer identity (a Nostr private key). It is stored
   encrypted and is never shown again.
3. Create a badge — give it a name, an image, a description, an optional
   availability window, and an optional location rule.
4. Show or print the badge's QR code and put it on display.
5. Watch collectors and export the claim list whenever you like.

You can create as many independent badges as you need — each one has its own QR
code, its own rules, and its own collectors.

### For visitors

1. Scan the QR code, or paste the badge link into the built-in public claim
   page — no app or account needed.
2. Create a passport right in your browser, import an existing Nostr key, or
   use a supported Nostr browser extension.
3. If the badge is location-aware, allow location access — it is only ever
   requested for badges that have a location rule.
4. Claim the badge. It appears in your passport straight away.

## Privacy

Your passport key stays in your browser and is never sent to the LNbits
server. Location is only requested for location-aware badges, only at claim
time, and only travels to the badge issuer.

## Requirements

Badges needs the **nostrclient** extension to be enabled and at least one relay
configured in it. Badge definitions and claims are published over Nostr.

## Development

Run `make test` for the extension tests. The target forces SQLite in a fresh
temporary data directory and removes that directory when the tests finish, so
it cannot use or delete a configured LNbits database.

Use `make format` and `make pyright` before the remaining checks:
`make checkruff`, `make checkblack`, and `make checkprettier`.

## Powered by LNbits

[LNbits](https://lnbits.com) is a free and open-source lightning accounts system.

[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
