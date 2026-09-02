const assert = require('node:assert/strict')

global.window = {
  NostrTools: {
    verifyEvent(event) {
      return event.valid !== false
    },
    nip19: {
      decode(value) {
        if (value === 'naddr1badkind') {
          return {type: 'naddr', data: {kind: 1}}
        }
        if (value === 'naddr1badtype') {
          return {type: 'npub', data: {kind: 30009}}
        }
        if (value === 'naddr1longid') {
          return {
            type: 'naddr',
            data: {
              identifier: 'x'.repeat(257),
              pubkey: 'a'.repeat(64),
              kind: 30009
            }
          }
        }
        if (value !== 'naddr1test') throw new Error('bad address')
        return {
          type: 'naddr',
          data: {
            identifier: 'badge',
            pubkey: 'a'.repeat(64),
            kind: 30009,
            relays: ['wss://hint.example', 'https://ignored.example']
          }
        }
      }
    }
  }
}

require('../static/public.js')

const {
  cleanNaddr,
  parseNaddr,
  selectRelays,
  hasNip07,
  getLocation,
  signClaimWithSigner,
  validateAward,
  hasBadge
} = window.BadgesPublic

assert.equal(cleanNaddr(' nostr://naddr1test '), 'naddr1test')
assert.equal(parseNaddr('nostr:naddr1test').relays[0], 'wss://hint.example/')
assert.throws(() => parseNaddr('naddr1badkind'), /Nostr badge address/)
assert.throws(() => parseNaddr('naddr1badtype'), /Nostr badge address/)
assert.throws(() => parseNaddr('naddr1longid'), /incomplete/)
assert.throws(() => parseNaddr('x'.repeat(4097)), /too long/)
assert.deepEqual(
  selectRelays(
    ['wss://hint.example', 'wss://known.example'],
    ['wss://hint.example', 'https://ignored.example'],
    ['wss://fallback.example']
  ),
  ['wss://hint.example/', 'wss://known.example/', 'wss://fallback.example/']
)
assert.equal(
  selectRelays(
    Array.from({length: 20}, (_, index) => `wss://relay-${index}.example`),
    [],
    []
  ).length,
  10
)

assert.equal(hasNip07({getPublicKey() {}}), false)
Object.defineProperty(globalThis, 'navigator', {
  configurable: true,
  value: {
    geolocation: {
      getCurrentPosition(resolve, reject, options) {
        assert.equal(options.enableHighAccuracy, true)
        resolve({coords: {latitude: 1.2, longitude: 3.4, accuracy: 42}})
      }
    }
  }
})
const awardIssuer = 'd'.repeat(64)
const passportPubkey = 'b'.repeat(64)
const awardTags = [
  ['p', passportPubkey],
  ['a', `30009:${awardIssuer}:badge`]
]
assert.deepEqual(
  validateAward(
    {kind: 8, pubkey: awardIssuer, tags: awardTags},
    passportPubkey
  ),
  {issuer: awardIssuer, identifier: 'badge'}
)
assert.equal(
  validateAward(
    {kind: 8, pubkey: 'c'.repeat(64), tags: awardTags},
    passportPubkey
  ),
  null
)
assert.equal(
  hasBadge([{badge: {issuer: awardIssuer, d: 'badge'}}], {
    issuer: awardIssuer,
    d: 'badge'
  }),
  true
)
assert.equal(hasBadge([], {issuer: awardIssuer, d: 'other'}), false)

const subscriptionFilter = {}
const subscriptionVm = {
  pool: {
    subscribeMany(relays, filter) {
      subscriptionFilter.relays = relays
      subscriptionFilter.filter = filter
      return {close() {}}
    }
  },
  identity: {pubkey: passportPubkey},
  knownRelays: [],
  awardSubscription: null,
  handleAward() {}
}
window.PageBadgesClaim.methods.startAwardSubscription.call(subscriptionVm)
assert.deepEqual(
  {
    kinds: subscriptionFilter.filter.kinds,
    '#p': subscriptionFilter.filter['#p']
  },
  {kinds: [8], '#p': [passportPubkey]}
)
assert.equal(typeof subscriptionFilter.filter.since, 'number')

