/* Private travel facts and actual reimbursements. No automatic payment retry. */
const ID = /^[a-f0-9]{32}$/;
const HASH = /^[a-f0-9]{64}$/;
const ROOT = '/business/personnel/travel';
const copy = value => JSON.parse(JSON.stringify(value));
const fail = (message, status = 0) => Object.assign(new Error(message), {status});
const newId = () => crypto.randomUUID().replaceAll('-', '');

export const travelStatus = {
  draft: 'Entwurf', submitted: 'Eingereicht', rejected: 'Zurückgewiesen',
  approved: 'Freigegeben', void: 'Aufgehoben', active: 'Gültig',
  partially_paid: 'Teilweise erstattet', paid: 'Erstattet',
};

export function travelMinor(input, {zero = false} = {}) {
  const value = String(input ?? '').trim().replace(',', '.');
  if (!/^\d{1,11}(?:\.\d{1,2})?$/.test(value)) {
    throw fail('EUR-Betrag mit höchstens zwei Nachkommastellen eingeben.');
  }
  const [integer, fraction = ''] = value.split('.');
  const amount = Number(integer) * 100 + Number(fraction.padEnd(2, '0'));
  if (!Number.isSafeInteger(amount) || amount < (zero ? 0 : 1) || amount > 1e12) {
    throw fail(zero ? 'Ein nicht negativer EUR-Betrag ist erforderlich.' : 'Ein positiver EUR-Betrag ist erforderlich.');
  }
  return amount;
}

export function travelLocalTime(value) {
  const raw = String(value ?? '').trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(raw);
  if (!match) throw fail('Tatsächliches Datum und lokale Uhrzeit vollständig angeben.');
  const [, year, month, day, hour, minute] = match.map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 ||
      date.getUTCDate() !== day || date.getUTCHours() !== hour || date.getUTCMinutes() !== minute) {
    throw fail('Die lokale Datums- oder Zeitangabe ist ungültig.');
  }
  // Preserve the entered civil time. The server resolves the explicit zone
  // and any ambiguous clock change; the browser's own zone is irrelevant.
  return raw;
}

export function travelCanonical(value) {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'number' && Number.isSafeInteger(value)) return String(value);
  if (Array.isArray(value)) return '[' + value.map(travelCanonical).join(',') + ']';
  if (value && Object.getPrototypeOf(value) === Object.prototype) {
    return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + travelCanonical(value[key])).join(',') + '}';
  }
  throw fail('Der Reiseauftrag enthält kein eindeutig speicherbares Feld.');
}

export async function travelHash(value) {
  const bytes = new TextEncoder().encode(travelCanonical(value));
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), v => v.toString(16).padStart(2, '0')).join('');
}

export async function travelReceipt(value, expected) {
  if (!value || value.confirmed !== true || value.request_id !== expected.request_id ||
      value.actor_id !== expected.actor_id || value.employee_id !== expected.employee_id ||
      value.operation !== expected.operation || value.target_kind !== expected.target_kind ||
      value.target_id !== expected.target_id || !Number.isSafeInteger(value.revision) || value.revision < 1 ||
      value.request_hash !== expected.request_hash || !HASH.test(value.result_hash ?? '') ||
      !value.result || value.result.id !== expected.target_id ||
      value.result.employee_id !== expected.employee_id || value.result.revision !== value.revision ||
      await travelHash(value.result) !== value.result_hash) {
    throw fail('Die Bestätigung gehört nicht zum ursprünglichen Reiseauftrag.');
  }
  return value;
}

export async function travelOriginal(blob, expected) {
  if (!HASH.test(expected?.sha256 ?? '') || !Number.isSafeInteger(expected?.size) || expected.size < 1 || expected.size > 16000000) {
    throw fail('Der Originalnachweis ist unvollständig.');
  }
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), v => v.toString(16).padStart(2, '0')).join('');
  if (bytes.length !== expected.size || hash !== expected.sha256) throw fail('Das Original stimmt nicht mit Größe und Prüfsumme überein.');
  return bytes;
}

export function travelReference(value) {
  if (!ID.test(value?.id ?? '') || !Number.isSafeInteger(value.revision) || value.revision < 1 || !HASH.test(value.content_hash ?? '')) {
    throw fail('Die gewählte Reisequelle besitzt keine eindeutige Fassung.');
  }
  return {id: value.id, revision: value.revision, content_hash: value.content_hash};
}

export function travelTimeOptions(value, local, timezone) {
  if (value?.local !== travelLocalTime(local) || value.timezone !== timezone ||
      !Array.isArray(value.options) || value.options.length > 2 ||
      value.valid !== (value.options.length > 0) ||
      value.options.some(item => typeof item.label !== 'string' ||
        !/^[+-]\d{2}:\d{2}$/.test(item.offset ?? '') ||
        item.instant !== local + ':00' + item.offset) ||
      new Set(value.options.map(item => item.instant)).size !== value.options.length) {
    throw fail('Die Zeitauflösung gehört nicht zum gewählten Ort und Zeitpunkt.');
  }
  if (!value.valid) throw fail('Diese lokale Uhrzeit existiert beim Zeitwechsel nicht. Tatsächlichen Zeitpunkt angeben.');
  return value.options;
}

export function travelPreview(value, employeeId, body) {
  const amounts = ['meal_base_minor', 'meal_reduction_minor', 'meal_allowance_minor',
    'lodging_allowance_minor', 'requested_minor', 'tax_free_minor',
    'flat_taxable_minor', 'individual_taxable_minor', 'benefit_in_kind_minor',
    'already_paid_minor', 'remaining_minor', 'overpaid_minor', ...(['de_travel_2026_v2','de_travel_2026_v3'].includes(value?.rule_version) ? ['expense_allowance_minor', 'expense_already_paid_minor'] : [])];
  if (value?.employee_id !== employeeId || !HASH.test(value.source_hash ?? '') ||
      !HASH.test(value.preview_hash ?? '') || !HASH.test(value.rule_hash ?? '') ||
      !HASH.test(value.table_hash ?? '') || typeof value.rule_version !== 'string' ||
      !Array.isArray(value.days) || !Array.isArray(value.blockers) ||
      typeof value.can_approve !== 'boolean' || typeof value.can_pay !== 'boolean' ||
      !Array.isArray(value.trip_refs) ||
      travelCanonical(value.trip_refs) !== travelCanonical(body.trip_refs) ||
      amounts.some(key => !Number.isSafeInteger(value.totals?.[key]) ||
        key !== 'remaining_minor' && value.totals[key] < 0) ||
      value.blockers.length > 0 && value.can_approve) {
    throw fail('Die Abrechnungsvorschau gehört nicht zu den gewählten Reisen und Quellen.');
  }
  value.trip_refs.forEach(travelReference);
  for (const day of value.days) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day.date ?? '') ||
        ['full_minor', 'base_minor', 'meal_reduction_minor', 'meal_allowance_minor',
          'lodging_allowance_minor', 'benefit_in_kind_minor', 'absence_seconds']
          .some(key => !Number.isSafeInteger(day[key]) || day[key] < 0) ||
        !Array.isArray(day.reasons)) {
      throw fail('Die Tagesherleitung ist unvollständig. Es wird kein Nullanspruch angenommen.');
    }
  }
  if(value.rule_version==='de_travel_2026_v3')travelV3Calculation(value,body.trip_refs);
  return value;
}

export function travelMixedAssessment(raw,files) {
  const keys=['method','program_sessions','program_complete','cost_allocation_reviewed','source_file_ids','review_note'];
  const originals=ids=>{
    if(!Array.isArray(ids)||ids.length<1||ids.length>100||new Set(ids).size!==ids.length||ids.some(id=>!ID.test(id)||!files.some(f=>f.id===id)))throw fail('Jeden Programmpunkt mit tatsächlichen freigegebenen Originalen belegen.');
    return [...ids].sort();
  };
  if(!raw||Object.keys(raw).some(key=>!keys.includes(key))||raw.method!=='documented_program_ratio'||typeof raw.program_complete!=='boolean'||typeof raw.cost_allocation_reviewed!=='boolean'||typeof raw.review_note!=='string'||!raw.review_note.trim()||raw.review_note.length>2000||!Array.isArray(raw.program_sessions)||raw.program_sessions.length<2||raw.program_sessions.length>1000)throw fail('Das vollständige gemischte Programm mit Prüfvermerk und beiden ausdrücklichen Prüfbestätigungen erfassen.');
  const seen=new Set(), sessions=raw.program_sessions.map(item=>{
    if(!item||Object.keys(item).sort().join(',')!=='from,id,kind,source_file_ids,to'||!ID.test(item.id)||seen.has(item.id)||!['business','private'].includes(item.kind)||['from','to'].some(key=>typeof item[key]!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$/.test(item[key])||!Number.isFinite(Date.parse(item[key])))||Date.parse(item.from)>=Date.parse(item.to))throw fail('Programmpunkte benötigen eindeutige tatsächliche Zeiträume, Art und Originale.');
    seen.add(item.id);return {...copy(item),source_file_ids:originals(item.source_file_ids)};
  });
  const times=[...sessions].sort((a,b)=>Date.parse(a.from)-Date.parse(b.from));
  if(times.some((item,i)=>i&&Date.parse(item.from)<Date.parse(times[i-1].to)))throw fail('Programmpunkte dürfen sich zeitlich nicht überschneiden.');
  return {...copy(raw),program_sessions:sessions,source_file_ids:originals(raw.source_file_ids),review_note:raw.review_note.trim()};
}

