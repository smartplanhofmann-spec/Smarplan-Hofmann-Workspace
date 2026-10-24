// Entirely synthetic; this fixture has no network or mailbox capability.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, 'SmartplanGmail.gs'), 'utf8');
const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, 'appsscript.json'), 'utf8'));

function fixture() {
  const properties = new Map([
    ['SMARTPLAN_INTAKE_URL', 'https://office.example.test/api/v1/intake/gmail'],
    ['SMARTPLAN_IMPORT_TOKEN', 'SPIN_' + 'A'.repeat(43)],
    ['SMARTPLAN_SOURCE_ACCOUNT', 'office@example.test'], ['SMARTPLAN_BATCH_SIZE', '2']
  ]);
  const store = {getProperty: key => properties.get(key) || null,
    setProperty: (key, value) => properties.set(key, value), deleteProperty: key => properties.delete(key)};
  const delivered = new Map(), requests = [], listings = [], logs = [], fetched = [], readErrors = new Map();
  let failSecond = true;
  let profile = 'office@example.test';
  let labelPresent = true;
  const text = value => Buffer.from(value).toString('base64url');
  const messages = {
    a1: {id: 'a1', labelIds: ['ONLY_LABEL'], internalDate: '1792828800000', payload: {
      mimeType: 'multipart/mixed', headers: [{name: 'Subject', value: 'Synthetic Aufmaß'}, {name: 'From', value: 'Synthetic Sender <sender@example.test>'}],
      parts: [{mimeType: 'text/plain', body: {data: text('Rückruf bitte.\nFiktiver Text.')}},
              {mimeType: 'text/plain', filename: 'private.txt', body: {attachmentId: 'never-fetch', data: text('SECRET ATTACHMENT')}}]}},
    a2: {id: 'a2', labelIds: ['ONLY_LABEL'], internalDate: '1792828801000', payload: {mimeType: 'text/plain',
      headers: [{name: 'Subject', value: 'Second synthetic'}], body: {data: text('Second synthetic body')}}},
    a3: {id: 'a3', labelIds: ['ONLY_LABEL'], internalDate: '1792828802000', payload: {mimeType: 'text/html',
      headers: [], body: {data: text('<script>never execute</script><img src="https://external.invalid/x">')}}}
  };
  let context;
  function restart() {
    context = vm.createContext({console: {log: item => logs.push(item)},
    PropertiesService: {getScriptProperties: () => store},
    LockService: {getScriptLock: () => ({tryLock: () => true, releaseLock: () => {}})},
    Gmail: {Users: {getProfile: () => ({emailAddress: profile}),
      Labels: {list: () => ({labels: labelPresent ? [{id: 'ONLY_LABEL', name: 'Smartplan-Anfragen'}] : []})},
      Messages: {list: (_account, options) => {
        listings.push(options); assert.equal(options.labelIds.length, 1); assert.equal(options.labelIds[0], 'ONLY_LABEL');
        assert.equal(options.includeSpamTrash, false); assert.ok(options.maxResults <= 20);
        return options.pageToken ? {messages: [{id: 'a3'}]} : {messages: [{id: 'a1'}, {id: 'a2'}], nextPageToken: 'NEXT'};
      }, get: (_account, id, options) => {
        fetched.push(id); assert.equal(options.format, 'full');
        if (readErrors.has(id)) throw readErrors.get(id);
        return messages[id];
      }}
    }},
    Utilities: {base64DecodeWebSafe: value => Buffer.from(value, 'base64url'),
      newBlob: bytes => ({getDataAsString: charset => Buffer.from(bytes).toString(/^utf-?8$/i.test(charset) ? 'utf8' : 'latin1')})},
    UrlFetchApp: {fetch: (url, options) => {
      assert.equal(url, properties.get('SMARTPLAN_INTAKE_URL'));
      assert.equal(options.method, 'post'); assert.equal(options.followRedirects, false);
      assert.equal(options.validateHttpsCertificates, true);
      assert.equal(options.headers.Authorization, 'Bearer ' + properties.get('SMARTPLAN_IMPORT_TOKEN'));
      const envelope = JSON.parse(options.payload); requests.push(envelope);
      assert.equal(envelope.source_account, 'office@example.test');
      assert.ok(!options.payload.includes('SECRET ATTACHMENT'));
      assert.ok(!options.payload.includes('SPIN_'));
      const fingerprint = JSON.stringify(envelope);
      if (delivered.has(envelope.source_id)) assert.equal(delivered.get(envelope.source_id), fingerprint);
      else delivered.set(envelope.source_id, fingerprint);
      let code = 201;
      if (envelope.source_id === 'a2' && failSecond) {failSecond = false; code = 503;}
      return {getResponseCode: () => code, getContentText: () => JSON.stringify({
        id: envelope.source_id.padStart(32, '0'), status: 'received', ingested_at: '2026-10-24T12:00:00+00:00'})};
    }}
    });
    vm.runInContext(script, context, {timeout: 1000});
  }
  restart();
  return {get context() {return context;}, restart, properties, delivered, requests, listings, logs, fetched, messages, readErrors,
          profile: value => {profile = value;}, label: value => {labelPresent = value;}};
}

