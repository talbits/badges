<template id="page-badges">
  <div class="row q-col-gutter-md">
    <div class="col-12 col-md-8 col-lg-7 q-gutter-y-md">
    
      <q-card
        id="settingsCard"
      >
        <q-card-section
          class=""
        >
          <div class="row">
            <div class="col">
              <span class="text-h5">Badges</span>
              <q-btn
                @click="showSettingsDataForm()"
                v-if="true"
                unelevated
                split
                color="primary"
                icon="settings"
                class="float-right"
              >
              </q-btn>
            </div>
          </div>
        </q-card-section>
      </q-card>
    

      <div class="q-mt-lg">
        <span class="text-h5">Owner Data</span>
      </div>
      <q-card
        id="ownerDataCard"
        class="q-mt-xs"
      >
        <q-card-section
          class=""
        >
          <div class="row items-center no-wrap q-mb-md">
            <div class="col">
              <q-input
                :label="$t('search')"
                dense
                class="q-pr-xl"
                v-model="ownerDataTable.search"
              >
                <template v-slot:before>
                  <q-icon name="search"> </q-icon>
                </template>
                <template v-slot:append>
                  <q-icon
                    v-if="ownerDataTable.search !== ''"
                    name="close"
                    @click="ownerDataTable.search = ''"
                    class="cursor-pointer"
                  >
                  </q-icon>
                </template>
              </q-input>
            </div>
            <div class="col-auto">
              
              <q-btn
                @click="showNewOwnerDataForm()"
                unelevated
                split
                color="primary"
              >
                New Owner Data
              </q-btn>
              
              <q-btn
                flat
                color="grey"
                icon="file_download"
                @click="exportOwnerDataCSV"
                >CSV</q-btn
              >
            </div>
          </div>
          <q-table
            dense
            flat
            :rows="ownerDataList"
            row-key="id"
            :columns="ownerDataTable.columns"
            v-model:pagination="ownerDataTable.pagination"
            :loading="ownerDataTable.loading"
            @request="getOwnerData"
          >
            <template v-slot:header="props">
              <q-tr :props="props">
                <q-th auto-width></q-th>
                <q-th v-for="col in props.cols" :key="col.name" :props="props">
                  ${ col.label }
                </q-th>
              </q-tr>
            </template>

            <template v-slot:body="props">
              <q-tr :props="props">
                <q-td auto-width>
                  
                  <q-btn
                    flat
                    dense
                    size="xs"
                    icon="launch"
                    color="primary"
                    type="a"
                    :href="'/badges/' + props.row.id"
                    target="_blank"
                    class="q-mr-sm"
                    ><q-tooltip>Open public page</q-tooltip></q-btn
                  >
                   
                  <q-btn
                    flat
                    dense
                    size="xs"
                    @click="showEditOwnerDataForm(props.row)"
                    icon="edit"
                    color="light-blue"
                    class="q-mr-sm"
                  >
                    <q-tooltip> Edit </q-tooltip>
                  </q-btn>
                  
                  <q-btn
                    flat
                    dense
                    size="xs"
                    @click="deleteOwnerData(props.row.id)"
                    icon="cancel"
                    color="pink"
                    class="q-mr-sm"
                  >
                    <q-tooltip> Delete </q-tooltip>
                  </q-btn>
                </q-td>

                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                  <div v-if="col.field == 'updated_at'">
                    <span v-text="dateFromNow(col.value)"> </span>
                  </div>
                  <div v-else>${ col.value }</div>
                </q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card-section>
      </q-card>

      <div class="q-mt-lg">
        <span class="text-h5">Client Data</span>
      </div>
      <q-card
        id="clientDataCard"
        class="q-mt-xs"
      >
        <q-card-section
          class=""
        >
          <div class="row items-center no-wrap q-mb-md">
            <div class="col">
              <q-input
                :label="$t('search')"
                dense
                class="q-pr-xl"
                v-model="clientDataTable.search"
              >
                <template v-slot:before>
                  <q-icon name="search"> </q-icon>
                </template>
                <template v-slot:append>
                  <q-icon
                    v-if="clientDataTable.search !== ''"
                    name="close"
                    @click="clientDataTable.search = ''"
                    class="cursor-pointer"
                  >
                  </q-icon>
                </template>
              </q-input>
            </div>
            <div class="col-auto">
              <q-select
                filled
                dense
                v-model="clientDataFormDialog.ownerData"
                :options="[
                  {label: 'All Owner Data', value: ''},
                  ...ownerDataList.map(x => ({
                    label: x.name || x.id,
                    value: x.id
                  }))
                ]"
                label="Owner Data"
                class="q-mb-md"
              ></q-select>
            </div>
            <div class="col-auto">
              <q-btn
                flat
                color="grey"
                icon="file_download"
                class="q-mb-md"
                @click="exportClientDataCSV"
                >CSV</q-btn
              >
            </div>
          </div>
          <q-table
            dense
            flat
            :rows="clientDataList"
            row-key="id"
            :columns="clientDataTable.columns"
            v-model:pagination="clientDataTable.pagination"
            :loading="clientDataTable.loading"
            @request="getClientData"
          >
            <template v-slot:header="props">
              <q-tr :props="props">
                <q-th auto-width></q-th>
                <q-th v-for="col in props.cols" :key="col.name" :props="props">
                  ${ col.label }
                </q-th>
              </q-tr>
            </template>

            <template v-slot:body="props">
              <q-tr :props="props">
                <q-td auto-width>
                  
                  <q-btn
                    flat
                    dense
                    size="xs"
                    @click="showEditClientDataForm(props.row)"
                    icon="edit"
                    color="light-blue"
                    class="q-mr-sm"
                  >
                    <q-tooltip> Edit </q-tooltip>
                  </q-btn>
                  
                  <q-btn
                    flat
                    dense
                    size="xs"
                    @click="deleteClientData(props.row.id)"
                    icon="cancel"
                    color="pink"
                    class="q-mr-sm"
                  >
                    <q-tooltip> Delete </q-tooltip>
                  </q-btn>
                </q-td>

                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                  <div v-if="col.field == 'updated_at'">
                    <span v-text="dateFromNow(col.value)"> </span>
                  </div>
                  <div v-else>${ col.value }</div>
                </q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card-section>
      </q-card>
    </div>
    
    <div class="col-12 col-md-4 col-lg-5 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <h6 class="text-subtitle1 q-my-none">Badges</h6>
          <p></p>
        </q-card-section>
        <q-card-section class="q-pa-none">
          <q-separator></q-separator>
          <q-list>
            <!-- {% include "badges/_api_docs.html" %} -->
            <q-separator></q-separator>
            <q-expansion-item group="extras" icon="info" label="More info">
              <q-card>
                <q-card-section>
                  <p>Some more info about Badges.</p>
                  <small
                    >Created by
                    <a
                      class="text-secondary"
                      href="https://github.com/lnbits"
                      target="_blank"
                      >LNbits extension builder</a
                    >.</small
                  >
                </q-card-section>
              </q-card>
            </q-expansion-item>
          </q-list>
        </q-card-section>
      </q-card>
    </div>
    

    <!--/////////////////////////////////////////////////-->
    <!--//////////////FORM DIALOG////////////////////////-->
    <!--/////////////////////////////////////////////////-->

    <q-dialog v-model="settingsFormDialog.show" position="top">
      <q-card
        v-if="settingsFormDialog.show"
        class="q-pa-lg q-pt-xl lnbits__dialog-card q-col-gutter-md"
      >
        <span class="text-h5">Settings</span>
       
