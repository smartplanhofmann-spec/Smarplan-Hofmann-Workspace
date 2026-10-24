/* Prepared Gmail bridge. Configure Script Properties; never put a token here.
 * Uses Advanced Gmail READONLY APIs and HTTPS intake only. No mail writes.
 */
const SMARTPLAN_GMAIL_LIMITS = Object.freeze({batch: 20, runMs: 240000, message: 40000, parts: 100, encoded: 240000});

function smartplanGmailImport() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return {skipped: true};
  try {
    const properties = PropertiesService.getScriptProperties();
    const endpoint = properties.getProperty('SMARTPLAN_INTAKE_URL') || '';
    const token = properties.getProperty('SMARTPLAN_IMPORT_TOKEN') || '';
    const account = (properties.getProperty('SMARTPLAN_SOURCE_ACCOUNT') || '').trim().toLowerCase();
    const labelName = (properties.getProperty('SMARTPLAN_LABEL') || 'Smartplan-Anfragen').trim();
    const batch = Number(properties.getProperty('SMARTPLAN_BATCH_SIZE') || 20);
    if (!/^https:\/\/[A-Za-z0-9.-]+(?::443)?\/api\/v1\/intake\/gmail$/.test(endpoint) ||
        !/^SPIN_[A-Za-z0-9_-]{43}$/.test(token) || !/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(account) ||
        !labelName || labelName.length > 100 || !Number.isInteger(batch) || batch < 1 || batch > 20) {
      throw new Error('Smartplan Script Properties vollständig und korrekt einrichten.');
    }
    const profile = Gmail.Users.getProfile('me');
    if (String(profile.emailAddress || '').toLowerCase() !== account) {
      throw new Error('Angemeldetes Gmail-Postfach passt nicht zum konfigurierten Importzugang.');
    }
    const labels = Gmail.Users.Labels.list('me').labels || [];
    const label = labels.find(item => item.name === labelName);
    if (!label) throw new Error('Konfiguriertes Gmail-Label fehlt. Bitte manuell anlegen.');
    const binding = account + '\n' + label.id;
    if (properties.getProperty('SMARTPLAN_CURSOR_BINDING') !== binding) {
      properties.deleteProperty('SMARTPLAN_PAGE_TOKEN');
      properties.deleteProperty('SMARTPLAN_PENDING');
      properties.setProperty('SMARTPLAN_CURSOR_BINDING', binding);
    }
    let pending = smartplanReadPending_(properties);
    if (!pending) {
      const options = {labelIds: [label.id], maxResults: batch, includeSpamTrash: false};
      const page = properties.getProperty('SMARTPLAN_PAGE_TOKEN');
      if (page) options.pageToken = page;
      let listing;
      try {
        listing = Gmail.Users.Messages.list('me', options);
      } catch (error) {
        // Gmail page tokens can expire. Restart a read-only scan next run;
        // server-side source-ID deduplication prevents duplicate enquiries.
        properties.deleteProperty('SMARTPLAN_PAGE_TOKEN');
        throw new Error('Gmail-Liste konnte nicht gelesen werden. Nächster Lauf beginnt erneut.');
      }
      const ids = (listing.messages || []).map(item => item.id);
      if (ids.length > batch || ids.some(id => !/^[A-Za-z0-9_-]{1,128}$/.test(id))) {
        throw new Error('Unerwartete Gmail-Nachrichtenliste.');
      }
      pending = {ids: ids, offset: 0, next: listing.nextPageToken || null};
      properties.setProperty('SMARTPLAN_PENDING', JSON.stringify(pending));
    }
    const deadline = Date.now() + SMARTPLAN_GMAIL_LIMITS.runMs;
    let ingested = 0;
    let inspected = 0;
    while (pending.offset < pending.ids.length && inspected < batch && Date.now() < deadline) {
      const id = pending.ids[pending.offset];
      let mail;
      try {
        mail = Gmail.Users.Messages.get('me', id, {format: 'full'});
      } catch (error) {
        if (!smartplanGmailMessageMissing_(error)) throw error;
        // The message disappeared after listing. Persist its own progress before
        // reading the next one; neither a delivery nor a success timestamp exists.
        inspected++;
        pending.offset++;
        properties.setProperty('SMARTPLAN_PENDING', JSON.stringify(pending));
        continue;
      }
      inspected++;
      // A user may remove the label after the list request. Do not deliver it.
      if ((mail.labelIds || []).indexOf(label.id) !== -1) {
        const envelope = smartplanEnvelope_(mail, account);
        const response = UrlFetchApp.fetch(endpoint, {
          method: 'post', contentType: 'application/json',
          headers: {Authorization: 'Bearer ' + token}, payload: JSON.stringify(envelope),
          muteHttpExceptions: true, followRedirects: false, validateHttpsCertificates: true
        });
        const code = response.getResponseCode();
        if (code !== 200 && code !== 201) {
          throw new Error('Smartplan-Übernahme fehlgeschlagen (HTTP ' + code + '). Unbestätigte Nachricht wird wiederholt.');
        }
        const text = response.getContentText();
        if (text.length > 4096) throw new Error('Unerwartete Smartplan-Bestätigung.');
        let receipt;
        try { receipt = JSON.parse(text); } catch (error) { throw new Error('Unerwartete Smartplan-Bestätigung.'); }
        if (!receipt || receipt.status !== 'received' || !/^[a-f0-9]{32}$/.test(receipt.id || '') ||
            !Number.isFinite(Date.parse(receipt.ingested_at || ''))) {
          throw new Error('Smartplan hat die Übernahme nicht eindeutig bestätigt.');
        }
        // Only a confirmed HTTP intake changes success/cursor state.
        properties.setProperty('SMARTPLAN_LAST_SUCCESS_AT', receipt.ingested_at);
        ingested++;
      }
      pending.offset++;
      properties.setProperty('SMARTPLAN_PENDING', JSON.stringify(pending));
    }
    if (pending.offset === pending.ids.length) {
      if (pending.next) properties.setProperty('SMARTPLAN_PAGE_TOKEN', pending.next);
      else properties.deleteProperty('SMARTPLAN_PAGE_TOKEN');
      properties.deleteProperty('SMARTPLAN_PENDING');
    }
    const summary = {inspected: inspected, ingested: ingested, remaining: pending.ids.length - pending.offset};
    console.log(JSON.stringify(summary));
    return summary;
  } finally {
    lock.releaseLock();
  }
}

