<template id="page-badges">
  <div class="row q-col-gutter-md">
    <div class="col-12">
      <q-card>
        <q-card-section class="row items-center">
          <div class="text-h5">Badges</div>
          <q-space></q-space>
          <q-btn
            flat
            icon="key"
            label="Issuer key"
            @click="showSettings"
          ></q-btn>
          <q-btn
            color="primary"
            unelevated
            icon="add"
            label="New badge"
            @click="newBadge"
          ></q-btn>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section v-if="!settings.configured">
          <q-banner rounded class="bg-orange-1 text-orange-10">
            Configure one issuer nsec before the first public claim. Key
            rotation is not supported.
            <template v-slot:action>
              <q-btn flat label="Configure" @click="showSettings"></q-btn>
            </template>
          </q-banner>
        </q-card-section>
        <q-card-section v-else>
          <q-banner rounded class="bg-green-1 text-green-10">
            Issuer: <span v-text="settings.issuer_npub"></span>
          </q-banner>
        </q-card-section>
        <q-card-section>
          <q-input
            v-model="badgesTable.search"
            dense
            filled
            clearable
            label="Search badges"
          >
            <template v-slot:prepend>
              <q-icon name="search"></q-icon>
            </template>
          </q-input>
        </q-card-section>
        <q-card-section>
          <q-table
            dense
            flat
            :rows="badges"
            :columns="badgeColumns"
            row-key="id"
            v-model:pagination="badgesTable.pagination"
            :filter="badgesTable.search"
            :loading="loading"
          >
            <template v-slot:body-cell-image="props">
              <q-td :props="props">
                <q-avatar square size="48px">
                  <q-img
                    :src="props.row.image_url"
                    :alt="props.row.name"
                  ></q-img>
                </q-avatar>
              </q-td>
            </template>
            <template v-slot:body-cell-active="props">
              <q-td :props="props">
                <q-badge :color="props.row.is_active ? 'positive' : 'grey'">
                  <span
                    v-text="props.row.is_active ? 'Active' : 'Inactive'"
                  ></span>
                </q-badge>
              </q-td>
            </template>
            <template v-slot:body-cell-actions="props">
              <q-td :props="props">
                <q-btn
                  flat
                  round
                  dense
                  icon="qr_code_2"
                  color="primary"
                  @click="showQr(props.row)"
                >
                  <q-tooltip>Claim QR</q-tooltip>
                </q-btn>
                <q-btn
                  flat
                  round
                  dense
                  icon="people"
                  color="secondary"
                  @click="showClaims(props.row)"
                >
                  <q-tooltip>Claims</q-tooltip>
                </q-btn>
                <q-btn
                  flat
                  round
                  dense
                  icon="edit"
                  color="light-blue"
                  @click="editBadge(props.row)"
                ></q-btn>
                <q-btn
                  flat
                  round
                  dense
                  icon="delete"
                  color="negative"
                  @click="deleteBadge(props.row)"
                ></q-btn>
              </q-td>
            </template>
            <template v-slot:no-data>
              <div class="full-width row flex-center q-pa-lg text-grey">
                Create your first badge.
              </div>
            </template>
          </q-table>
        </q-card-section>
      </q-card>
    </div>

    <q-dialog v-model="settingsDialog.show" position="top">
      <q-card
        class="q-pa-lg q-pt-xl lnbits__dialog-card"
        style="width: 600px; max-width: 95vw"
      >
        <q-form @submit.prevent="saveSettings" class="q-gutter-md">
          <div class="text-h6">Issuer key</div>
          <div v-if="settings.configured" class="text-body2">
            This issuer is fixed to
            <span v-text="settings.issuer_npub"></span>. Key rotation is not
            supported.
          </div>
          <q-input
            v-else
            v-model.trim="settingsDialog.data.issuer_nsec"
            type="password"
            label="Issuer nsec"
            hint="Stored encrypted; never returned by the API."
            required
          ></q-input>
          <div class="row q-mt-lg">
            <q-btn
              v-if="!settings.configured"
              type="submit"
              color="primary"
              unelevated
              label="Save issuer key"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              label="Close"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="badgeDialog.show" position="top">
      <q-card
        class="q-pa-lg q-pt-xl lnbits__dialog-card"
        style="width: 600px; max-width: 95vw"
      >
        <q-form @submit.prevent="saveBadge" class="q-gutter-md">
          <div class="text-h6" v-text="badgeDialogTitle"></div>
          <q-input
            v-model.trim="badgeDialog.data.name"
            label="Name"
            required
            autofocus
          ></q-input>
          <div class="text-subtitle2">Badge image *</div>
          <q-btn-toggle
            v-model="badgeDialog.imageMode"
            spread
            no-caps
            unelevated
            toggle-color="primary"
            :options="imageOptions"
          ></q-btn-toggle>
          <q-input
            v-if="badgeDialog.imageMode === 'url'"
            v-model.trim="badgeDialog.data.image_url"
            filled
            dense
            type="url"
            label="Image URL"
            hint="Required. Use a public URL or upload an LNbits asset."
            :rules="[value => !!value || 'Image is required']"
          ></q-input>
          <div v-else class="row items-center q-gutter-sm">
            <input
              ref="badgeImageInput"
              type="file"
              accept="image/*"
              style="display: none"
              @change="uploadBadgeAsset"
            />
            <q-btn
              color="primary"
              outline
              icon="upload"
              label="Upload image"
              @click="$refs.badgeImageInput.click()"
            ></q-btn>
            <q-img
              v-if="badgeDialog.data.image_url"
              :src="badgeDialog.data.image_url"
              style="width: 64px; height: 64px"
              fit="cover"
            ></q-img>
            <div
              v-if="badgeDialog.data.image_url"
              class="text-caption ellipsis"
              style="max-width: 300px"
              v-text="badgeDialog.data.image_url"
            ></div>
          </div>
          <q-input
            v-model.trim="badgeDialog.data.description"
            label="Description"
            type="textarea"
          ></q-input>
          <q-toggle
            v-model="badgeDialog.data.is_active"
            label="Active"
          ></q-toggle>
          <q-expansion-item
            group="advanced"
            icon="settings"
            label="Advanced options"
          >
            <div class="q-gutter-md q-pt-md">
              <div class="text-subtitle2">Availability</div>
              <q-input
                v-model="badgeDialog.data.starts_at"
                filled
                dense
                type="datetime-local"
                label="Starts at"
              ></q-input>
              <q-input
                v-model="badgeDialog.data.ends_at"
                filled
                dense
                type="datetime-local"
                label="Ends at"
              ></q-input>
              <q-separator></q-separator>
              <q-toggle
                v-model="badgeDialog.data.location_enabled"
                label="Location-aware claiming"
              ></q-toggle>
              <div v-if="badgeDialog.data.location_enabled" class="q-gutter-md">
                <div class="text-caption">
                  Pick the claim location on a map, then set the allowed radius.
                </div>
                <q-btn
                  color="primary"
                  outline
                  icon="map"
                  label="Pick point on map"
                  @click="openLocationPicker"
                ></q-btn>
                <div class="row q-col-gutter-sm">
                  <q-input
                    class="col-12 col-sm-4"
                    v-model.number="badgeDialog.data.latitude"
                    filled
                    dense
                    type="number"
                    label="Latitude"
                  ></q-input>
                  <q-input
                    class="col-12 col-sm-4"
                    v-model.number="badgeDialog.data.longitude"
                    filled
                    dense
                    type="number"
                    label="Longitude"
                  ></q-input>
                  <q-input
                    class="col-12 col-sm-4"
                    v-model.number="badgeDialog.data.radius_meters"
                    filled
                    dense
                    type="number"
                    label="Radius (m)"
                    min="1"
                  ></q-input>
                </div>
              </div>
            </div>
          </q-expansion-item>
          <div class="row q-mt-lg">
            <q-btn
              type="submit"
              color="primary"
              unelevated
              label="Save"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              label="Cancel"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="mapDialog.show" position="top" @hide="closeMapDialog">
      <q-card
        class="q-pa-lg q-pt-xl lnbits__dialog-card"
        style="width: 900px; max-width: 95vw"
      >
        <div class="text-h6 q-mb-md">Pick badge location</div>
        <div id="badge-location-map" style="height: 420px"></div>
        <div class="row q-col-gutter-sm q-mt-md">
          <q-input
            class="col-12 col-sm-6"
            v-model.number="mapDialog.latitude"
            filled
            dense
            type="number"
            label="Latitude"
          ></q-input>
          <q-input
            class="col-12 col-sm-6"
            v-model.number="mapDialog.longitude"
            filled
            dense
            type="number"
            label="Longitude"
          ></q-input>
        </div>
        <div class="row q-mt-lg">
          <q-btn
            color="primary"
            unelevated
            label="Use this point"
            :disable="
              mapDialog.latitude === null || mapDialog.longitude === null
            "
            @click="applyMapLocation"
          ></q-btn>
          <q-btn v-close-popup flat color="grey" class="q-ml-auto">
            Cancel
          </q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="qrDialog.show" position="top">
      <q-card v-if="qrDialog.badge" class="q-pa-lg lnbits__dialog-card">
        <div class="text-h6 q-mb-md" v-text="qrDialog.badge.name"></div>
        <lnbits-qrcode
          :href="claimUrl(qrDialog.badge)"
          :value="claimUrl(qrDialog.badge)"
          class="q-mb-md"
        ></lnbits-qrcode>
        <q-input
          readonly
          :model-value="claimUrl(qrDialog.badge)"
          label="Claim API URL for the companion app"
        ></q-input>
        <div class="row q-mt-md">
          <q-btn
            color="primary"
            unelevated
            label="Copy link"
            @click="copyClaimUrl(qrDialog.badge)"
          ></q-btn>
          <q-btn
            flat
            color="grey"
            class="q-ml-auto"
            label="Close"
            v-close-popup
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="claimsDialog.show" position="top">
      <q-card
        v-if="claimsDialog.badge"
        class="q-pa-lg lnbits__dialog-card"
        style="width: 900px; max-width: 95vw"
      >
        <div class="row items-center q-mb-md">
          <div class="text-h6" v-text="claimsDialog.badge.name"></div>
          <q-space></q-space>
          <q-btn
            flat
            icon="file_download"
            label="CSV"
            @click="exportClaims(claimsDialog.badge)"
          ></q-btn>
        </div>
        <q-table
          flat
          :rows="claimsDialog.claims"
          :columns="claimColumns"
          row-key="id"
          :loading="claimsDialog.loading"
        ></q-table>
      </q-card>
    </q-dialog>
  </div>
</template>
