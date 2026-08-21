window.PageBadges = {
  template: '#page-badges',
  delimiters: ['${', '}'],
  data() {
    return {
      badges: [],
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
      badgeColumns: [
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
        data: {}
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
    claimUrl(badge) {
      return `${window.location.origin}/badges/api/v1/public/claims/${badge.claim_token}`
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
        latitude: null,
        longitude: null,
        radius_meters: null
      }
      this.badgeDialog.show = true
    },
    editBadge(badge) {
      this.badgeDialog.data = {...badge}
      this.badgeDialog.show = true
    },
    payload(data) {
      return {
        name: data.name,
        description: data.description || null,
        image_url: data.image_url || null,
        is_active: data.is_active,
        starts_at: data.starts_at || null,
        ends_at: data.ends_at || null,
        latitude: data.latitude === '' ? null : data.latitude,
        longitude: data.longitude === '' ? null : data.longitude,
        radius_meters: data.radius_meters === '' ? null : data.radius_meters
      }
    },
    async saveBadge() {
      try {
        const data = this.badgeDialog.data
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
    copyClaimUrl(badge) {
      LNbits.utils.copyText(this.claimUrl(badge), 'Claim API URL copied')
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
