let leafletPromise

const IMAGE_OPTIONS = [
  {label: 'URL', value: 'url', icon: 'link'},
  {label: 'LNbits asset', value: 'asset', icon: 'upload_file'}
]
const ASSET_COLUMNS = [
  {name: 'name', label: 'Name', field: 'name'},
  {name: 'created_at', label: 'Created', field: 'created_at'}
]
const BADGE_COLUMNS = [
  {name: 'image', label: 'Image', field: 'image_url', align: 'left'},
  {name: 'name', label: 'Name', field: 'name', align: 'left'},
  {name: 'active', label: 'Active', field: 'is_active', align: 'left'},
  {name: 'actions', label: '', field: 'actions', align: 'right'}
]
const CLAIM_COLUMNS = [
  {
    name: 'passport_pubkey',
    label: 'Passport public key',
    field: 'passport_pubkey',
    align: 'left'
  },
  {name: 'claimed_at', label: 'Claimed', field: 'claimed_at', align: 'left'},
  {
    name: 'location_verified',
    label: 'Location',
    field: 'location_verified',
    align: 'left'
  },
  {
    name: 'award_event_id',
    label: 'Award event',
    field: 'award_event_id',
    align: 'left'
  }
]

function loadLeaflet() {
  if (window.L) {
    return Promise.resolve(window.L)
  }
  if (leafletPromise) {
    return leafletPromise
  }
  leafletPromise = new Promise((resolve, reject) => {
    const css = document.createElement('link')
    css.rel = 'stylesheet'
    css.href = '/badges/static/vendor/leaflet/leaflet.css'
    document.head.appendChild(css)

    const script = document.createElement('script')
    script.src = '/badges/static/vendor/leaflet/leaflet.js'
    script.onload = () => resolve(window.L)
    script.onerror = reject
    document.head.appendChild(script)
  })
  return leafletPromise
}