// 1. Exact minimum scopes: no send/modify/read-mark or settings scope.
assert.deepEqual(manifest.oauthScopes.sort(), [
  'https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/script.external_request'].sort());

// 2. A lost receipt retains cursor and retries idempotently, then pages onward.
const f = fixture();
assert.throws(() => f.context.smartplanGmailImport(), /HTTP 503/);
assert.equal(JSON.parse(f.properties.get('SMARTPLAN_PENDING')).offset, 1);
assert.equal(f.delivered.size, 2);
f.context.smartplanGmailImport();
assert.equal(f.delivered.size, 2);
assert.equal(f.properties.get('SMARTPLAN_PAGE_TOKEN'), 'NEXT');
f.context.smartplanGmailImport();
assert.equal(f.delivered.size, 3);
assert.equal(f.properties.has('SMARTPLAN_PENDING'), false);
assert.equal(f.properties.has('SMARTPLAN_PAGE_TOKEN'), false);
assert.equal(f.properties.get('SMARTPLAN_LAST_SUCCESS_AT'), '2026-10-24T12:00:00+00:00');

// 3. Plain text/Unicode is preserved; attachment and HTML bytes are not delivered.
assert.equal(f.requests[0].message, 'Rückruf bitte.\nFiktiver Text.');
assert.equal(f.requests[0].sender_email, 'sender@example.test');
assert.ok(f.requests.at(-1).message.startsWith('Diese E-Mail enthält keinen übernehmbaren Textteil.'));
assert.ok(!JSON.stringify(f.requests).includes('external.invalid'));
assert.ok(!f.logs.join('').includes('SPIN_'));

// 4. Wrong mailbox and missing configured label fail before reading messages.
const wrong = fixture(); wrong.profile('other@example.test');
assert.throws(() => wrong.context.smartplanGmailImport(), /Postfach/);
assert.equal(wrong.listings.length, 0); assert.equal(wrong.fetched.length, 0);
const missing = fixture(); missing.label(false);
assert.throws(() => missing.context.smartplanGmailImport(), /Label fehlt/);
assert.equal(missing.fetched.length, 0);

// 5. A label removed since the list is not delivered or marked successful.
const removed = fixture(); removed.messages.a1.labelIds = []; removed.messages.a2.labelIds = [];
removed.context.smartplanGmailImport();
assert.equal(removed.requests.length, 0);
assert.equal(removed.properties.has('SMARTPLAN_LAST_SUCCESS_AT'), false);

// 6. Header-only/body limits are deterministic and keep explicit truncation.
const limits = fixture();
const envelope = limits.context.smartplanEnvelope_({id: 'bb', internalDate: '1792828800000', labelIds: ['ONLY_LABEL'],
  payload: {mimeType: 'text/plain', headers: [{name: 'Subject', value: 'x'.repeat(500)}],
            body: {data: Buffer.from('ä'.repeat(50000)).toString('base64url')}}}, 'office@example.test');