export function travelV3Calculation(value,tripRefs) {
  const share=v=>v&&Number.isSafeInteger(v.numerator)&&Number.isSafeInteger(v.denominator)&&v.denominator>0&&v.numerator>=0&&v.numerator<=v.denominator;
  for(const day of value.days||[])if(!Number.isSafeInteger(day.unapportioned_base_minor)||day.unapportioned_base_minor<0||!share(day.business_share)||day.base_minor>day.unapportioned_base_minor)throw fail('Der berufliche Tagesanteil und die ungekürzte Bemessung fehlen.');
  for(const [key,rule]of [['ground_calendar_sources','de_travel_ground_2026_v1'],['mixed_program_sources','de_travel_mixed_program_2026_v1']]) {
    const seen=new Set();if(!Array.isArray(value[key]))throw fail('Die belegte Programm- oder Ortskalenderherleitung fehlt.');
    for(const source of value[key]) {
      const ref=travelReference(source.trip);
      if(source.rule_version!==rule||seen.has(ref.id)||!tripRefs.some(v=>travelCanonical(v)===travelCanonical(ref)))throw fail('Die Programm- oder Ortskalenderquelle gehört nicht zur ausgewählten Reisefassung.');
      seen.add(ref.id);
      if(key==='mixed_program_sources'&&source.method===undefined) {
        if(source.can_calculate!==false||!Array.isArray(source.blockers)||!source.blockers.length||value.can_approve!==false)throw fail('Die fehlende Programmbeurteilung wurde nicht ausdrücklich blockiert.');
        continue;
      }
      if(!HASH.test(source.module_hash||'')||!HASH.test(source.facts_hash||''))throw fail('Die unveränderliche Programm- oder Ortskalenderquelle ist unvollständig.');
      if(key==='mixed_program_sources'&&(source.method!=='documented_program_ratio'||!share(source)||!Number.isSafeInteger(source.business_seconds)||source.business_seconds<0||!Number.isSafeInteger(source.private_seconds)||source.private_seconds<0||!Array.isArray(source.source_file_ids)||!source.source_file_ids.length||new Set(source.source_file_ids).size!==source.source_file_ids.length||source.source_file_ids.some(id=>!ID.test(id))||typeof source.can_calculate!=='boolean'||!Array.isArray(source.blockers)))throw fail('Die belegte Programmquote ist unvollständig.');
      if(key==='ground_calendar_sources'&&(!source.days||typeof source.days!=='object'||Array.isArray(source.days)||!Array.isArray(source.boundaries)||Object.values(source.days).some(day=>!Number.isSafeInteger(day.absence_seconds)||day.absence_seconds<0||!Array.isArray(day.intervals)||typeof day.timezone!=='string')))throw fail('Der belegte örtliche Reisekalender ist unvollständig.');
    }
  }
  return value;
}

