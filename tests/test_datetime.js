const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const source = fs.readFileSync('static/index.js', 'utf8')
const context = {window: {}}
vm.runInNewContext(source, context)
const methods = context.window.PageBadges.methods
const {toDatetimeLocal, toUtcIso} = methods

const local = '2026-08-26T08:34'
const utc = toUtcIso(local)
assert.equal(utc, '2026-08-26T12:34:00.000Z')
assert.equal(toDatetimeLocal(utc), local)
const converted = methods.payload({starts_at: local, ends_at: ''})
assert.equal(converted.starts_at, utc)
assert.equal(converted.ends_at, null)
assert.equal(methods.payload({starts_at: '', ends_at: null}).starts_at, null)
assert.equal(toDatetimeLocal('2026-08-26T12:34:00'), '2026-08-26T12:34')
