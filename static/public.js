const BADGES_PUBLIC_RELAYS = [
  'wss://relay.damus.io',
  'wss://nos.lol',
  'wss://relay.primal.net',
  'wss://relay.nostr.com'
]
const MAX_NADDR_LENGTH = 4096
const MAX_IDENTIFIER_LENGTH = 256
const MAX_RELAYS = 10
const MAX_COLLECTION = 200
const IDENTITY_STORAGE_KEY = 'badges.passport'
const RELAYS_STORAGE_KEY = 'badges.relays'

function cleanNaddr(value) {
  return String(value || '')
    .trim()
    .replace(/^nostr:\/\//i, '')
    .replace(/^nostr:/i, '')
}

function validRelay(value) {
  try {
    const url = new URL(value)
    return ['ws:', 'wss:'].includes(url.protocol) ? url.toString() : null
  } catch {
    return null
  }
}

function selectRelays(
  hinted = [],
  known = [],
  fallback = BADGES_PUBLIC_RELAYS
) {
  const relays = []
  const seen = new Set()
  for (const candidates of [hinted, known, fallback]) {
    if (!Array.isArray(candidates)) continue
    for (const candidate of candidates) {
      const relay = validRelay(candidate)
      if (relay && !seen.has(relay)) {
        seen.add(relay)
        relays.push(relay)
        if (relays.length === MAX_RELAYS) return relays
      }
    }
  }
  return relays
}

function parseNaddr(value) {
  const encoded = cleanNaddr(value)
  if (!encoded) throw new Error('Enter or scan a badge address.')
  if (encoded.length > MAX_NADDR_LENGTH) {
    throw new Error('The badge address is too long.')
  }
  const decoded = window.NostrTools.nip19.decode(encoded)
  if (
    !decoded ||
    decoded.type !== 'naddr' ||
    !decoded.data ||
    typeof decoded.data !== 'object' ||
    Array.isArray(decoded.data) ||
    decoded.data.kind !== 30009
  ) {
    throw new Error('This is not a Nostr badge address.')
  }
  const {identifier, pubkey} = decoded.data
  if (
    typeof identifier !== 'string' ||
    !identifier ||
    identifier.length > MAX_IDENTIFIER_LENGTH ||
    typeof pubkey !== 'string' ||
    !/^[0-9a-f]{64}$/i.test(pubkey)
  ) {
    throw new Error('The badge address is incomplete.')
  }
  const relays = Array.isArray(decoded.data.relays) ? decoded.data.relays : []
  return {
    encoded,
    identifier,
    pubkey,
    relays: relays.map(validRelay).filter(Boolean)
  }
}

function readStorage(key, fallback) {
  try {
    const value = window.localStorage.getItem(key)
    const parsed = value ? JSON.parse(value) : fallback
    return Array.isArray(fallback) && !Array.isArray(parsed) ? fallback : parsed
  } catch {
    return fallback
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Private browsing or a disabled storage backend should not block claims.
  }
}

function badgeFromEvent(event) {
  const badge = {id: event.id, issuer: event.pubkey, content: event.content}
  for (const tag of event.tags || []) {
    if (tag.length > 1 && badge[tag[0]] === undefined) badge[tag[0]] = tag[1]
  }
  return badge
}

function hasLocationSubject(badge) {
  return badge.subject === 'poap:location'
}

function hasBadge(collection, badge) {
  if (
    !Array.isArray(collection) ||
    typeof badge?.issuer !== 'string' ||
    typeof badge?.d !== 'string'
  )
    return false
  return collection.some(
    item => item.badge?.issuer === badge.issuer && item.badge?.d === badge.d
  )
}

function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(
        new Error('This badge requires browser location, which is unavailable.')
      )
      return
    }
    navigator.geolocation.getCurrentPosition(
      ({coords}) =>
        resolve({
          lat: coords.latitude,
          long: coords.longitude,
          accuracy: coords.accuracy
        }),
      () =>
        reject(
          new Error('Location permission is required to claim this badge.')
        ),
      {enableHighAccuracy: true, timeout: 10000, maximumAge: 0}
    )
  })
}

function decodeIdentity(value) {
  const tools = window.NostrTools
  if (String(value).startsWith('nsec')) {
    const decoded = tools.nip19.decode(String(value))
    if (decoded.type !== 'nsec') throw new Error('Invalid nsec.')
    return decoded.data
  }
  if (!/^[0-9a-f]{64}$/i.test(value))
    throw new Error('Enter a valid nsec or private key.')
  return tools.utils.hexToBytes(value)
}

