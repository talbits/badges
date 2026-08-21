let leafletPromise

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
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(css)

    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
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
      settingsDialog: {
        show: false,
        data: {issuer_nsec: ''}
      },
      imageOptions: [
        {label: 'URL', value: 'url', icon: 'link'},
        {label: 'LNbits asset', value: 'asset', icon: 'upload_file'}
      ],
      badgeColumns: [
        {name: 'image', label: 'Image', field: 'image_url', align: 'left'},
        {name: 'name', label: 'Name', field: 'name', align: 'left'},
        {name: 'active', label: 'Active', field: 'is_active', align: 'left'},
        {name: 'actions', label: '', field: 'actions', align: 'right'}
      ],
      claimColumns: [
        {
          name: 'passport_pubkey',
          label: 'Passport public key',
          field: 'passport_pubkey',
          align: 'left'
        },
        {
          name: 'claimed_at',
          label: 'Claimed',
          field: 'claimed_at',
          align: 'left'
        },
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
      ],
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
    badgeDialogTitle() {
      return this.badgeDialog.data.id ? 'Edit badge' : 'New badge'
    }
  },
  methods: {
    badgeAddress(badge) {
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
        image_asset_id: null,
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
    payload(data) {
      return {
        name: data.name,
        description: data.description || null,
        image_url: data.image_url,
        is_active: data.is_active,
        starts_at: data.starts_at || null,
        ends_at: data.ends_at || null,
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
        this.badgeDialog.data.image_asset_id = data.id
        this.$q.notify({type: 'positive', message: 'Badge image uploaded.'})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
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
    copyBadgeAddress(badge) {
      LNbits.utils.copyText(this.badgeAddress(badge), 'Nostr address copied')
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
  created() {
    this.getSettings()
    this.getBadges()
  }
}