assert.equal(Array.from(envelope.subject).length, 300);
assert.ok(Array.from(envelope.message).length <= 40000);
assert.ok(envelope.message.includes('Text gekürzt'));
console.log('6 synthetic Apps Script checks passed');

// 7. Permanently deleted first message advances durably before a later lost
// receipt. A fresh script context resumes at the second message, then next page.
const methodNotFound = 'API call to gmail.users.messages.get failed with error: Requested entity was not found.';
const permanentErrors = [
  Object.assign(new Error('Synthetic provider 404'), {code: 404}),
  Object.assign(new Error('Synthetic provider details'), {details: {code: 404}}),
  Object.assign(new Error('Synthetic nested provider details'), {details: {error: {code: 404}}}),
  new Error(methodNotFound), new Error('GoogleJsonResponseException: ' + methodNotFound)
];
for (const error of permanentErrors) {
  const gone = fixture(); gone.readErrors.set('a1', error);
  assert.throws(() => gone.context.smartplanGmailImport(), /HTTP 503/);
  assert.equal(JSON.parse(gone.properties.get('SMARTPLAN_PENDING')).offset, 1);
  assert.equal(gone.properties.has('SMARTPLAN_LAST_SUCCESS_AT'), false);
  assert.deepEqual(gone.requests.map(item => item.source_id), ['a2']);
  gone.restart();
  gone.context.smartplanGmailImport();
  assert.equal(gone.properties.get('SMARTPLAN_PAGE_TOKEN'), 'NEXT');
  assert.equal(gone.properties.has('SMARTPLAN_PENDING'), false);
  gone.restart();
  gone.context.smartplanGmailImport();
  assert.deepEqual(gone.fetched, ['a1', 'a2', 'a2', 'a3']);
  assert.deepEqual([...gone.delivered.keys()], ['a2', 'a3']);
  assert.equal(gone.properties.has('SMARTPLAN_PAGE_TOKEN'), false);
  assert.equal(gone.properties.get('SMARTPLAN_LAST_SUCCESS_AT'), '2026-10-24T12:00:00+00:00');
}

// 8. Transient, permission, ambiguous and unrelated NotFound errors keep the same
// pending ID even across a fresh runtime. Mail text cannot mark itself missing.
const retryErrors = [
  ...[403, 429, 500].map(code => Object.assign(new Error('Synthetic provider failure'), {code})),
  new Error('Synthetic timeout'), new Error('404 not found'),
  new Error('Requested entity was not found.'),
  new Error(methodNotFound.replace('messages.get', 'messages.list')),
  Object.assign(new Error(methodNotFound), {code: 403}),
  Object.assign(new Error(methodNotFound), {code: '404'}),
  Object.assign(new Error(methodNotFound), {code: 500, details: {code: 404}})
];
for (const error of retryErrors) {
  const retry = fixture(); retry.readErrors.set('a1', error);
  for (let attempt = 0; attempt < 2; attempt++) {
    assert.throws(() => retry.context.smartplanGmailImport(), thrown => thrown === error);
    assert.equal(JSON.parse(retry.properties.get('SMARTPLAN_PENDING')).offset, 0);
    assert.equal(retry.requests.length, 0);
    assert.equal(retry.properties.has('SMARTPLAN_LAST_SUCCESS_AT'), false);
    retry.restart();
  }
  assert.deepEqual(retry.fetched, ['a1', 'a1']);
}
const userText = fixture();
userText.messages.a1.payload.parts[0].body.data = Buffer.from(methodNotFound).toString('base64url');
assert.throws(() => userText.context.smartplanGmailImport(), /HTTP 503/);
assert.equal(userText.requests[0].message, methodNotFound);
assert.deepEqual(userText.requests.map(item => item.source_id), ['a1', 'a2']);
console.log('2 additional deleted-message retry checks passed');