function identityFromSecret(secretKey) {
  const tools = window.NostrTools
  const nsec = tools.nip19.nsecEncode(secretKey)
  const pubkey = tools.getPublicKey(secretKey)
  return {secretKey, nsec, pubkey, npub: tools.nip19.npubEncode(pubkey)}
}

function hasNip07(signer = window.nostr) {
  return Boolean(
    signer &&
      typeof signer.getPublicKey === 'function' &&
      typeof signer.nip04?.encrypt === 'function' &&
      typeof signer.signEvent === 'function'
  )
}

function validateSignedEvent(signed, expectedPubkey, unsigned) {
  if (!signed || typeof signed !== 'object') {
    throw new Error('The signer returned an invalid event.')
  }
  if (
    typeof signed.pubkey !== 'string' ||
    signed.pubkey.toLowerCase() !== expectedPubkey.toLowerCase()
  ) {
    throw new Error('The signer returned a different identity.')
  }
  if (
    unsigned &&
    (signed.kind !== unsigned.kind ||
      signed.created_at !== unsigned.created_at ||
      signed.content !== unsigned.content ||
      JSON.stringify(signed.tags) !== JSON.stringify(unsigned.tags))
  ) {
    throw new Error('The signer changed the claim event.')
  }
  if (!window.NostrTools.verifyEvent(signed)) {
    throw new Error('The signer returned an invalid signature.')
  }
  return signed
}

async function signClaimWithSigner(signer, issuer, payload, expectedPubkey) {
  if (!hasNip07(signer))
    throw new Error('A compatible Nostr extension is required.')
  const unsigned = {
    kind: 4,
    created_at: Math.floor(Date.now() / 1000),
    tags: [['p', issuer]]
  }
  unsigned.content = await signer.nip04.encrypt(issuer, JSON.stringify(payload))
  return validateSignedEvent(
    await signer.signEvent(unsigned),
    expectedPubkey,
    unsigned
  )
}

function validateAward(award, expectedPubkey) {
  const tags = Array.isArray(award?.tags) ? award.tags : []
  const passport = tags.find(
    tag => Array.isArray(tag) && tag[0] === 'p' && tag[1]
  )?.[1]
  const aTag = tags.find(tag => Array.isArray(tag) && tag[0] === 'a' && tag[1])
  const [kind, issuer, ...identifierParts] = aTag?.[1]?.split(':') || []
  const identifier = identifierParts.join(':')
  if (
    award?.kind !== 8 ||
    typeof expectedPubkey !== 'string' ||
    typeof passport !== 'string' ||
    passport?.toLowerCase() !== expectedPubkey.toLowerCase() ||
    kind !== '30009' ||
    !issuer ||
    !identifier ||
    typeof award?.pubkey !== 'string' ||
    award.pubkey !== issuer
  ) {
    return null
  }
  return {issuer, identifier}
}

window.BadgesPublic = {
  cleanNaddr,
  parseNaddr,
  selectRelays,
  MAX_NADDR_LENGTH,
  MAX_RELAYS,
  hasNip07,
  getLocation,
  validateSignedEvent,
  signClaimWithSigner,
  validateAward,
  hasBadge
}