function smartplanReadPending_(properties) {
  const raw = properties.getProperty('SMARTPLAN_PENDING');
  if (!raw) return null;
  try {
    const value = JSON.parse(raw);
    if (Array.isArray(value.ids) && value.ids.length <= 20 &&
        value.ids.every(id => typeof id === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(id)) &&
        Number.isInteger(value.offset) && value.offset >= 0 && value.offset <= value.ids.length &&
        (value.next === null || (typeof value.next === 'string' && value.next.length <= 2048))) return value;
  } catch (error) { /* Invalid local cursor restarts a deduplicated scan. */ }
  properties.deleteProperty('SMARTPLAN_PENDING');
  properties.deleteProperty('SMARTPLAN_PAGE_TOKEN');
  return null;
}

function smartplanGmailMessageMissing_(error) {
  // Called only for Messages.get exceptions, never for message contents or an
  // intake response. Conflicting or nonnumeric provider codes remain retryable.
  if (!error || typeof error !== 'object') return false;
  const details = error.details && typeof error.details === 'object' ? error.details : {};
  const nested = details.error && typeof details.error === 'object' ? details.error : {};
  const codes = [error.code, details.code, nested.code].filter(value => value !== undefined);
  if (codes.length) return codes.every(code => code === 404);
  // Advanced Gmail may expose only this exact GoogleJsonResponseException text.
  return typeof error.message === 'string' &&
    /^(?:GoogleJsonResponseException: )?API call to gmail\.users\.messages\.get failed with error: Requested entity was not found\.?$/.test(error.message);
}