<q-input
  filled
  dense
  v-model.trim="settingsFormDialog.data.name"
  label="Name"
  hint="  (optional)"
></q-input>
 
        <div class="row q-mt-lg">
          <q-btn
            @click="updateSettings"
            unelevated
            color="primary"
            type="submit"
            >Update</q-btn
          >
          <q-btn v-close-popup flat color="grey" class="q-ml-auto"
            >Cancel</q-btn
          >
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="ownerDataFormDialog.show" position="top">
      <q-card
        v-if="ownerDataFormDialog.show"
        class="q-pa-lg q-pt-md lnbits__dialog-card q-col-gutter-md"
      >
        <span class="text-h5">Owner Data</span>

       
<q-input
  filled
  dense
  v-model.trim="ownerDataFormDialog.data.name"
  label="Name"
  hint="  (optional)"
></q-input>
 
        <div class="row q-mt-lg">
          <q-btn @click="saveOwnerData" unelevated color="primary">
            <span v-if="ownerDataFormDialog.data.id">Update</span>
            <span v-else>Create</span>
          </q-btn>
          <q-btn v-close-popup flat color="grey" class="q-ml-auto"
            >Cancel</q-btn
          >
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="clientDataFormDialog.show" position="top">
      <q-card
        v-if="clientDataFormDialog.show"
        class="q-pa-lg q-pt-md lnbits__dialog-card q-col-gutter-md"
      >
        <span class="text-h5">Client Data</span>

       
<q-input
  filled
  dense
  v-model.trim="clientDataFormDialog.data.name"
  label="Name"
  hint="  (optional)"
></q-input>
 
        <div class="row q-mt-lg">
          <q-btn @click="saveClientData" unelevated color="primary">
            <span v-if="clientDataFormDialog.data.id">Update</span>
            <span v-else>Create</span>
          </q-btn>
          <q-btn v-close-popup flat color="grey" class="q-ml-auto"
            >Cancel</q-btn
          >
        </div>
      </q-card>
    </q-dialog>
  </div>
</template>