const pageMethods = window.PageBadgesClaim.methods
assert.equal(
  pageMethods.shortKey('1234567890123456789012345'),
  '1234567890...6789012345'
)
assert.equal(pageMethods.shortKey('short'), 'short')
assert.equal(
  window.PageBadgesClaim.computed.alreadyClaimed.call({
    collection: [{badge: {issuer: awardIssuer, d: 'badge'}}],
    badge: {issuer: awardIssuer, d: 'badge'}
  }),
  true
)

const duplicateClaimNotifications = []
const duplicateClaimVm = {
  badge: {issuer: awardIssuer, d: 'badge'},
  identity: {pubkey: passportPubkey},
  collection: [{badge: {issuer: awardIssuer, d: 'badge'}}],
  claiming: false,
  tab: 'scan',
  $q: {notify: notification => duplicateClaimNotifications.push(notification)}
}

const pubkey = 'b'.repeat(64)
const signer = {
  getPublicKey: async () => pubkey,
  nip04: {encrypt: async () => 'ciphertext'},
  signEvent: async event => ({...event, pubkey})
}
const mismatchedSigner = {
  ...signer,
  signEvent: async event => ({...event, pubkey: 'c'.repeat(64)})
}
const invalidSigner = {
  ...signer,
  signEvent: async event => ({...event, pubkey, valid: false})
}
const changedTimestampSigner = {
  ...signer,
  signEvent: async event => ({
    ...event,
    pubkey,
    created_at: event.created_at + 1
  })
}

;(async () => {
  assert.deepEqual(await getLocation(), {lat: 1.2, long: 3.4, accuracy: 42})
  const signed = await signClaimWithSigner(
    signer,
    'd'.repeat(64),
    {type: 'claim_poap', badge_id: 'badge'},
    pubkey
  )
  assert.equal(signed.pubkey, pubkey)
  assert.equal(signed.kind, 4)
  assert.deepEqual(signed.tags, [['p', 'd'.repeat(64)]])
  await assert.rejects(
    signClaimWithSigner(signer, 'd'.repeat(64), {}, 'a'.repeat(64)),
    /different identity/
  )
  await assert.rejects(
    signClaimWithSigner(mismatchedSigner, 'd'.repeat(64), {}, pubkey),
    /different identity/
  )
  await assert.rejects(
    signClaimWithSigner(invalidSigner, 'd'.repeat(64), {}, pubkey),
    /invalid signature/
  )
  await assert.rejects(
    signClaimWithSigner(changedTimestampSigner, 'd'.repeat(64), {}, pubkey),
    /changed the claim event/
  )

  const award = {
    id: 'award-1',
    kind: 8,
    pubkey: awardIssuer,
    tags: [
      ['p', passportPubkey],
      ['a', `30009:${awardIssuer}:badge`]
    ]
  }
  const awardVm = {
    identity: {pubkey: passportPubkey},
    collection: [],
    processingAwards: new Set(),
    knownRelays: [],
    badge: null,
    tab: 'scan',
    notifications: [],
    $q: {notify: notification => awardVm.notifications.push(notification)},
    pool: {
      get: async () => {
        await new Promise(resolve => setTimeout(resolve, 0))
        return {
          id: 'badge-1',
          pubkey: awardIssuer,
          content: 'badge',
          tags: [
            ['d', 'badge'],
            ['name', 'Badge']
          ]
        }
      }
    }
  }
  await Promise.all([
    window.PageBadgesClaim.methods.handleAward.call(awardVm, award),
    window.PageBadgesClaim.methods.handleAward.call(awardVm, {
      ...award,
      id: 'award-2'
    })
  ])
  assert.equal(awardVm.collection.length, 1)
  assert.equal(awardVm.notifications.length, 1)
  await window.PageBadgesClaim.methods.claimBadge.call(duplicateClaimVm)
  assert.equal(duplicateClaimVm.tab, 'passport')
  assert.match(
    duplicateClaimNotifications[0].message,
    /already have this badge/
  )
  console.log('badges public parsing/relay/signer checks passed')
})().catch(error => {
  console.error(error)
  process.exitCode = 1
})