function smartplanHeader_(part, name) {
  const entries = (part.headers || []).filter(item => String(item.name).toLowerCase() === name.toLowerCase());
  return entries.length ? String(entries[0].value || '').replace(/[\r\n\x00-\x1f]/g, ' ').trim() : '';
}

function smartplanClip_(text, maximum, suffix) {
  const characters = Array.from(String(text));
  if (characters.length <= maximum) return characters.join('');
  suffix = suffix || '';
  return characters.slice(0, maximum - Array.from(suffix).length).join('') + suffix;
}

function smartplanEnvelope_(mail, account) {
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(mail.id || '')) throw new Error('Gmail-ID fehlt.');
  const payload = mail.payload || {};
  const pieces = [];
  let visited = 0;
  let total = 0;
  let truncated = false;
  function collect(part) {
    if (++visited > SMARTPLAN_GMAIL_LIMITS.parts || total >= SMARTPLAN_GMAIL_LIMITS.message) { truncated = true; return; }
    // Never fetch Attachments.get, filename parts or attachmentId payloads.
    if (part.filename || (part.body && part.body.attachmentId)) return;
    if (part.mimeType === 'text/plain' && part.body && part.body.data) {
      let encoded = String(part.body.data);
      if (encoded.length > SMARTPLAN_GMAIL_LIMITS.encoded) { encoded = encoded.slice(0, SMARTPLAN_GMAIL_LIMITS.encoded); truncated = true; }
      while (encoded.length % 4) encoded += '=';
      const type = smartplanHeader_(part, 'Content-Type');
      const charset = /charset\s*=\s*["']?([A-Za-z0-9_-]+)/i.exec(type);
      let decoded;
      try {
        decoded = Utilities.newBlob(Utilities.base64DecodeWebSafe(encoded)).getDataAsString(charset ? charset[1] : 'UTF-8');
      } catch (error) { throw new Error('Gmail-Text konnte nicht sicher dekodiert werden.'); }
      decoded = decoded.replace(/\r\n?/g, '\n').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '');
      const remaining = SMARTPLAN_GMAIL_LIMITS.message - total;
      if (Array.from(decoded).length > remaining) truncated = true;
      pieces.push(smartplanClip_(decoded, remaining, ''));
      total += Array.from(pieces[pieces.length - 1]).length;
    }
    (part.parts || []).forEach(collect);
  }
  collect(payload);
  let message = pieces.join('\n\n').trim();
  if (!message) message = 'Diese E-Mail enthält keinen übernehmbaren Textteil. Bitte das Original in Gmail prüfen; Anhänge wurden nicht übernommen.';
  const notice = '\n\n[Text gekürzt; vollständiges Original in Gmail prüfen.]';
  if (truncated || Array.from(message).length > SMARTPLAN_GMAIL_LIMITS.message) {
    message = smartplanClip_(message + notice, SMARTPLAN_GMAIL_LIMITS.message, notice);
  }
  const from = smartplanHeader_(payload, 'From');
  const match = /^(.*?)\s*<([^<>\s]+@[^<>\s]+)>$/.exec(from);
  let email = match ? match[2] : from;
  if (!/^[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+$/.test(email) || email.length > 254) email = '';
  const instant = Number(mail.internalDate);
  if (!Number.isFinite(instant) || instant <= 0) throw new Error('Gmail-Eingangszeit fehlt.');
  return {source_account: account, source_id: mail.id,
          subject: smartplanClip_(smartplanHeader_(payload, 'Subject') || '(ohne Betreff)', 300, ''),
          message: message, sender_name: smartplanClip_(match ? match[1].replace(/^["']|["']$/g, '').trim() : (email ? '' : from), 200, ''),
          sender_email: email, received_at: new Date(instant).toISOString()};
}
