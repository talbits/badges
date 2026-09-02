<template id="page-badges-claim">
  <div class="row justify-center">
    <div class="col-12 col-md-9 col-lg-8 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <div class="text-h5">Badges</div>
          <div class="text-subtitle2 text-grey-7">
            Scan a badge QR code, claim it, and keep your Nostr passport.
          </div>
        </q-card-section>
        <q-card-section>
          <q-tabs
            v-model="tab"
            class="text-primary"
            inline-label
            align="justify"
          >
            <q-tab name="scan" icon="qr_code_scanner" label="Scan"></q-tab>
            <q-tab
              name="passport"
              icon="collections_bookmark"
              label="Passport"
            ></q-tab>
            <q-tab
              name="identity"
              icon="account_circle"
              label="Identity"
            ></q-tab>
          </q-tabs>
        </q-card-section>
        <q-separator></q-separator>
        <q-tab-panels v-model="tab" animated>
          <q-tab-panel name="scan" class="q-gutter-y-md">
            <q-btn
              color="primary"
              unelevated
              icon="qr_code_scanner"
              label="Scan badge QR code"
              @click="startScan"
            ></q-btn>
            <q-input
              v-model.trim="naddrInput"
              outlined
              clearable
              label="Or paste a Nostr badge address"
              hint="Supports nostr:naddr… and nostr://naddr…"
              @keyup.enter="loadBadge(naddrInput)"
            >
              <template v-slot:append>
                <q-btn
                  flat
                  round
                  icon="download"
                  @click="loadBadge(naddrInput)"
                ></q-btn>
              </template>
            </q-input>
            <q-inner-loading :showing="loadingBadge">
              <q-spinner-gears size="40px" color="primary"></q-spinner-gears>
            </q-inner-loading>
            <q-card v-if="badge" class="q-my-md" flat bordered>
              <q-img
                v-if="badge.image"
                :src="badge.image"
                height="45vh"
                fit="contain"
              ></q-img>
              <q-card-section>
                <div class="text-h6">{{ badge.name || badge.content }}</div>
                <div v-if="badge.description" class="q-mt-sm">
                  {{ badge.description }}
                </div>
                <q-banner
                  v-if="needsLocation"
                  rounded
                  class="bg-primary text-white q-mt-md"
                >
                  This badge requests your browser location to check that you
                  are at the event. It is sent only to the badge issuer.
                </q-banner>
              </q-card-section>
              <q-card-actions>
                <q-btn
                  color="primary"
                  unelevated
                  :label="
                    alreadyClaimed
                      ? 'Already claimed'
                      : claiming
                        ? 'Claiming…'
                        : 'Claim badge'
                  "
                  :disable="claiming || !identity.pubkey || alreadyClaimed"
                  @click="claimBadge"
                ></q-btn>
                <q-btn
                  v-if="!identity.pubkey"
                  flat
                  color="primary"
                  label="Create identity first"
                  @click="tab = 'identity'"
                ></q-btn>
              </q-card-actions>
            </q-card>
          </q-tab-panel>

          <q-tab-panel name="passport" class="relative-position">
            <div v-if="!identity.pubkey" class="text-grey-7">
              Create a local identity to start your passport.
            </div>
            <q-inner-loading :showing="collectionLoading">
              <q-spinner-gears size="40px" color="primary"></q-spinner-gears>
            </q-inner-loading>
            <div
              v-if="!collection.length && !collectionLoading"
              class="text-grey-7"
            >
              Your claimed badges will appear here.
            </div>
            <div class="row q-col-gutter-md">
              <div
                v-for="item in collection"
                :key="item.award.id"
                class="col-12 col-sm-4 col-md-3"
              >
                <q-card bordered>
                  <q-img
                    v-if="item.badge.image"
                    :src="item.badge.image"
                    ratio="1"
                  ></q-img>
                  <q-card-section>
                    <div class="text-h6 ellipsis">
                      {{ item.badge.name || item.badge.content }}
                    </div>
                  </q-card-section>
                  <q-card-actions
                    v-if="item.badge.description"
                    class="q-pt-none"
                  >
                    <q-space></q-space>
                    <q-btn
                      flat
                      round
                      dense
                      :icon="
                        item.expanded
                          ? 'keyboard_arrow_up'
                          : 'keyboard_arrow_down'
                      "
                      :aria-label="
                        item.expanded
                          ? 'Hide badge description'
                          : 'Show badge description'
                      "
                      @click="item.expanded = !item.expanded"
                    ></q-btn>
                  </q-card-actions>
                  <q-slide-transition v-if="item.badge.description">
                    <div v-show="item.expanded">
                      <q-separator></q-separator>
                      <q-card-section class="text-body2">
                        <div class="ellipsis-3-lines">
                          {{ item.badge.description }}
                        </div>
                      </q-card-section>
                    </div>
                  </q-slide-transition>
                </q-card>
              </div>
            </div>
          </q-tab-panel>

          <q-tab-panel name="identity" class="q-gutter-y-md">
            <p
              v-if="identity.signerBacked"
              class="text-caption text-grey-7 q-mb-none"
            >
              This passport uses your Nostr browser extension. Its private key
              remains in the extension and is never stored by this page.
            </p>
            <p
              v-else-if="identity.pubkey"
              class="text-caption text-grey-7 q-mb-none"
            >
              Your identity is kept in this browser only. Save your nsec before
              clearing browser data; anyone with it can sign as you.
            </p>
            <q-btn
              v-if="hasNip07 && !identity.pubkey"
              outline
              color="primary"
              icon="extension"
              label="Use Nostr extension"
              @click="useSignerIdentity"
            ></q-btn>
            <div v-if="identity.pubkey" class="column q-gutter-y-md">
              <q-input
                :model-value="shortKey(identity.npub)"
                readonly
                outlined
                label="Passport npub"
              >
                <template v-slot:append>
                  <q-btn
                    flat
                    round
                    icon="content_copy"
                    aria-label="Copy passport npub"
                    @click="
                      utils.copyText(identity.npub, 'Passport npub copied')
                    "
                  ></q-btn>
                </template>
              </q-input>
              <q-input
                v-if="!identity.signerBacked"
                :model-value="
                  showNsec ? identity.nsec : shortKey(identity.nsec)
                "
                readonly
                outlined
                type="text"
                label="Passport nsec"
              >
                <template v-slot:append>
                  <q-btn
                    flat
                    round
                    :icon="showNsec ? 'visibility_off' : 'visibility'"
                    aria-label="Toggle passport nsec visibility"
                    @click="showNsec = !showNsec"
                  ></q-btn>
                  <q-btn
                    flat
                    round
                    icon="content_copy"
                    aria-label="Copy passport nsec"
                    @click="
                      utils.copyText(identity.nsec, 'Passport nsec copied')
                    "
                  ></q-btn>
                </template>
              </q-input>
              <q-btn
                flat
                color="negative"
                icon="delete"
                label="Forget this identity"
                @click="forgetIdentity"
              ></q-btn>
            </div>
            <div v-else class="q-gutter-y-md">
              <q-btn
                color="primary"
                unelevated
                icon="add"
                label="Generate local identity"
                @click="generateIdentity"
              ></q-btn>
              <q-input
                v-model.trim="identityInput"
                outlined
                type="password"
                label="Import nsec or 64-character private key"
                @keyup.enter="importIdentity"
              >
                <template v-slot:append>
                  <q-btn
                    flat
                    round
                    icon="login"
                    @click="importIdentity"
                  ></q-btn>
                </template>
              </q-input>
            </div>
          </q-tab-panel>
        </q-tab-panels>
      </q-card>
    </div>
  </div>
</template>