window.PageBadgesClaim = {
  template: '#page-badges-claim',
  data() {
    const savedIdentity = readStorage(IDENTITY_STORAGE_KEY, null)
    let identity = {secretKey: null, nsec: '', pubkey: '', npub: ''}
    const storedSignerPubkey =
      savedIdentity?.mode === 'signer' &&
      /^[0-9a-f]{64}$/i.test(savedIdentity.pubkey || '')
        ? savedIdentity.pubkey.toLowerCase()
        : ''
    const storedSignerMode = savedIdentity?.mode === 'signer'
    if (storedSignerMode) {
      writeStorage(
        IDENTITY_STORAGE_KEY,
        storedSignerPubkey ? {mode: 'signer', pubkey: storedSignerPubkey} : null
      )
    }
    if (!storedSignerMode && savedIdentity?.nsec) {
      try {
        identity = identityFromSecret(decodeIdentity(savedIdentity.nsec))
      } catch {
        writeStorage(IDENTITY_STORAGE_KEY, null)
      }
    }
    return {
      tab: 'scan',
      naddrInput: '',
      badge: null,
      parsedBadge: null,
      identity,
      identityInput: '',
      showNsec: false,
      storedSignerPubkey,
      collection: [],
      loadingBadge: false,
      collectionLoading: false,
      claiming: false,
      pool: null,
      awardSubscription: null,
      processingAwards: new Set(),
      knownRelays: readStorage(RELAYS_STORAGE_KEY, [])
    }
  },
  computed: {
    hasNip07() {
      return hasNip07()
    },
    needsLocation() {
      return this.badge ? hasLocationSubject(this.badge) : false
    },
    alreadyClaimed() {
      return hasBadge(this.collection, this.badge)
    }
  },
  async mounted() {
    this.g.scanner = null
    this.pool = new window.NostrTools.SimplePool()
    const naddr = this.$route.query.naddr
    if (naddr) await this.loadBadge(naddr)
    if (this.storedSignerPubkey) {
      try {
        await this.activateSigner(this.storedSignerPubkey)
      } catch (error) {
        this.showError(error)
      }
    } else if (this.identity.pubkey) {
      this.startAwardSubscription()
      await this.loadCollection()
    }
  },
  beforeUnmount() {
    this.g.scanner = null
    this.awardSubscription?.close()
    this.pool?.destroy()
  },
  methods: {
    shortKey(value) {
      const key = String(value || '')
      return key.length > 23 ? `${key.slice(0, 10)}...${key.slice(-10)}` : key
    },
    startScan() {
      this.g.scanner = value => this.loadBadge(value)
    },
    async loadBadge(value) {
      this.loadingBadge = true
      try {
        const parsed = parseNaddr(value)
        this.parsedBadge = parsed
        this.naddrInput = value
        this.knownRelays = selectRelays(parsed.relays, this.knownRelays, [])
        writeStorage(RELAYS_STORAGE_KEY, this.knownRelays)
        const relays = selectRelays(parsed.relays, this.knownRelays)
        const event = await this.pool.get(relays, {
          kinds: [30009],
          authors: [parsed.pubkey],
          '#d': [parsed.identifier]
        })
        if (!event)
          throw new Error('Badge definition was not found on the relays.')
        this.badge = badgeFromEvent(event)
        if (
          this.badge.issuer !== parsed.pubkey ||
          this.badge.d !== parsed.identifier
        ) {
          throw new Error('The relay returned a different badge definition.')
        }
        this.tab = 'scan'
      } catch (error) {
        this.badge = null
        this.$q.notify({
          type: 'negative',
          message: error.message || 'Could not load this badge.'
        })
      } finally {
        this.loadingBadge = false
      }
    },
    generateIdentity() {
      this.setIdentity(
        identityFromSecret(window.NostrTools.generateSecretKey())
      )
    },
    importIdentity() {
      try {
        this.setIdentity(identityFromSecret(decodeIdentity(this.identityInput)))
        this.identityInput = ''
      } catch (error) {
        this.$q.notify({
          type: 'negative',
          message: error.message || 'Could not import identity.'
        })
      }
    },
    setIdentity(identity) {
      this.identity = identity
      this.showNsec = false
      this.storedSignerPubkey = ''
      writeStorage(IDENTITY_STORAGE_KEY, {mode: 'local', nsec: identity.nsec})
      this.startAwardSubscription()
      this.loadCollection()
    },
    async useSignerIdentity() {
      if (!hasNip07()) return
      if (this.identity.pubkey && !this.identity.signerBacked) {
        LNbits.utils
          .confirmDialog(
            'Switch to the Nostr extension? The local identity will be removed from this page. Back up its nsec first if you need it later.'
          )
          .onOk(() =>
            this.activateSigner().catch(error => this.showError(error))
          )
        return
      }
      try {
        await this.activateSigner()
      } catch (error) {
        this.showError(error)
      }
    },
    async activateSigner(expectedPubkey = '') {
      if (!hasNip07()) {
        throw new Error('A compatible Nostr extension is not available.')
      }
      const pubkey = String(await window.nostr.getPublicKey()).toLowerCase()
      if (!/^[0-9a-f]{64}$/.test(pubkey)) {
        throw new Error('The Nostr extension returned an invalid public key.')
      }
      if (expectedPubkey && pubkey !== expectedPubkey.toLowerCase()) {
        throw new Error(
          'The Nostr extension identity changed; choose it explicitly.'
        )
      }
      this.identity = {
        secretKey: null,
        nsec: '',
        pubkey,
        npub: window.NostrTools.nip19.npubEncode(pubkey),
        signer: window.nostr,
        signerBacked: true
      }
      this.showNsec = false
      this.storedSignerPubkey = pubkey
      writeStorage(IDENTITY_STORAGE_KEY, {mode: 'signer', pubkey})
      this.startAwardSubscription()
      await this.loadCollection()
    },
    showError(error) {
      this.$q.notify({
        type: 'negative',
        message: error.message || 'Could not change identity.'
      })
    },
    forgetIdentity() {
      LNbits.utils
        .confirmDialog(
          'Forget this passport identity? Your nsec will be removed from this browser.'
        )
        .onOk(() => {
          this.awardSubscription?.close()
          this.awardSubscription = null
          writeStorage(IDENTITY_STORAGE_KEY, null)
          this.identity = {secretKey: null, nsec: '', pubkey: '', npub: ''}
          this.collection = []
          this.showNsec = false
          this.storedSignerPubkey = ''
        })
    },
    async claimBadge() {
      if (!this.badge || !this.identity.pubkey) return
      if (this.claiming) return
      if (hasBadge(this.collection, this.badge)) {
        this.$q.notify({
          type: 'info',
          message: 'You already have this badge in your passport.'
        })
        this.tab = 'passport'
        return
      }
      this.claiming = true
      try {
        const content = {badge_id: this.badge.d, type: 'claim_poap'}
        if (this.needsLocation) Object.assign(content, await getLocation())
        const event = {
          kind: 4,
          created_at: Math.floor(Date.now() / 1000),
          tags: [['p', this.badge.issuer]]
        }
        let signed
        if (this.identity.signerBacked) {
          signed = await signClaimWithSigner(
            this.identity.signer,
            this.badge.issuer,
            content,
            this.identity.pubkey
          )
        } else {
          event.content = await window.NostrTools.nip04.encrypt(
            this.identity.secretKey,
            this.badge.issuer,
            JSON.stringify(content)
          )
          signed = validateSignedEvent(
            window.NostrTools.finalizeEvent(event, this.identity.secretKey),
            this.identity.pubkey,
            event
          )
        }
        await Promise.any(
          this.pool.publish(
            selectRelays(this.parsedBadge?.relays || [], this.knownRelays),
            signed
          )
        )
        this.$q.notify({
          type: 'info',
          message: 'Claim sent. Waiting for the issuer award…'
        })
        this.startAwardSubscription()
      } catch (error) {
        this.$q.notify({
          type: 'negative',
          message: error.message || 'Could not send the claim.'
        })
      } finally {
        this.claiming = false
      }
    },
    startAwardSubscription() {
      if (!this.pool || !this.identity.pubkey) return
      this.awardSubscription?.close()
      const relays = selectRelays([], this.knownRelays)
      this.awardSubscription = this.pool.subscribeMany(
        relays,
        {
          kinds: [8],
          '#p': [this.identity.pubkey],
          since: Math.floor(Date.now() / 1000)
        },
        {onevent: event => this.handleAward(event)}
      )
    },
    async loadCollection() {
      if (!this.pool || !this.identity.pubkey) return
      this.collectionLoading = true
      try {
        const events = await this.pool.querySync(
          selectRelays([], this.knownRelays),
          {
            kinds: [8],
            '#p': [this.identity.pubkey],
            limit: MAX_COLLECTION
          }
        )
        await Promise.all(events.map(event => this.handleAward(event, false)))
      } catch (error) {
        this.$q.notify({
          type: 'negative',
          message: error.message || 'Could not load your passport.'
        })
      } finally {
        this.collectionLoading = false
      }
    },
    async handleAward(award, notify = true) {
      const reference = validateAward(award, this.identity.pubkey)
      if (!reference || this.collection.length >= MAX_COLLECTION) return
      const {issuer, identifier} = reference
      const key = `${issuer}:${identifier}`
      if (
        hasBadge(this.collection, {issuer, d: identifier}) ||
        this.collection.some(item => award.id && item.award.id === award.id) ||
        this.processingAwards.has(key)
      )
        return
      this.processingAwards.add(key)
      try {
        const badge = await this.pool.get(selectRelays([], this.knownRelays), {
          kinds: [30009],
          authors: [issuer],
          '#d': [identifier]
        })
        if (
          badge &&
          this.collection.length < MAX_COLLECTION &&
          !hasBadge(this.collection, {issuer, d: identifier})
        ) {
          this.collection.push({
            award,
            badge: badgeFromEvent(badge),
            expanded: false
          })
          if (notify) {
            this.$q.notify({
              type: 'positive',
              message: 'Badge awarded! It is now in your passport.'
            })
          }
          if (this.badge?.d === identifier && this.badge?.issuer === issuer) {
            this.tab = 'passport'
          }
        }
      } catch (error) {
        this.$q.notify({
          type: 'negative',
          message: error.message || 'Could not load a passport badge.'
        })
      } finally {
        this.processingAwards.delete(key)
      }
    }
  }
}