/** Complete private bodies never enter OfficeApi's general pending queue. */
export class TravelCommand {
  #pending = null;
  constructor(api, {employeeId, stamp = () => 0, allowed = () => true} = {}) {
    if (!ID.test(employeeId ?? '')) throw fail('Eine eindeutige Mitarbeiterzuordnung ist erforderlich.');
    this.api = api; this.employeeId = employeeId; this.stamp = stamp; this.allowed = allowed; this.epoch = 0;
  }
  get pending() {
    if (!this.#pending) return null;
    const {request_id, actor_id, employee_id, operation, target_kind, target_id} = this.#pending;
    return {request_id, actor_id, employee_id, operation, target_kind, target_id};
  }
  clear() {
    if (this.#pending) this.#pending.body = {};
    this.#pending = null; this.epoch++;
  }
  check(stamp, epoch) {
    if (!this.allowed() || stamp !== this.stamp() || epoch !== this.epoch) {
      this.clear(); throw fail('Sitzung oder Mitarbeiter geändert. Private Reiseeingaben wurden verworfen.', 403);
    }
  }
  async read(path) {
    const stamp = this.stamp(), epoch = this.epoch;
    try {
      const value = await this.api.get(path);
      this.check(stamp, epoch); return value;
    } catch (error) {
      if ([401, 403, 410].includes(error?.status)) this.clear();
      throw error;
    }
  }
  async fresh(right = 'read') {
    const stamp = this.stamp(), epoch = this.epoch;
    const [actor, caps, sources] = await Promise.all([
      this.read('/me'), this.read('/business/capabilities'),
      this.read(ROOT + '/sources?employee_id=' + this.employeeId),
    ]);
    this.check(stamp, epoch);
    if (!ID.test(actor?.id ?? '') || !caps.features?.includes('travel_allowances') ||
        !caps.capabilities?.includes('business_travel_allowances') ||
        sources.employee?.id !== this.employeeId || sources.rights?.read !== true ||
        sources.rights?.[right] !== true || right !== 'read' && (caps.readonly !== false || sources.active !== true || sources.readonly !== false)) {
      this.clear(); throw fail('Die aktuelle Mitarbeiter- oder Reisefreigabe fehlt.', 403);
    }
    return {actor, caps, sources};
  }
  async submit(path, body, {operation, targetKind, targetId, right = 'write', validate} = {}) {
    if (this.#pending) throw fail('Zuerst die Bestätigung des offenen Reiseauftrags prüfen.', 409);
    if (!ID.test(targetId ?? '') || !['site', 'trip', 'settlement', 'payment'].includes(targetKind) ||
        typeof operation !== 'string' || !/^[a-z][a-z_.-]{0,39}$/.test(operation) ||
        !path.startsWith(ROOT + '/') || /[?#]/.test(path) || body?.employee_id !== this.employeeId) {
      throw fail('Der Reiseauftrag ist nicht eindeutig an Mitarbeiter und Quelle gebunden.');
    }
    const stamp = this.stamp(), epoch = this.epoch;
    const {actor} = await this.fresh(right);
    const frozen = {...copy(body), request_id: newId()};
    const requestHash = await travelHash([operation, targetKind, targetId, frozen]);
    this.check(stamp, epoch);
    this.#pending = {
      path, body: frozen, operation, target_kind: targetKind, target_id: targetId,
      request_id: frozen.request_id, employee_id: this.employeeId, actor_id: actor.id,
      request_hash: requestHash, right, validate, stamp, epoch,
    };
    return this.send();
  }
  async status({resolve = false} = {}) {
    const pending = this.#pending;
    if (!pending) throw fail('Kein unbestätigter Reiseauftrag im Arbeitsspeicher.');
    this.check(pending.stamp, pending.epoch);
    const {actor} = await this.fresh();
    if (actor.id !== pending.actor_id) {this.clear(); throw fail('Der Auftraggeber wurde geändert.', 403);}
    const value = await this.read(ROOT + '/requests/' + pending.request_id);
    const receipt = await travelReceipt(value, pending);
    this.check(pending.stamp, pending.epoch);
    if (pending.validate) await pending.validate(receipt.result);
    this.check(pending.stamp, pending.epoch);
    if (resolve) {pending.body = {}; this.#pending = null;}
    return receipt;
  }
  async send() {
    const pending = this.#pending;
    if (!pending) throw fail('Kein privater Reiseauftrag zum Senden vorhanden.');
    this.check(pending.stamp, pending.epoch);
    const {actor} = await this.fresh(pending.right);
    if (actor.id !== pending.actor_id) {this.clear(); throw fail('Der Auftraggeber wurde geändert.', 403);}
    try {
      await this.api.post(pending.path, copy(pending.body));
      this.check(pending.stamp, pending.epoch);
      return await this.status({resolve: true});
    } catch (error) {
      if ([401, 403, 410].includes(error?.status)) this.clear();
      // An uncertain transport, stale source or absent status cannot prove
      // that an accepted payment record did not already reach the server.
      throw error;
    }
  }
  async retry() {
    if (!this.#pending) throw fail('Kein unbestätigter Reiseauftrag vorhanden.');
    try {return await this.status({resolve: true});}
    catch (error) {if (error?.status !== 404) throw error;}
    return this.send();
  }
}

export function travelAllowancesUi(h) {
  const {api, el, button, field, form: sharedForm, dialog, panel, rows, row, notice, table} = h;
  // The ordinary form closes its modal before running `after`. A private
  // view must replace its own modal first, otherwise its close observer would
  // correctly revoke the command while the next private view is loading.
  const form = (title, fields, save, options = {}) => sharedForm(title, fields, async (...args) => {
    try {
      const result = await save(...args);
      if (result !== undefined && options.after) await options.after(result);
      return undefined;
    } catch (error) {
      if ([401, 403, 410].includes(error?.status)) clear();
      refreshPending();
      throw error;
    }
  }, {...options, after: () => {}});
  const money = amount => Number.isSafeInteger(amount) ? h.formatMoney((amount / 100).toFixed(2)) : 'Noch nicht bestimmt';
  let command = null, employee = null, sources = null, catalog = null;
  let active = null, observer = null, draft = null;
  function clear() {
    observer?.disconnect(); observer = null;
    command?.clear(); command = null;
    if (active?.isConnected) {
      active.querySelectorAll('input,textarea,select').forEach(input => {input.value = '';});
      active.replaceChildren(notice('Private Reiseansicht geschlossen. Quellen erneut öffnen.'));
    }
    active = null; employee = null; sources = null; catalog = null; draft = null;
  }
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') clear();
  });
  if (typeof window !== 'undefined') window.addEventListener('pagehide', clear);
  const path = part => ROOT + part;
  async function run(task) {
    try {return await task();}
    catch (error) {
      const target = active;
      if ([401, 403, 410].includes(error?.status)) clear();
      refreshPending();
      if (target?.isConnected) {
        target.querySelectorAll(':scope > [data-travel-error]').forEach(node => node.remove());
        const message = notice(error.message || 'Die Reiseaktion konnte nicht bestätigt werden.', 'error');
        message.dataset.travelError = 'true'; target.prepend(message);
      } else throw error;
    }
  }
  function show(title, body) {
    observer?.disconnect(); active = body;
    body.setAttribute('data-travel-allowances', employee?.id || 'private');
    dialog(title, body);
    if (typeof MutationObserver !== 'undefined') {
      observer = new MutationObserver(() => {if (active === body && !body.isConnected) clear();});
      observer.observe(document.body, {childList: true, subtree: true});
    }
  }
  async function fresh(right = 'read') {
    if (!command) throw fail('Die Reiseansicht wurde geschlossen.', 403);
    const value = await command.fresh(right); sources = value.sources;
    employee = sources.employee; return value;
  }
  async function get(part) {
    if (!command) throw fail('Die Reiseansicht wurde geschlossen.', 403);
    return command.read(path(part));
  }
  function can(right) {return sources?.rights?.[right] === true && sources.active === true && sources.readonly === false;}
  function choices(values, label = value => value.name || value.filename || value.id) {
    return values.map(value => [value.id, label(value)]);
  }
  function fileChoices() {return [['', 'Original auswählen'], ...choices(sources.files || [])];}
  function sourceFiles(ids) {
    if (!Array.isArray(ids) || !ids.length || ids.some(id => !sources.files.some(file => file.id === id && file.employee_id === employee.id))) {
      throw fail('Mindestens ein tatsächlich freigegebenes Original auswählen.');
    }
    return ids;
  }
  function refreshPending() {
    if (!active?.isConnected) return;
    active.querySelectorAll('[data-travel-pending]').forEach(node => node.remove());
    const pending = pendingBox();
    if (pending) active.prepend(pending);
  }
  function pendingBox() {
    if (!command?.pending) return null;
    const pending = command.pending;
    const box = panel('Bestätigung noch offen', notice('Zuerst den ursprünglichen Auftrag prüfen. Es wird keine neue Zahlung angelegt.'),
      el('p', {}, `${pending.operation} · ursprünglicher Auftrag ${pending.request_id.slice(0, 8)}`),
      button('Status des ursprünglichen Auftrags prüfen', () => run(async () => {
        await command.status({resolve: true}); await load();
      }), 'primary'),
      button('Ursprünglichen Auftrag unverändert wiederholen', () => run(async () => {
        await command.retry(); await load();
      }), 'small'),
      button('Private Eingaben verwerfen und Stand neu laden', () => run(async () => {
        command.clear(); draft = null; await load();
      }), 'small'));
    box.dataset.travelPending = 'true'; return box;
  }
  async function open(person) {
    if (!person || !ID.test(person.id ?? '')) throw fail('Mitarbeiter zuerst auswählen.');
    if (!command || employee?.id !== person.id) {
      clear(); employee = person;
      command = new TravelCommand(api, {employeeId: person.id, stamp: h.stamp, allowed: () => h.allowed?.() !== false});
    }
    return load();
  }
  async function load() {
    await fresh(); const captured = command, epoch = command.epoch, stamp = h.stamp?.() ?? 0;
    const [rules, trips, settlements, payments] = await Promise.all([
      get('/catalog'), get('/trips?employee_id=' + employee.id),
      get('/settlements?employee_id=' + employee.id), get('/payments?employee_id=' + employee.id),
    ]);
    captured.check(stamp, epoch);
    if ([trips, settlements, payments].some(value => value.employee_id !== employee.id || !Array.isArray(value.items)) || !Array.isArray(rules.rates)) {
      throw fail('Die Reiseübersicht gehört nicht zum geöffneten Mitarbeiter.');
    }
    catalog = rules;
    const free = !command.pending;
    show('Reisen und Pauschalen · ' + employee.name, el('div', {class: 'stack'},
      notice('Belegte Reisen, nachvollziehbare Tagesbeträge und tatsächliche Erstattungen. Eine Berechnung ist noch keine Zahlung.'),
      pendingBox(),
      panel('Reisen', can('write') && free ? button('Neue Reise erfassen', () => run(() => editTrip()), 'primary') : null,
        rows(trips.items, item => row(item.details?.purpose || item.purpose || 'Reise',
          `Fassung ${item.revision} · ${travelStatus[item.status] || item.status}`,
          [button('Reise und Historie', () => run(() => detail('trips', item.id)), 'small')]))),
      panel('Orte und Nachweise', can('write') && free ? button('Stätte belegt erfassen', () => run(() => editSite()), 'small') : null,
        rows(sources.sites || [], item => row(item.details?.name || item.name || 'Stätte',
          `Fassung ${item.revision} · ${travelStatus[item.status] || item.status}`,
          [button('Stättennachweis öffnen', () => run(() => detail('sites', item.id)), 'small')]))),
      panel('Abrechnungen', can('approve') && free ? button('Eingereichte Reisen abrechnen', () => run(() => settlementEditor(trips.items)), 'primary') : null,
        rows(settlements.items, item => row(`Abrechnung · Fassung ${item.revision}`,
          `${money(item.calculation?.totals?.requested_minor ?? item.totals?.requested_minor)} · ${travelStatus[item.status] || item.status}`,
          [button('Abrechnung und Erstattungen', () => run(() => detail('settlements', item.id)), 'small')]))),
      panel('Tatsächliche Erstattungen', rows(payments.items, item => row(
        item.details?.kind === 'repayment' ? 'Tatsächliche Rückzahlung' : 'Tatsächliche Erstattung',
        `${money(item.details?.amount_minor)} · ${h.formatDate(item.details?.paid_on)} · Fassung ${item.revision}`,
        [button('Zahlungsnachweis und Historie', () => run(() => detail('payments', item.id)), 'small')]))),
      button('Ansicht neu laden', () => run(load), 'small')));
  }
  function bodyFields(value, fields) {
    return table(['Angabe', 'Gespeicherter Nachweis'], fields.map(([key, label]) => [label, value?.[key] == null || value[key] === '' ? 'Nicht angegeben' : factLabel(String(value[key]))]));
  }
  function calculation(value) {
    const totals = value?.totals || {};
    return el('div', {class: 'stack'},
      value?.blockers?.length ? panel('Noch zu klären', ...value.blockers.map(item => notice(item.text || item.code))) : null,
      el('div', {class: 'table-scroll', style: 'overflow-x:auto;max-width:100%'}, table(
        ['Tag', 'Ort', 'Anspruch', 'Mahlzeitenkürzung', 'Verpflegung', 'Unterkunft'],
        (value?.days || []).map(day => [h.formatDate(day.date), [day.country, day.region].filter(Boolean).join(' · '),
          money(day.base_minor), money(day.meal_reduction_minor), money(day.meal_allowance_minor), money(day.lodging_allowance_minor)]))),
      ...(value?.days || []).map(day => el('details', {}, el('summary', {}, 'Herleitung · ' + h.formatDate(day.date)),
        value.rule_version==='de_travel_2026_v3'?el('p',{},`Bemessung vor Aufteilung: ${money(day.unapportioned_base_minor)} · belegter beruflicher Anteil: ${day.business_share.numerator}/${day.business_share.denominator}`):null,
        el('p', {}, `Belegte Abwesenheit: ${Math.floor(day.absence_seconds / 3600)} h ${Math.floor(day.absence_seconds % 3600 / 60)} min · voller Tagessatz: ${money(day.full_minor)} · Kennzeichen M: ${day.letter_m === true ? 'Ja' : day.letter_m === false ? 'Nein' : 'Noch nicht festgestellt'} · Sachbezug: ${money(day.benefit_in_kind_minor)}`),
        ...day.reasons.map(reason => el('p', {}, reason.text || reason.code)),
        day.three_month ? el('p', {}, `Stättenfrist: ${day.three_month.eligible ? 'Anspruch zeitlich zulässig' : 'Kein bestätigter Anspruch'} · Beginn ${h.formatDate(day.three_month.started_on)} · Ende ${h.formatDate(day.three_month.expires_on)}`) : null)),
      ...((value?.mixed_program_sources||[]).map(source=>panel('Belegte Programmaufteilung',notice(source.method?`Beruflich ${source.business_seconds} Sekunden · privat ${source.private_seconds} Sekunden · Anteil ${source.numerator}/${source.denominator} · ${source.source_file_ids.length} Originalnachweise`:'Eine belegte vollständige Programmbeurteilung fehlt.')))),
      ...((value?.ground_calendar_sources||[]).map(source=>panel('Örtlicher Reisekalender',table(['Ortstag','Belegte Abwesenheit','Ortszeitzone'],Object.entries(source.days).map(([day,detail])=>[h.formatDate(day),detail.absence_seconds+' Sekunden',detail.timezone]))))),
      ...(value?.payroll_required ? [notice('Diese geprüfte Abrechnung benötigt zusätzlich die gebundene Lohnverarbeitung. Steuerpflichtige Mehrbeträge werden über Lohnnetto ausgezahlt; ein Reisekostenauftrag zahlt sie nicht nochmals.')] : []),
      ...((value?.expense_items || []).length ? [panel('Tatsächliche Auslagen je Original', table(['Datum', 'Art', 'Beruflich', 'Privat', 'Bereitgestellt', 'Bereits bezahlt', 'Prüfgrund'], value.expense_items.map(item => [h.formatDate(item.date), factLabel(item.kind), money(item.business_minor), money(item.private_minor), money(item.provided_minor), money(item.already_paid_minor), item.review_note])))] : []),
      table(['Gesamtbetrag', 'EUR'], [
        ['Beantragt', money(totals.requested_minor)], ['Steuerfrei', money(totals.tax_free_minor)],
        ['Pauschalierbarer Anteil', money(totals.flat_taxable_minor)], ['Individuell steuerpflichtig', money(totals.individual_taxable_minor)],
        ['Sachbezug', money(totals.benefit_in_kind_minor)], ['Bereits tatsächlich bezahlt', money(totals.already_paid_minor)],
        ...(totals.expense_allowance_minor === undefined ? [] : [['Tatsächliche berufliche Auslagen', money(totals.expense_allowance_minor)], ['Davon bereits belegte Auslagenerstattung', money(totals.expense_already_paid_minor)]]), ['Verbleibend', money(totals.remaining_minor)], ['Belegt überzahlt', money(totals.overpaid_minor)],
      ]));
  }
  async function detail(kind, id, revision = null) {
    await fresh(); const current = command, epoch = command.epoch, stamp = h.stamp?.() ?? 0;
    const response = await get(`/${kind}/${id}${revision ? '?revision=' + revision : ''}`);
    current.check(stamp, epoch);
    const item = response.item;
    if (item?.id !== id || item.employee_id !== employee.id || !Number.isSafeInteger(item.revision) || revision && item.revision !== revision) {
      throw fail('Die historische Ansicht gehört nicht zur gewählten Reisequelle.');
    }
    const content = el('div', {class: 'stack'}, pendingBox(),
      el('p', {}, `Fassung ${item.revision} · ${travelStatus[item.status] || item.status || 'Gespeichert'}`));
    if (kind === 'sites') {
      content.append(bodyFields(item.details, [['name', 'Stätte'], ['kind', 'Art'], ['address', 'Anschrift'], ['timezone', 'Zeitzone'],
        ['effective_from', 'Gültig ab'], ['effective_to', 'Gültig bis'], ['assignment_basis', 'Belegte Zuordnung'], ['history_complete_from', 'Vorgeschichte vollständig ab']]));
      if (item.details.frequency_periods?.length) content.append(panel('Datierte Einsatzhäufigkeit', table(['Gültig ab', 'Gültig bis', 'Belegte Einsatztage je Woche'], item.details.frequency_periods.map(period => [h.formatDate(period.from), period.to ? h.formatDate(period.to) : 'Offen', String(period.days_per_week)]))));
      if (!revision && can('write') && !command.pending) content.append(button('Stättennachweis korrigieren', () => run(() => editSite(item)), 'small'));
    } else if (kind === 'trips') {
      content.append(bodyFields(item.details, [['purpose', 'Reisezweck'], ['departed_at', 'Tatsächlicher Beginn'], ['returned_at', 'Tatsächliches Ende'], ['timezone', 'Zeitzone']]),
        tripSections(item.details || {}));
      if (!revision && !command.pending) {
        if (can('write')) content.append(button('Reise korrigieren', () => run(() => editTrip(item)), 'small'));
        if (item.status === 'draft' && can('write')) content.append(button('Reise zur Prüfung einreichen', () => run(() => tripAction(item, 'submit')), 'primary'));
        if (item.status === 'submitted' && can('approve')) content.append(button('Mit Begründung zurückweisen', () => run(() => tripAction(item, 'reject')), 'small'));
      }
    } else if (kind === 'settlements') {
      if(item.calculation?.rule_version==='de_travel_2026_v3')travelV3Calculation(item.calculation,item.details.trip_refs);
      content.append(notice('Stand dieser gespeicherten Abrechnung. Nachfolgende tatsächliche Zahlungen und Rückzahlungen sind separat in den Zahlungsnachweisen dokumentiert.'), calculation(item.calculation || item.preview || item));
      if (sources.rights.export) for (const format of ['pdf', 'json']) {
        const metadata = item.exports?.[format];
        if (metadata) content.append(button(`${format.toUpperCase()} · Fassung ${item.revision}`, () => run(() => download(
          `/${kind}/${id}/export?revision=${item.revision}&format=${format}`, metadata, 'export')), 'small'));
      }
      if (!revision && can('payments') && !command.pending) content.append(
        button('Tatsächliche Erstattung erfassen', () => run(() => paymentEditor(item, 'reimbursement')), 'primary'),
        button('Tatsächliche Rückzahlung erfassen', () => run(() => paymentEditor(item, 'repayment')), 'small'),
        ...((item.sources?.expenses || []).some(expense => expense.payments?.length) ? [button('Bereits belegte Auslagenzahlung für Finanzen übernehmen', () => run(() => adoptLegacy(item)), 'small')] : []));
      if (!revision && can('approve') && !command.pending) content.append(button('Abrechnung belegt korrigieren', () => run(async () => {
        const trips = await get('/trips?employee_id=' + employee.id); await settlementEditor(trips.items, item);
      }), 'small'));
    } else {
      if (item.details?.legacy_payment) content.append(notice('Finanznachweis einer bereits früher belegten Auslagenzahlung. Diese Übernahme erzeugt keine weitere Auszahlung.'));
      content.append(bodyFields(item.details, [['kind', 'Zahlungsart'], ['paid_on', 'Tatsächlicher Tag'], ['reference', 'Zahlungsreferenz'], ['status', 'Nachweisstatus']]),
        el('p', {}, 'Tatsächlicher Betrag: ' + money(item.details?.amount_minor)));
      if (!revision && can('payments') && !command.pending) content.append(
        button('Zahlungsnachweis korrigieren', () => run(async () => {
          const settlement = (await get('/settlements/' + item.details.settlement_ref.id)).item;
          await paymentEditor(settlement, item.details.kind, item, 'correct');
        }), 'small'),
        button('Fälschlichen Zahlungsnachweis aufheben', () => run(async () => {
          const settlement = (await get('/settlements/' + item.details.settlement_ref.id)).item;
          await paymentEditor(settlement, item.details.kind, item, 'void');
        }), 'small'));
    }
    const originalFiles = item.sources?.files || [];
    if (originalFiles.length) content.append(panel('Unveränderte Originalnachweise', ...originalFiles.map(file =>
      button(file.filename, () => run(() => originalFile(file)), 'small'))));
    if (!revision) content.append(button('Alle Fassungen öffnen', () => run(async () => {
      const history = await get(`/${kind}/${id}/history`);
      if (history.id !== id || history.employee_id !== employee.id) throw fail('Historie gehört nicht zur gewählten Quelle.');
      show('Unveränderte Fassungen', rows(history.items, previous => row('Fassung ' + previous.revision,
        travelStatus[previous.status] || previous.status || '',
        [button('Historische Fassung öffnen', () => run(() => detail(kind, id, previous.revision)), 'small')])));
    }), 'small'));
    content.append(button('Zur Reiseübersicht', () => run(load), 'small'));
    show({sites: 'Stättennachweis', trips: 'Reise', settlements: 'Reiseabrechnung', payments: 'Zahlungsnachweis'}[kind], content);
  }
  async function download(part, metadata, right = 'read') {
    await fresh(right === 'export' ? 'read' : right);
    if (right === 'export' && sources.rights.export !== true) throw fail('Die Exportfreigabe fehlt.', 403);
    const captured = command, epoch = command.epoch, stamp = h.stamp?.() ?? 0;
    const blob = await api.binary(path(part));
    await travelOriginal(blob, metadata); await fresh(); captured.check(stamp, epoch);
    if (right === 'export' && sources.rights.export !== true) throw fail('Die Exportfreigabe wurde entzogen.', 403);
    h.saveBlob(blob, metadata.filename);
  }
  async function originalFile(metadata) {
    await fresh(); const current = command, epoch = command.epoch, stamp = h.stamp?.() ?? 0;
    const file = (sources.files || []).find(value => value.id === metadata.id && value.sha256 === metadata.sha256 && value.employee_id === employee.id);
    if (!file) throw fail('Das private Original ist für diese Person nicht mehr freigegeben.', 403);
    const blob = await api.binary('/business/personnel/files/' + file.id + '/content');
    await travelOriginal(blob, file); await fresh(); current.check(stamp, epoch);
    if (!(sources.files || []).some(value => value.id === file.id && value.sha256 === file.sha256)) throw fail('Die Originalfreigabe wurde geändert.', 403);
    h.saveBlob(blob, file.filename);
  }
  async function editSite(previous = null) {
    await fresh('write'); const old = previous?.details || {};
    const frequencyRows = el('div', {class: 'stack'});
    const changed = el('input', {type: 'checkbox', checked: !!old.frequency_periods?.length});
    const frequencyBody = el('div', {class: 'stack'});
    function addPeriod(value = {}) {
      const input = (label, type, value, extra = {}) => el('label', {class: 'field'}, label,
        el('input', {type, value: value ?? '', 'aria-label': label, ...extra}));
      const start = input('Häufigkeitsphase gültig ab', 'date', value.from),
        end = input('Häufigkeitsphase gültig bis, falls beendet', 'date', value.to),
        days = input('Einsatztage pro Woche in dieser Phase', 'number', value.days_per_week, {min: 0, max: 7, step: 1});
      const files = el('select', {multiple: true, 'aria-label': 'Originale dieser Häufigkeitsphase'},
        (sources.files || []).map(file => el('option', {value: file.id, selected: (value.source_file_ids || []).includes(file.id)}, file.filename)));
      const entry = el('div', {class: 'panel stack'}, start, end, days,
        el('label', {class: 'field'}, 'Originale dieser Häufigkeitsphase', files));
      entry.read = () => {
        const from = start.querySelector('input').value, to = end.querySelector('input').value || null,
          raw = days.querySelector('input').value, number = Number(raw);
        if (!from || raw === '' || !Number.isInteger(number) || number < 0 || number > 7) throw fail('Jede Häufigkeitsphase braucht Beginn und belegte Einsatztage zwischen null und sieben.');
        return {from, to, days_per_week: number, source_file_ids: sourceFiles(Array.from(files.selectedOptions, item => item.value))};
      };
      entry.append(button('Häufigkeitsphase entfernen', () => entry.remove(), 'small'));
      frequencyRows.append(entry);
    }
    for (const value of old.frequency_periods || []) addPeriod(value);
    frequencyBody.append(notice('Die Phasen müssen ab dem Zuordnungsbeginn lückenlos sein. Jede Änderung braucht einen datierten Originalnachweis.'), frequencyRows,
      button('Häufigkeitsphase hinzufügen', () => addPeriod(), 'small'));
    frequencyBody.hidden = !changed.checked;
    changed.addEventListener('change', () => {frequencyBody.hidden = !changed.checked; if (changed.checked && !frequencyRows.children.length) addPeriod();});
    const frequency = panel('Belegte Einsatzhäufigkeit', el('label', {class: 'check'}, changed, 'Einsatzhäufigkeit hat sich geändert'),
      notice('Ohne datierte Änderungen gilt die angegebene Wochenhäufigkeit ausdrücklich für die gesamte belegte Zuordnung.'), frequencyBody);
    const fields = [field('name', 'Bezeichnung der Stätte', 'text', old.name || '', {required: true}),
      field('kind', 'Art der Stätte', 'select', old.kind || '', {required: true, options: [['', 'Bitte auswählen'],
        ['home', 'Wohnung'], ['first_workplace', 'Erste Tätigkeitsstätte'], ['external_fixed', 'Auswärtige feste Stätte'], ['mobile', 'Mobile Tätigkeit'], ['wide_area', 'Weiträumiges Gebiet']]}),
      field('address', 'Tatsächliche Anschrift oder Ortsbeschreibung', 'textarea', old.address || '', {required: true}),
      field('rate_id', 'Land und Gebiet', 'select', old.rate_id || '', {required: true, options: [['', 'Bitte auswählen'], ...catalog.rates.map(rate => [rate.id, [rate.country, rate.region].filter(Boolean).join(' · ')])]}),
      field('timezone', 'Zeitzone am Ort (IANA)', 'text', old.timezone || '', {required: true, help: 'Zum Beispiel Europe/Berlin. Ortszeit und Zeitwechsel werden damit geprüft.'}),
      field('effective_from', 'Zuordnung gültig ab', 'date', old.effective_from || '', {required: true}),
      field('effective_to', 'Zuordnung gültig bis (falls beendet)', 'date', old.effective_to || ''),
      field('assignment_basis', 'Begründung und Nachweis der Zuordnung', 'textarea', old.assignment_basis || '', {required: true}),
      field('regular_days_per_week', 'Belegte tatsächliche Einsatztage pro Woche', 'integer', old.regular_days_per_week ?? '', {required: true, min: 0, max: 7}),
      field('history_complete_from', 'Vorgeschichte vollständig geprüft ab', 'date', old.history_complete_from || '', {required: true}),
      field('prior_visit_dates', 'Frühere belegte Besuchstage · ein Datum YYYY-MM-DD je Zeile', 'textarea', (old.prior_visit_dates || []).join('\n')),
      field('source_file_ids', 'Originalnachweise der Stätte', 'multi', old.source_file_ids || [], {required: true, options: choices(sources.files || [])}),
      ...(previous ? [field('status', 'Nachweisstatus', 'select', previous.status, {options: [['active', 'Gültig'], ['void', 'Begründet aufgehoben']]}),
        field('correction_reason', 'Korrekturgrund', 'textarea', '', {required: true})] : [])];
    const id = previous?.id || newId();
    show(previous ? 'Stättennachweis korrigieren' : 'Stätte belegt erfassen', form('', fields, async values => {
      const {status = 'active', correction_reason = '', ...details} = values;
      details.effective_to ||= null;
      details.prior_visit_dates = details.prior_visit_dates.split(/\s+/).filter(Boolean);
      if (details.prior_visit_dates.some(value => !/^\d{4}-\d{2}-\d{2}$/.test(value))) throw fail('Frühere Besuchstage jeweils als vollständiges Datum angeben.');
      sourceFiles(details.source_file_ids);
      if (changed.checked) {
        details.frequency_periods = Array.from(frequencyRows.children, entry => entry.read());
        if (!details.frequency_periods.length) throw fail('Mindestens eine belegte Häufigkeitsphase angeben.');
      }
      return command.submit(path('/sites'), {employee_id: employee.id, id, revision: previous?.revision || 0, status, details, correction_reason},
        {operation: 'site.save', targetKind: 'site', targetId: id});
    }, {key: 'travel-site-' + id, submit: 'Nachweis unveränderlich speichern', after: load, extra: el('div', {class: 'stack'}, pendingBox(), frequency)}));
  }
  const labels = {work: 'Tätigkeit', transit: 'Unterwegs', stay: 'Aufenthalt', ground: 'Landweg', flight: 'Flug', ship: 'Schiff', none: 'Keine Unterkunftserstattung', flat: 'Übernachtungspauschale', expense: 'Tatsächliche Auslage', employee: 'Mitarbeiter', employer: 'Arbeitgeber', third_party_free: 'Dritter unentgeltlich', breakfast: 'Frühstück', lunch: 'Mittagessen', dinner: 'Abendessen', home: 'Wohnung', first_workplace: 'Erste Tätigkeitsstätte', external_fixed: 'Auswärtige feste Stätte', mobile: 'Mobile Tätigkeit', wide_area: 'Weiträumiges Gebiet', reimbursement: 'Erstattung', repayment: 'Rückzahlung', transport: 'Beförderung', lodging: 'Unterkunft', incidental: 'Reisenebenkosten'};
  const factLabel = value => labels[value] || value || '';
  function tripSections(value) {
    return el('div', {class: 'stack'},
      panel('Stationen', rows(value.segments || [], item => row(`${item.from} – ${item.to}`, `${factLabel(item.activity)} · ${factLabel(item.transport)}`))),
      panel('Übernachtungen', rows(value.overnights || [], item => row(h.formatDate(item.date), `${factLabel(item.claim_method)} · ${factLabel(item.provided_by)}`))),
      panel('Mahlzeiten', rows(value.meals || [], item => row(`${h.formatDate(item.date)} · ${factLabel(item.kind)}`, `Eigener Anteil: ${money(item.employee_paid_minor)}`))),
      panel('Private Reiseabschnitte',rows(value.private_intervals||[],item=>row(`${item.from} – ${item.to}`,'Tatsächlich privat'))),
      value.mixed_assessment?panel('Belegtes gemischtes Reiseprogramm',notice(value.mixed_assessment.review_note),rows(value.mixed_assessment.program_sessions,item=>row(`${item.from} – ${item.to}`,item.kind==='business'?'Berufliches Programm':'Privates Programm'))):null);
  }
  async function editTrip(previous = null) {
    await fresh('write');
    draft = {id: previous?.id || newId(), revision: previous?.revision || 0,
      correction_reason: '', details: copy(previous?.details || {purpose: '', project_id: null,
        departed_at: '', returned_at: '', timezone: '', source_file_ids: [],
        home_site_ref: null, first_workplace_ref: null, segments: [], overnights: [], meals: [],
        expense_refs: [], requested_meal_minor: 0, requested_lodging_minor: 0,
        tax_choice: 'tax_free_only', private_intervals: []})};
    return tripEditor();
  }
  function tripEditor() {
    if (!draft) throw fail('Der private Reiseentwurf wurde verworfen.');
    const current = draft, details = current.details;
    const content = el('div', {class: 'stack'}, notice('Reisedaten zuerst belegt erfassen. Eine Speicherung ist noch keine Freigabe oder Zahlung.'),
      pendingBox(), bodyFields(details, [['purpose', 'Reisezweck'], ['departed_at', 'Beginn'], ['returned_at', 'Ende'], ['timezone', 'Zeitzone']]),
      button('Grunddaten und Pauschalenwunsch bearbeiten', () => run(() => tripBasics()), 'primary'));
    for (const [kind, title, singular] of [['segments', 'Stationen', 'Station'], ['overnights', 'Übernachtungen', 'Übernachtung'],
      ['meals', 'Mahlzeiten', 'Mahlzeit'], ['private_intervals', 'Private Reiseabschnitte', 'Privater Abschnitt']]) {
      content.append(panel(title, button(singular + ' hinzufügen', () => run(() => tripRow(kind)), 'small'),
        rows(details[kind], (item, index) => row(item.date || item.from || singular,
          factLabel(item.kind || item.activity || item.claim_method),
          [button('Angaben bearbeiten', () => run(() => tripRow(kind, item, index)), 'small'),
            button('Aus Entwurf entfernen', () => {details[kind].splice(index, 1); tripEditor();}, 'small')]))));
    }
    if(catalog?.rule_version==='de_travel_2026_v3'||details.mixed_assessment) {
      const mixed=details.mixed_assessment;
      content.append(panel('Belegtes gemischtes Reiseprogramm',notice('Nur ein vollständig belegtes berufliches und privates Gesamtprogramm erlaubt diese Aufteilung. Tatsächliche Privatzeiten zusätzlich einzeln erfassen; Originalkosten gesondert aufteilen.'),
        button('Programmbeurteilung bearbeiten',()=>run(()=>mixedEditor()),'small'),
        mixed?el('div',{class:'stack'},notice(mixed.review_note),notice(`Vollständiges Programm: ${mixed.program_complete?'bestätigt':'noch offen'} · getrennte Kosten: ${mixed.cost_allocation_reviewed?'geprüft':'noch offen'}`),
          button('Programmpunkt hinzufügen',()=>run(()=>programEditor()),'small'),
          rows(mixed.program_sessions,(item,index)=>row(`${item.from} – ${item.to}`,item.kind==='business'?'Berufliches Programm':'Privates Programm',[button('Programmpunkt bearbeiten',()=>run(()=>programEditor(item,index)),'small'),button('Programmpunkt entfernen',()=>{mixed.program_sessions.splice(index,1);mixed.program_complete=false;mixed.cost_allocation_reviewed=false;tripEditor();},'small')])),
          button('Programmbeurteilung aus Entwurf entfernen',()=>{delete details.mixed_assessment;tripEditor();},'small')):null));
    }
    content.append(panel('Tatsächliche Auslagen', button('Auslagenposition belegt aufteilen', () => run(() => expenseEditor()), 'small'),
      rows(details.expense_allocations || [], (item, index) => row(({transport: 'Beförderung', lodging: 'Unterkunft', incidental: 'Reisenebenkosten'})[item.kind],
        `Beruflich ${money(item.business_minor)} · privat ${money(item.private_minor)} · bereitgestellt ${money(item.provided_minor)}`,
        [button('Aufteilung bearbeiten', () => run(() => expenseEditor(item, index)), 'small'), button('Aufteilung entfernen', () => {details.expense_allocations.splice(index, 1); tripEditor();}, 'small')]))),
      panel('Zusammenhängende Beförderungen', button('Flugreise belegen', () => run(() => transportEditor('flight')), 'small'), button('Schiffsreise belegen', () => run(() => transportEditor('ship')), 'small'),
        rows(details.transport_facts || [], (item, index) => row(item.kind === 'flight' ? 'Belegte Flugreise' : 'Belegte Schiffsreise', `${(item.legs || item.segment_ids || []).length} zugeordnete Abschnitte`,
          [button('Beförderung bearbeiten', () => run(() => transportEditor(item.kind, item, index)), 'small'), button('Beförderungszuordnung entfernen', () => {details.transport_facts.splice(index, 1); tripEditor();}, 'small')]))));
    content.append(button('Reiseentwurf belegt speichern', () => run(async () => {
      await fresh('write');
      if (!details.purpose || !details.departed_at || !details.returned_at || !details.timezone || !details.segments.length) {
        throw fail('Reisezweck, tatsächlicher Zeitraum, Zeitzone und vollständige Stationen sind erforderlich.');
      }
      sourceFiles(details.source_file_ids);
      if(details.mixed_assessment)details.mixed_assessment=travelMixedAssessment(details.mixed_assessment,sources.files);
      if (current.revision && !current.correction_reason.trim()) throw fail('Für die neue Fassung einen Korrekturgrund angeben.');
      await command.submit(path('/trips'), {employee_id: employee.id, ...copy(current)},
        {operation: 'trip.save', targetKind: 'trip', targetId: current.id});
      draft = null; await load();
    }), 'primary'), button('Zur Übersicht', () => run(load), 'small'));
    show('Reiseentwurf', content);
  }
  async function mixedEditor() {
    await fresh('write');const current=draft,old=current.details.mixed_assessment||{};
    show('Gemischtes Programm belegt beurteilen',form('',[
      field('source_file_ids','Originale des vollständigen Reiseprogramms','multi',old.source_file_ids||[],{required:true,options:choices(sources.files)}),
      field('review_note','Begründung der beruflichen und privaten Programmzuordnung','textarea',old.review_note||'',{required:true,maxLength:2000}),
      field('program_complete','Das gesamte berufliche und private Programm ist vollständig belegt.','checkbox',false),
      field('cost_allocation_reviewed','Die Originalkosten sind getrennt beruflich, privat und bereitgestellt geprüft.','checkbox',false),
    ],async values=>{
      if(draft!==current)throw fail('Der Reiseentwurf wurde geschlossen.',403);
      current.details.mixed_assessment={method:'documented_program_ratio',program_sessions:copy(old.program_sessions||[]),source_file_ids:sourceFiles(values.source_file_ids),review_note:values.review_note,program_complete:values.program_complete===true,cost_allocation_reviewed:values.cost_allocation_reviewed===true};
      tripEditor();return undefined;
    },{key:'travel-mixed-assessment',submit:'Programmbeurteilung in den Entwurf übernehmen'}));
  }
  async function programEditor(previous=null,index=null) {
    await fresh('write');const current=draft,assessment=current.details.mixed_assessment,old=previous||{};
    show('Belegter Programmpunkt',form('',[
      ...timeFields('from','Programmbeginn',old.from||''),...timeFields('to','Programmende',old.to||''),
      field('timezone','Zeitzone am Programmort (IANA)','text',current.details.timezone,{required:true}),
      field('kind','Belegte Art des Programmpunkts','select',old.kind||'',{required:true,options:[['','Bitte ausdrücklich wählen'],['business','Berufliches Programm'],['private','Privates Programm']]}),
      field('source_file_ids','Originale dieses Programmpunkts','multi',old.source_file_ids||[],{required:true,options:choices(sources.files)}),
    ],async values=>{
      const files=sourceFiles(values.source_file_ids);
      await withTimes(values,[['from','Programmbeginn',values.timezone],['to','Programmende',values.timezone]],times=>{
        if(draft!==current||current.details.mixed_assessment!==assessment)throw fail('Die Programmbeurteilung wurde geschlossen.',403);
        const item={id:old.id||newId(),...times,kind:values.kind,source_file_ids:files};
        if(Date.parse(item.from)>=Date.parse(item.to))throw fail('Der Programmbeginn muss vor dem Ende liegen.');
        if(index===null)assessment.program_sessions.push(item);else assessment.program_sessions[index]=item;
        assessment.program_complete=false;assessment.cost_allocation_reviewed=false;tripEditor();
      });return undefined;
    },{key:'travel-program-session',submit:'Programmpunkt in den Entwurf übernehmen'}));
  }
  function expensePositions() {
    const selected = new Set((draft.details.expense_refs || []).map(item => item.id));
    return (sources.expenses || []).filter(expense => selected.has(expense.id)).flatMap(expense =>
      (expense.items || []).map(item => ({expense, item, id: expense.id + ':' + item.receipt_file_id,
        name: `${expense.purpose || 'Auslage'} · ${item.date} · ${item.description} · ${money(item.amount_minor)}`})));
  }
  async function expenseEditor(previous = null, index = null) {
    await fresh('write'); const current = draft, old = previous || {}, positions = expensePositions();
    if (!positions.length) throw fail('Zuerst vorhandene tatsächliche Auslagen in den Reisegrunddaten auswählen.');
    show('Belegte Auslagenposition aufteilen', form('', [
      field('position', 'Tatsächlich gespeicherte Auslagenposition', 'select', previous ? old.expense_ref.id + ':' + old.receipt_file_id : '',
        {required: true, options: [['', 'Originalposition auswählen'], ...positions.map(value => [value.id, value.name])]}),
      field('kind', 'Belegte Auslagenart', 'select', old.kind || '', {required: true, options: [['', 'Bitte auswählen'], ['transport', 'Beförderung'], ['lodging', 'Unterkunft'], ['incidental', 'Reisenebenkosten']]}),
      ...[['business_minor', 'Tatsächlich beruflicher Anteil EUR'], ['private_minor', 'Tatsächlich privater Anteil EUR'], ['provided_minor', 'Vom Arbeitgeber oder Dritten bereitgestellter Anteil EUR']].map(([key, label]) =>
        field(key, label, 'text', previous ? (old[key] / 100).toFixed(2) : '', {required: true})),
      field('review_note', 'Nachweis und Begründung der vollständigen Aufteilung', 'textarea', old.review_note || '', {required: true}),
    ], async values => {
      if (draft !== current) throw fail('Der Reiseentwurf wurde geschlossen.', 403);
      const position = positions.find(item => item.id === values.position);
      if (!position) throw fail('Eine tatsächliche gespeicherte Originalposition auswählen.');
      const value = {expense_ref: travelReference(position.expense), receipt_file_id: position.item.receipt_file_id,
        kind: values.kind, review_note: values.review_note,
        ...Object.fromEntries(['business_minor', 'private_minor', 'provided_minor'].map(key => [key, travelMinor(values[key], {zero: true})]))};
      if (value.business_minor + value.private_minor + value.provided_minor !== position.item.amount_minor) throw fail('Beruflicher, privater und bereitgestellter Anteil müssen genau den gespeicherten Originalbetrag ergeben.');
      const list = current.details.expense_allocations ||= [];
      if (list.some((item, at) => at !== index && item.expense_ref.id === value.expense_ref.id && item.receipt_file_id === value.receipt_file_id)) throw fail('Diese Originalposition ist bereits aufgeteilt.');
      if (index === null) list.push(value); else list[index] = value;
      tripEditor(); return undefined;
    }, {key: 'travel-expense-allocation', submit: 'Belegte Aufteilung übernehmen', description: 'Nur tatsächlich berufliche Arbeitnehmerauslagen werden erstattet. Eine bereits belegte Erstattung bleibt bezahlt. Hier wird keine Vorsteuer beansprucht.'}));
  }
  async function transportEditor(kind, previous = null, index = null) {
    await fresh('write'); const current = draft, old = previous || {},
      segments = current.details.segments.filter(item => item.transport === kind),
      sites = [['', 'Stätte auswählen'], ...choices((sources.sites || []).filter(item => item.details?.kind !== 'home'), item => item.details?.name || item.name)],
      segmentChoices = segments.map((item, at) => [item.id, `${kind === 'flight' ? 'Flug' : 'Schiff'} ${at + 1} · ${item.from} – ${item.to}`]),
      nightChoices = (current.details.overnights || []).map(item => [item.id, `${item.date} · ${sources.sites.find(site => site.id === item.site_ref.id)?.details?.name || 'Übernachtung'}`]);
    if (!segments.length) throw fail('Zuerst die tatsächlichen Flug- beziehungsweise Schiffsabschnitte als Reisestationen erfassen.');
    const fields = [field('segment_ids', 'Zu dieser zusammenhängenden Beförderung gehörende Abschnitte', 'multi', kind === 'flight' ? (old.legs || []).map(item => item.segment_id) : old.segment_ids || [], {required: true, options: segmentChoices})];
    if (kind === 'flight') for (const [at, segment] of segments.entries()) {
      const leg = (old.legs || []).find(item => item.segment_id === segment.id) || {}, stop = (old.stopovers || []).find(item => item.after_segment_id === segment.id);
      fields.push(field('departure_' + at, `Flugabschnitt ${at + 1} · tatsächlicher Abflugort`, 'select', leg.departure_site_ref?.id || '', {options: sites}),
        field('arrival_' + at, `Flugabschnitt ${at + 1} · tatsächlicher Ankunftsort`, 'select', leg.arrival_site_ref?.id || '', {options: sites}),
        field('nights_' + at, `Notwendige Zwischenübernachtungen nach Flugabschnitt ${at + 1}`, 'multi', stop?.overnight_ids || [], {options: nightChoices}));
    } else fields.push(
      field('departure_site', 'Tatsächlicher Einschiffungsort', 'select', old.departure_site_ref?.id || '', {required: true, options: sites}),
      field('arrival_site', 'Tatsächlicher Ausschiffungsort', 'select', old.arrival_site_ref?.id || '', {required: true, options: sites}),
      field('role', 'Belegte Rolle während der Schiffsreise', 'select', old.role || '', {required: true, options: [['', 'Bitte auswählen'], ['passenger', 'Reisender'], ['german_state_crew', 'Besatzung eines deutschen staatlichen Schiffs'], ['german_merchant_crew', 'Besatzung eines deutschen Handelsschiffs']]}),
      field('high_seas_segment_ids', 'Belegte Abschnitte auf hoher See', 'multi', old.high_seas_segment_ids || [], {options: segmentChoices}));
    fields.push(field('source_file_ids', 'Originale dieser zusammenhängenden Beförderung', 'multi', old.source_file_ids || [], {required: true, options: choices(sources.files || [])}));
    show(kind === 'flight' ? 'Zusammenhängende Flugreise belegen' : 'Zusammenhängende Schiffsreise belegen', form('', fields, async values => {
      if (draft !== current) throw fail('Der Reiseentwurf wurde geschlossen.', 403);
      if (!values.segment_ids.length) throw fail('Die tatsächlich zugehörigen Beförderungsabschnitte auswählen.');
      const ref = siteId => travelReference(sources.sites.find(site => site.id === siteId));
      const value = {id: old.id || newId(), kind, source_file_ids: sourceFiles(values.source_file_ids)};
      if (kind === 'flight') {
        value.legs = segments.flatMap((segment, at) => values.segment_ids.includes(segment.id) ? [{segment_id: segment.id,
          departure_site_ref: ref(values['departure_' + at]), arrival_site_ref: ref(values['arrival_' + at])}] : []);
        value.stopovers = segments.flatMap((segment, at) => values.segment_ids.includes(segment.id) && values['nights_' + at]?.length ? [{after_segment_id: segment.id, overnight_ids: values['nights_' + at]}] : []);
      } else Object.assign(value, {segment_ids: values.segment_ids, departure_site_ref: ref(values.departure_site), arrival_site_ref: ref(values.arrival_site), role: values.role, high_seas_segment_ids: values.high_seas_segment_ids || []});
      const list = current.details.transport_facts ||= [];
      if (index === null) list.push(value); else list[index] = value;
      tripEditor(); return undefined;
    }, {key: 'travel-transport-' + kind, submit: 'Belegte Beförderung übernehmen', description: 'Orte und Zeitpunkte stammen aus tatsächlichen Stationen. Notwendige Zwischenübernachtungen werden einzeln zugeordnet; Tagespauschalen werden daraus berechnet.'}));
  }
  function timeFields(prefix, label, instant = '') {
    return [field(prefix + '_date', label + ' · Datum', 'date', instant.slice(0, 10), {required: true}),
      field(prefix + '_time', label + ' · Ortszeit', 'time', instant.slice(11, 16), {required: true})];
  }
  async function withTimes(values, entries, finish) {
    const unresolved = [], resolved = {};
    for (const [key, label, timezone] of entries) {
      const local = travelLocalTime(`${values[key + '_date']}T${values[key + '_time']}`);
      const options = travelTimeOptions(await get('/time-options?local=' + encodeURIComponent(local) + '&timezone=' + encodeURIComponent(timezone)), local, timezone);
      if (options.length === 1) resolved[key] = options[0].instant;
      else unresolved.push({key, label, options});
    }
    if (!unresolved.length) return finish(resolved);
    show('Zeitlage am tatsächlichen Ort bestätigen', form('', unresolved.map(({key, label, options}) =>
      field(key, label + ' · tatsächlich gemeinte Uhrzeit', 'select', '', {required: true, options: [['', 'Zeitlage auswählen'], ...options.map(option => [option.instant, option.label])]})),
    async selected => {for (const item of unresolved) if (!item.options.some(option => option.instant === selected[item.key])) throw fail('Tatsächliche Zeitlage auswählen.');
      await finish({...resolved, ...selected}); return undefined;
    }, {key: 'travel-time-choice', submit: 'Tatsächliche Zeitlage übernehmen', description: 'Diese Uhrzeit kommt bei der Zeitumstellung zweimal vor.'}));
  }
  async function tripBasics() {
    await fresh('write'); const current = draft, value = current.details;
    const siteChoices = [['', 'Nicht zugeordnet'], ...choices(sources.sites || [], item => item.details?.name || item.name)];
    const fields = [field('purpose', 'Tatsächlicher Reisezweck', 'textarea', value.purpose, {required: true}),
      field('project_id', 'Projektbezug', 'select', value.project_id || '', {options: [['', 'Ohne Projektbezug'], ...choices(sources.projects || [])]}),
      field('timezone', 'Zeitzone des Reisezeitraums (IANA)', 'text', value.timezone, {required: true}),
      ...timeFields('departed_at', 'Tatsächlicher Beginn', value.departed_at), ...timeFields('returned_at', 'Tatsächliches Ende', value.returned_at),
      field('home_site_ref', 'Belegte Wohnung', 'select', value.home_site_ref?.id || '', {options: siteChoices}),
      field('first_workplace_ref', 'Belegte erste Tätigkeitsstätte', 'select', value.first_workplace_ref?.id || '', {options: siteChoices}),
      field('source_file_ids', 'Reiseoriginale', 'multi', value.source_file_ids, {required: true, options: choices(sources.files || [])}),
      field('expense_refs', 'Bereits erfasste tatsächliche Auslagen', 'multi', value.expense_refs.map(item => item.id), {options: choices(sources.expenses || [], item => item.purpose || item.id)}),
      field('requested_meal', 'Beantragte Verpflegung EUR', 'text', (value.requested_meal_minor / 100).toFixed(2), {required: true}),
      field('requested_lodging', 'Beantragte Unterkunft EUR', 'text', (value.requested_lodging_minor / 100).toFixed(2), {required: true}),
      field('tax_choice', 'Beantragte steuerliche Behandlung', 'select', value.tax_choice, {options: [['tax_free_only', 'Nur belegbar steuerfreie Erstattung'], ['flat_25', 'Pauschalversteuerung ausdrücklich prüfen'], ['individual', 'Individuelle Lohnversteuerung ausdrücklich prüfen']]}),
      ...(current.revision ? [field('correction_reason', 'Korrekturgrund', 'textarea', current.correction_reason, {required: true})] : [])];
    show('Reisegrunddaten', form('', fields, async values => {
      const resolved = {...values, requested_meal_minor: travelMinor(values.requested_meal, {zero: true}),
        requested_lodging_minor: travelMinor(values.requested_lodging, {zero: true})};
      sourceFiles(values.source_file_ids);
      await withTimes(values, [['departed_at', 'Beginn', values.timezone], ['returned_at', 'Ende', values.timezone]], times => {
        if (draft !== current) throw fail('Der Reiseentwurf wurde geschlossen.', 403);
        for (const key of ['purpose', 'timezone', 'source_file_ids', 'tax_choice', 'requested_meal_minor', 'requested_lodging_minor']) value[key] = resolved[key];
        Object.assign(value, times, {project_id: values.project_id || null});
        for (const key of ['home_site_ref', 'first_workplace_ref']) value[key] = values[key] ? travelReference(sources.sites.find(site => site.id === values[key])) : null;
        value.expense_refs = values.expense_refs.map(id => travelReference(sources.expenses.find(item => item.id === id)));
        current.correction_reason = values.correction_reason || ''; tripEditor();
      }); return undefined;
    }, {key: 'travel-basics-' + current.id, submit: 'Grunddaten in den Entwurf übernehmen'}));
  }
  async function tripRow(kind, previous = null, index = null) {
    await fresh('write'); const current = draft, old = previous || {}, siteChoices = [['', 'Stätte auswählen'], ...choices(sources.sites || [], item => item.details?.name || item.name)];
    let fields;
    if (kind === 'segments' || kind === 'private_intervals') fields = [
      ...timeFields('from', 'Beginn', old.from || ''), ...timeFields('to', 'Ende', old.to || ''),
      field('timezone', 'Zeitzone am Ort (IANA)', 'text', current.details.timezone, {required: true}),
      ...(kind === 'segments' ? [field('site_id', 'Tatsächliche Stätte', 'select', old.site_ref?.id || '', {required: true, options: siteChoices}),
        field('activity', 'Tatsächliche Tätigkeit', 'select', old.activity || '', {required: true, options: [['', 'Bitte auswählen'], ['work', 'Tätigkeit'], ['transit', 'Unterwegs'], ['stay', 'Aufenthalt']]}),
        field('transport', 'Beförderungsart', 'select', old.transport || '', {required: true, options: [['', 'Bitte auswählen'], ['ground', 'Landweg'], ['flight', 'Flug'], ['ship', 'Schiff']]}),
        field('necessary_stopover', 'Notwendige Zwischenübernachtung', 'checkbox', old.necessary_stopover === true)] : [])];
    else if (kind === 'overnights') fields = [field('date', 'Datum der Außenübernachtung', 'date', old.date || '', {required: true}),
      field('site_id', 'Tatsächliche Übernachtungsstätte', 'select', old.site_ref?.id || '', {required: true, options: siteChoices}),
      field('claim_method', 'Beantragter Unterkunftsnachweis', 'select', old.claim_method || '', {required: true, options: [['', 'Bitte auswählen'], ['none', 'Keine Unterkunftserstattung beantragt'], ['flat', 'Übernachtungspauschale'], ['expense', 'Bereits erfasste tatsächliche Auslage']]}),
      field('provided_by', 'Unterkunft tatsächlich bezahlt beziehungsweise bereitgestellt durch', 'select', old.provided_by || '', {required: true, options: [['', 'Bitte auswählen'], ['employee', 'Mitarbeiter'], ['employer', 'Arbeitgeber'], ['third_party_free', 'Dritter unentgeltlich']]}),
      field('accommodation_kind', 'Tatsächliche Unterkunftsart · bei Pauschale erforderlich', 'select', old.accommodation_kind || '', {options: [['', 'Noch nicht belegt'], ['lodging', 'Unterkunft außerhalb eines Fahrzeugs'], ['vehicle', 'Übernachtung im Fahrzeug'], ['sleeper_train', 'Schlafwagen'], ['ship_cabin', 'Schiffskabine']]}),
      field('other_lodging_started_or_finished', 'Schlafwagen oder Schiffskabine: Übernachtung begann oder endete tatsächlich in einer anderen Unterkunft; belegt durch Reiseoriginale.', 'checkbox', old.other_lodging_started_or_finished === true),
      field('expense_receipt_file_id', 'Unterkunftsoriginal innerhalb der gewählten Auslage', 'select', old.expense_receipt_file_id || '', {options: [['', 'Kein gesondertes Original gewählt'], ...(sources.expenses || []).flatMap(expense => (expense.items || []).map(item => [item.receipt_file_id, `${expense.purpose} · ${item.description} · ${money(item.amount_minor)}`]))]}),
      field('expense_id', 'Vorhandene tatsächliche Auslage', 'select', old.expense_ref?.id || '', {options: [['', 'Keine Auslage'], ...choices(sources.expenses || [], item => item.purpose || item.id)]})];
    else fields = [field('date', 'Datum der Mahlzeit', 'date', old.date || '', {required: true}),
      field('kind', 'Mahlzeit', 'select', old.kind || '', {required: true, options: [['', 'Bitte auswählen'], ['breakfast', 'Frühstück'], ['lunch', 'Mittagessen'], ['dinner', 'Abendessen']]}),
      field('provider', 'Bereitstellung', 'select', old.provider || '', {required: true, options: [['', 'Bitte auswählen'], ['employer', 'Arbeitgeber'], ['employer_arranged', 'Vom Arbeitgeber veranlasst'], ['independent_third_party', 'Unabhängiger Dritter'], ['self', 'Selbst beschafft']]}),
      field('offered', 'Tatsächlich bereitgestellt', 'checkbox', old.offered === true), field('is_meal', 'Vollwertige Mahlzeit, kein bloßer Snack', 'checkbox', old.is_meal === true),
      field('price', 'Tatsächlicher Mahlzeitenpreis EUR', 'text', previous ? (old.price_minor / 100).toFixed(2) : '', {required: true}),
      field('employee_paid', 'Tatsächlicher eigener Anteil EUR', 'text', previous ? (old.employee_paid_minor / 100).toFixed(2) : '', {required: true}),
      field('replacement_for', 'Ersatz für bereits erfasste Mahlzeit', 'select', old.replacement_for || '', {options: [['', 'Keine Ersatzmahlzeit'], ...choices(current.details.meals.filter(item => item.id !== old.id), item => item.date + ' · ' + item.kind)]}),
      field('source_file_ids', 'Mahlzeitnachweise', 'multi', old.source_file_ids || [], {options: choices(sources.files || [])})];
    const save = value => {
      if (draft !== current) throw fail('Der Reiseentwurf wurde geschlossen.', 403);
      const item = {id: old.id || newId(), ...value};
      if (index === null) current.details[kind].push(item); else current.details[kind][index] = item;
      tripEditor();
    };
    show({segments: 'Reisestation', private_intervals: 'Privater Reiseabschnitt', overnights: 'Außenübernachtung', meals: 'Mahlzeitnachweis'}[kind], form('', fields, async values => {
      if (kind === 'segments' || kind === 'private_intervals') await withTimes(values,
        [['from', 'Beginn', values.timezone], ['to', 'Ende', values.timezone]], times => save({...times,
          ...(kind === 'segments' ? {site_ref: travelReference(sources.sites.find(site => site.id === values.site_id)),
            activity: values.activity, transport: values.transport, necessary_stopover: values.necessary_stopover === true} : {})}));
      else if (kind === 'overnights') save({date: values.date, site_ref: travelReference(sources.sites.find(site => site.id === values.site_id)),
        claim_method: values.claim_method, provided_by: values.provided_by,
        ...(values.accommodation_kind ? {accommodation_kind: values.accommodation_kind} : {}),
        other_lodging_started_or_finished: values.other_lodging_started_or_finished === true,
        ...(values.expense_receipt_file_id ? {expense_receipt_file_id: values.expense_receipt_file_id} : {}),
        expense_ref: values.expense_id ? travelReference(sources.expenses.find(item => item.id === values.expense_id)) : null});
      else save({date: values.date, kind: values.kind, provider: values.provider, offered: values.offered === true,
        is_meal: values.is_meal === true, price_minor: travelMinor(values.price, {zero: true}), employee_paid_minor: travelMinor(values.employee_paid, {zero: true}),
        replacement_for: values.replacement_for || null, source_file_ids: values.source_file_ids || []});
      return undefined;
    }, {key: 'travel-row-' + kind, submit: 'Angaben in den Entwurf übernehmen'}));
  }
  async function tripAction(item, action) {
    await fresh(action === 'reject' ? 'approve' : 'write');
    const capturedSources = sources.source_hash;
    show(action === 'submit' ? 'Reise zur Prüfung einreichen' : 'Reise zurückweisen', form('', [
      ...(action === 'reject' ? [field('reason', 'Begründung der Zurückweisung', 'textarea', '', {required: true})] : []),
      field('confirmed', 'Ich bestätige die ausgewählte Reise und ihre belegten Angaben.', 'checkbox', false, {required: true}),
    ], async values => {
      if (values.confirmed !== true) throw fail('Den gewählten Reiseauftrag ausdrücklich bestätigen.');
      return command.submit(path(`/trips/${item.id}/${action}`), {employee_id: employee.id, revision: item.revision,
        source_hash: capturedSources, ...values}, {operation: 'trip.' + action, targetKind: 'trip', targetId: item.id,
        right: action === 'reject' ? 'approve' : 'write'});
    }, {key: 'travel-' + action + '-' + item.id, submit: action === 'submit' ? 'Zur fremden Prüfung einreichen' : 'Begründet zurückweisen', after: load, extra: pendingBox()}));
  }
  async function settlementEditor(trips, previous = null) {
    await fresh('approve'); const available = trips.filter(item => item.status === 'submitted');
    if (!available.length) {show('Keine eingereichten Reisen', notice('Zuerst einen fremd prüfbaren Reiseantrag einreichen.')); return;}
    show('Eingereichte Reisen abrechnen', form('', [
      field('trip_ids', 'Ausdrücklich ausgewählte Reisen', 'multi', previous?.details?.trip_refs?.map(item => item.id) || [], {required: true, options: choices(available, item => item.details?.purpose || item.purpose || item.id)}),
      field('payroll_month', 'Vorgesehener Zuflussmonat steuerpflichtiger Mehrbeträge', 'month', previous?.details?.payroll_month || ''),
      field('period_from', 'Abrechnung von', 'date', previous?.details?.period_from || '', {required: true}), field('period_to', 'Abrechnung bis', 'date', previous?.details?.period_to || '', {required: true}),
      field('settlement_unit', 'Abrechnungseinheit', 'select', previous?.details?.settlement_unit || '', {required: true, options: [['', 'Bitte auswählen'], ['trip', 'Eine Reise'], ['combined_period', 'Belegt zusammengefasster Zeitraum']]}),
      field('tax_choice', 'Geprüfte steuerliche Behandlung', 'select', previous?.details?.tax_choice || '', {required: true, options: [['', 'Bitte auswählen'], ['tax_free_only', 'Nur steuerfreie Erstattung'], ['flat_25', 'Zulässige Pauschalversteuerung'], ['individual', 'Individuelle Lohnversteuerung']]}),
      field('requested_meal', 'Geprüfter Verpflegungsantrag EUR', 'text', previous ? (previous.details.requested_meal_minor / 100).toFixed(2) : '', {required: true}),
      field('requested_lodging', 'Geprüfter Unterkunftsantrag EUR', 'text', previous ? (previous.details.requested_lodging_minor / 100).toFixed(2) : '', {required: true}),
      field('review_note', 'Prüfung von Stätte, Vorgeschichte, Belegen und Behandlung', 'textarea', '', {required: true}),
    ], async values => {
      if (!values.trip_ids.length) throw fail('Mindestens eine eingereichte Reise auswählen.');
      const body = {employee_id: employee.id, payroll_month: values.payroll_month || null, trip_refs: values.trip_ids.map(id => travelReference(available.find(item => item.id === id))),
        period_from: values.period_from, period_to: values.period_to, settlement_unit: values.settlement_unit, tax_choice: values.tax_choice,
        requested_meal_minor: travelMinor(values.requested_meal, {zero: true}), requested_lodging_minor: travelMinor(values.requested_lodging, {zero: true}),
        correction_of: previous ? travelReference(previous) : null, review_note: values.review_note};
      const captured = command, epoch = command.epoch, stamp = h.stamp?.() ?? 0;
      const preview = travelPreview(await api.post(path('/settlements/preview'), copy(body)), employee.id, body);
      captured.check(stamp, epoch);
      const id = previous?.id || newId(), extra = calculation(preview);
      if (!preview.can_approve) {show('Reiseabrechnung noch offen', el('div', {class: 'stack'}, extra, button('Zur Übersicht', () => run(load), 'small'))); return undefined;}
      show('Geprüfte Reiseabrechnung bestätigen', form('', [field('confirmed', 'Ich bestätige die fremd geprüften Quellen und genau diese Tagesrechnung.', 'checkbox', false, {required: true})],
        async values => {if (!values.confirmed) throw fail('Die konkrete Abrechnung ausdrücklich bestätigen.');
          return command.submit(path('/settlements'), {...body, id, revision: previous?.revision || 0, source_hash: preview.source_hash,
            preview_hash: preview.preview_hash, confirmed: true}, {operation: 'settlement.approve', targetKind: 'settlement', targetId: id, right: 'approve'});
        }, {key: 'travel-settlement-' + id, submit: 'Abrechnung freigeben', after: load, extra}));
      return undefined;
    }, {key: 'travel-settlement-preview', submit: 'Tagesrechnung und offene Punkte prüfen'}));
  }
  async function adoptLegacy(settlement) {
    await fresh('payments');
    const entries = (settlement.sources?.expenses || []).flatMap(expense => (expense.payments || []).map((payment, payment_index) => ({expense, payment, payment_index, id: expense.id + ':' + payment_index})));
    if (!entries.length) throw fail('In dieser Abrechnung sind keine früher bestätigten Auslagenzahlungen gebunden.');
    show('Früher belegte Auslagenzahlung auswählen', form('', [field('payment_id', 'Unveränderte ursprüngliche Zahlung', 'select', '', {required: true, options: [['', 'Tatsächliche Zahlung auswählen'], ...entries.map(entry => [entry.id, `${entry.expense.purpose} · ${h.formatDate(entry.payment.paid_on)} · ${factLabel(entry.payment.kind)} · ${money(entry.payment.amount_minor)} · ${entry.payment.reference}`])]})], async values => {
      const selected = entries.find(entry => entry.id === values.payment_id);
      if (!selected) throw fail('Eine unveränderte tatsächlich bestätigte Auslagenzahlung auswählen.');
      await paymentEditor(settlement, selected.payment.kind, null, 'adopt_legacy', {payment: copy(selected.payment), binding: {expense_ref: travelReference(selected.expense), payment_index: selected.payment_index, payment_hash: await travelHash(selected.payment)}});
      return undefined;
    }, {key: 'travel-legacy-select', submit: 'Finanznachweis dieser Altzahlung ergänzen', description: 'Die vorhandene Zahlung wird in die Finanzquellen übernommen. Es entsteht keine weitere Auszahlung und keine zweite bereits bezahlte Auslage.'}));
  }
  async function paymentEditor(settlement, kind, previous = null, action = 'record', legacy = null) {
    await fresh('payments'); const state = sources, id = previous?.id || newId();
    const prior = previous?.details || {}, legacyBinding = legacy?.binding || prior.legacy_payment || null, fixed = legacy?.payment || prior;
    const fields = [...(action === 'void' || legacyBinding ? [] : [field('paid_on', 'Tatsächlicher Zahlungstag', 'date', prior.paid_on || '', {required: true}),
      field('amount', 'Tatsächlich belegter Betrag EUR', 'text', previous ? (prior.amount_minor / 100).toFixed(2) : '', {required: true})]),
      ...(action === 'void' ? [] : [field('account_id', 'Tatsächlich verwendetes Geldkonto', 'select', prior.account_id || '', {required: true, options: [['', 'Geldkonto auswählen'], ...choices((state.accounts || []).filter(account => account.active))]}),
      ...(legacyBinding ? [] : [field('reference', 'Zahlungsnachweis / Referenz', 'text', prior.reference || '', {required: true})]),
      field('reference_file_id', 'Unverändertes Zahlungsoriginal', 'select', '', {required: true, options: [['', 'Original auswählen'], ...choices((sources.files || []).filter(file => file.purpose === 'personnel'))]})]),
      ...(previous ? [field('correction_reason', 'Belegte Nachweiskorrektur', 'textarea', '', {required: true})] : []),
      field('confirmed', action === 'void' && legacyBinding ? 'Ich bestätige die sachlich falsche Finanz-Nachweisübernahme; die ursprüngliche tatsächliche Auslagenzahlung bleibt erhalten.' : action === 'adopt_legacy' ? 'Ich bestätige die Finanzübernahme dieser bereits belegten Zahlung; es erfolgt keine neue Auszahlung.' : action === 'void' ? 'Ich bestätige, dass der frühere Zahlungsnachweis sachlich falsch war; dies ist keine tatsächliche Rückzahlung.' :
        `Ich bestätige die bereits tatsächlich erfolgte ${kind === 'repayment' ? 'Rückzahlung' : 'Erstattung'}.`, 'checkbox', false, {required: true})];
    show(action === 'adopt_legacy' ? 'Bereits belegte Auslagenzahlung für Finanzen übernehmen' : action === 'void' ? 'Fälschlichen Zahlungsnachweis aufheben' : previous ? 'Zahlungsnachweis korrigieren' : kind === 'repayment' ? 'Tatsächliche Rückzahlung erfassen' : 'Tatsächliche Erstattung erfassen',
      form('', fields, async values => {
        if (!values.confirmed) throw fail('Den tatsächlichen Nachweis ausdrücklich bestätigen.');
        const account = action === 'void' ? {id: prior.account_id, revision: prior.account_revision} : (state.accounts || []).find(item => item.id === values.account_id);
        if (!account || !Number.isSafeInteger(account.revision)) throw fail('Das tatsächliche Geldkonto besitzt keine aktuelle Fassung.');
        return command.submit(path('/payments'), {employee_id: employee.id, id, revision: previous?.revision || 0, action,
          settlement_ref: action === 'void' || legacyBinding && previous ? copy(prior.settlement_ref) : travelReference(settlement), kind, paid_on: action === 'void' || legacyBinding ? fixed.paid_on : values.paid_on, amount_minor: action === 'void' || legacyBinding ? fixed.amount_minor : travelMinor(values.amount),
          account_id: account.id, account_revision: account.revision, instance_id: state.instance_id,
          reference: action === 'void' || legacyBinding ? fixed.reference : values.reference, ...(legacyBinding ? {legacy_payment: copy(legacyBinding)} : {}), reference_file_id: action === 'void' ? prior.reference_file_id : values.reference_file_id, source_hash: state.source_hash,
          correction_reason: values.correction_reason || '', confirmed: true},
        {operation: 'payment.record', targetKind: 'payment', targetId: id, right: 'payments'});
      }, {key: 'travel-payment-' + id, submit: action === 'adopt_legacy' ? 'Vorhandene Zahlung als Finanzquelle übernehmen' : action === 'void' ? 'Falschen Nachweis belegt aufheben' : 'Tatsächlichen Geldfluss dokumentieren',
        after: load, extra: notice(legacyBinding && action === 'void' ? 'Aufgehoben wird ausschließlich die Finanz-Nachweisübernahme. Die ursprüngliche tatsächliche Auslagenzahlung bleibt unverändert und gilt weiterhin als bereits bezahlt.' : legacyBinding && action !== 'void' ? `Unverändert gebundene frühere Zahlung: ${h.formatDate(fixed.paid_on)} · ${factLabel(fixed.kind)} · ${money(fixed.amount_minor)} · ${fixed.reference}. Ausschließlich Finanznachweis; keine neue Auszahlung.` : action === 'void' ? `Unverändert aufgehoben wird ausschließlich der frühere Nachweis: ${prior.paid_on} · ${money(prior.amount_minor)} · ${prior.reference}. Keine tatsächliche Rückzahlung.` : 'Hier wird kein Zahlungsauftrag an eine Bank versendet. Ein geänderter Anspruch ist ohne tatsächliche Zahlung noch kein Geldfluss.')}));
  }
  return {open, clear, detail, download};
}