window.PageBadges = {
  template: '#page-badges',
  delimiters: ['${', '}'],
  data() {
    return {
      badges: [],
      badgesTable: {
        search: '',
        pagination: {rowsPerPage: 10}
      },
      loading: false,
      settings: {
        configured: false,
        issuer_pubkey: null,
        issuer_npub: null
      },
      relayUrls: [],
      settingsDialog: {
        show: false,
        data: {issuer_nsec: ''}
      },
      assets: [],
      assetsTable: {
        loading: false,
        search: '',
        columns: ASSET_COLUMNS,
        pagination: {rowsPerPage: 6, page: 1}
      },
      assetsDialog: {show: false},
      badgeDialog: {
        show: false,
        data: {},
        imageMode: 'url'
      },
      mapDialog: {
        show: false,
        latitude: null,
        longitude: null,
        map: null,
        marker: null
      },
      qrDialog: {
        show: false,
        badge: null
      },
      claimsDialog: {
        show: false,
        badge: null,
        claims: [],
        loading: false
      }
    }
  },
  computed: {
    imageOptions: () => IMAGE_OPTIONS,
    badgeColumns: () => BADGE_COLUMNS,
    claimColumns: () => CLAIM_COLUMNS,
    badgeDialogTitle() {
      return this.badgeDialog.data.id ? 'Edit badge' : 'New badge'
    }
  },
  watch: {
    'assetsTable.search'() {
      if (this.assetsDialog.show) this.getBadgeAssets()
    }
  },
  methods: {
    badgeAddress(badge) {
      if (this.relayUrls.length && window.NostrTools?.nip19?.naddrEncode) {
        return window.NostrTools.nip19.naddrEncode({
          identifier: badge.id,
          pubkey: badge.issuer_pubkey,
          kind: 30009,
          relays: this.relayUrls
        })
      }
      return badge.naddr || `30009:${badge.issuer_pubkey}:${badge.id}`
    },
    async showSettings() {
      await this.getSettings()
      this.settingsDialog.data = {issuer_nsec: ''}
      this.settingsDialog.show = true
    },
    async getSettings() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/badges/api/v1/settings',
          null
        )
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async saveSettings() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/badges/api/v1/settings',
          null,
          this.settingsDialog.data
        )
        this.settings = data
        this.settingsDialog.show = false
        this.settingsDialog.data = {issuer_nsec: ''}
        this.$q.notify({type: 'positive', message: 'Issuer key configured.'})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    newBadge() {
      this.badgeDialog.data = {
        name: '',
        description: '',
        image_url: '',
        is_active: true,
        starts_at: null,
        ends_at: null,
        location_enabled: false,
        latitude: null,
        longitude: null,
        radius_meters: 100
      }
      this.badgeDialog.imageMode = 'url'
      this.badgeDialog.show = true
    },
    editBadge(badge) {
      this.badgeDialog.data = {
        ...badge,
        starts_at: this.toDatetimeLocal(badge.starts_at),
        ends_at: this.toDatetimeLocal(badge.ends_at),
        location_enabled:
          badge.latitude !== null &&
          badge.longitude !== null &&
          badge.radius_meters !== null
      }
      this.badgeDialog.imageMode = badge.image_url.includes('/api/v1/assets/')
        ? 'asset'
        : 'url'
      this.badgeDialog.show = true
    },
    toDatetimeLocal(value) {
      if (!value || typeof value !== 'string') {
        return null
      }
      if (!/[zZ]|[+-]\d\d:\d\d$/.test(value)) {
        return value.slice(0, 16)
      }
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) {
        return value
      }
      return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16)
    },
    toUtcIso(value) {
      return value ? new Date(value).toISOString() : null
    },
    payload(data) {
      return {
        name: data.name,
        description: data.description || null,
        image_url: data.image_url,
        is_active: data.is_active,
        starts_at: this.toUtcIso(data.starts_at),
        ends_at: this.toUtcIso(data.ends_at),
        latitude: data.location_enabled ? data.latitude : null,
        longitude: data.location_enabled ? data.longitude : null,
        radius_meters: data.location_enabled ? data.radius_meters : null
      }
    },
    async uploadBadgeAsset(event) {
      const file = event.target.files[0]
      event.target.value = null
      if (!file) {
        return
      }
      const formData = new FormData()
      formData.append('file', file)
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/assets?public_asset=true',
          null,
          formData,
          {headers: {'Content-Type': 'multipart/form-data'}}
        )
        this.badgeDialog.data.image_url = `${window.location.origin}/api/v1/assets/${data.id}/data`
        this.$q.notify({type: 'positive', message: 'Badge image uploaded.'})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async showAssetPicker() {
      this.assetsDialog.show = true
      await this.getBadgeAssets()
    },
    async getBadgeAssets(props) {
      this.assetsTable.loading = true
      try {
        const params = LNbits.utils.prepareFilterQuery(this.assetsTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/assets/paginated?${params}`,
          null
        )
        this.assets = data.data
        this.assetsTable.pagination.rowsNumber = data.total
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.assetsTable.loading = false
      }
    },
    selectBadgeAsset(asset) {
      if (!asset.mime_type?.startsWith('image/')) {
        this.$q.notify({type: 'warning', message: 'Choose an image asset.'})
        return
      }
      if (!asset.is_public) {
        LNbits.utils
          .confirmDialog(
            'This image is private. Make it public so badge claimants can load it?'
          )
          .onOk(() => this.publishBadgeAsset(asset))
        return
      }
      this.useBadgeAsset(asset)
    },
    async publishBadgeAsset(asset) {
      try {
        await LNbits.api.request('PUT', `/api/v1/assets/${asset.id}`, null, {
          is_public: true
        })
        asset.is_public = true
        this.useBadgeAsset(asset)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    useBadgeAsset(asset) {
      this.badgeDialog.data.image_url = `${window.location.origin}/api/v1/assets/${asset.id}/data`
      this.assetsDialog.show = false
    },
    async openLocationPicker() {
      this.mapDialog.latitude = this.badgeDialog.data.latitude
      this.mapDialog.longitude = this.badgeDialog.data.longitude
      this.mapDialog.show = true
      await this.$nextTick()
      try {
        await loadLeaflet()
        this.initMap()
      } catch (error) {
        this.$q.notify({
          type: 'negative',
          message: 'The map could not be loaded. Enter coordinates manually.'
        })
      }
    },
    initMap() {
      const element = document.getElementById('badge-location-map')
      if (!element || !window.L) {
        return
      }
      if (this.mapDialog.map) {
        this.mapDialog.map.remove()
      }
      const latitude = Number(this.mapDialog.latitude) || 0
      const longitude = Number(this.mapDialog.longitude) || 0
      const map = window.L.map(element).setView(
        [latitude, longitude],
        latitude || longitude ? 14 : 2
      )
      window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map)
      map.on('click', event => {
        this.mapDialog.latitude = Number(event.latlng.lat.toFixed(6))
        this.mapDialog.longitude = Number(event.latlng.lng.toFixed(6))
        this.setMapMarker()
      })
      this.mapDialog.map = map
      if (
        this.mapDialog.latitude !== null &&
        this.mapDialog.longitude !== null
      ) {
        this.setMapMarker()
      }
      window.setTimeout(() => map.invalidateSize(), 0)
    },
    setMapMarker() {
      const {map, marker, latitude, longitude} = this.mapDialog
      if (!map || latitude === null || longitude === null) {
        return
      }
      if (marker) {
        marker.setLatLng([latitude, longitude])
      } else {
        this.mapDialog.marker = window.L.marker([latitude, longitude]).addTo(
          map
        )
      }
    },
    applyMapLocation() {
      this.badgeDialog.data.latitude = this.mapDialog.latitude
      this.badgeDialog.data.longitude = this.mapDialog.longitude
      this.mapDialog.show = false
    },
    closeMapDialog() {
      if (this.mapDialog.map) {
        this.mapDialog.map.remove()
      }
      this.mapDialog.map = null
      this.mapDialog.marker = null
    },
    async saveBadge() {
      try {
        const data = this.badgeDialog.data
        if (!data.image_url) {
          this.$q.notify({type: 'warning', message: 'Badge image is required.'})
          return
        }
        if (
          data.location_enabled &&
          (data.latitude === null ||
            data.latitude === '' ||
            data.longitude === null ||
            data.longitude === '' ||
            data.radius_meters === null ||
            data.radius_meters === '')
        ) {
          this.$q.notify({
            type: 'warning',
            message: 'Choose a map point and set a location radius.'
          })
          return
        }
        const method = data.id ? 'PUT' : 'POST'
        const url = data.id
          ? `/badges/api/v1/badges/${data.id}`
          : '/badges/api/v1/badges'
        await LNbits.api.request(method, url, null, this.payload(data))
        this.badgeDialog.show = false
        await this.getBadges()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async getBadges() {
      this.loading = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/badges/api/v1/badges',
          null
        )
        this.badges = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.loading = false
      }
    },
    async deleteBadge(badge) {
      await LNbits.utils
        .confirmDialog(`Delete badge "${badge.name}"?`)
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              `/badges/api/v1/badges/${badge.id}`,
              null
            )
            await this.getBadges()
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    showQr(badge) {
      this.qrDialog.badge = badge
      this.qrDialog.show = true
    },
    async showClaims(badge) {
      this.claimsDialog.badge = badge
      this.claimsDialog.claims = []
      this.claimsDialog.show = true
      this.claimsDialog.loading = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/badges/api/v1/badges/${badge.id}/claims`,
          null
        )
        this.claimsDialog.claims = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.claimsDialog.loading = false
      }
    },
    exportClaims(badge) {
      window.open(`/badges/api/v1/badges/${badge.id}/claims.csv`, '_blank')
    }
  },
  async created() {
    const wallet = this.g.wallet || this.g.user?.wallets?.[0]
    if (wallet?.adminkey) {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/nostrclient/api/v1/relays/urls',
          wallet.adminkey
        )
        this.relayUrls = Array.isArray(data) ? data : []
      } catch (error) {
        // Badge responses still provide a usable naddr when relay discovery fails.
      }
    }
    await Promise.all([this.getSettings(), this.getBadges()])
  }
}
