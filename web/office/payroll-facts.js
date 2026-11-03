/* Private, source-bound employment facts and payroll period plans. */
const ID = /^[a-f0-9]{32}$/, HASH = /^[a-f0-9]{64}$/;
const copy = value => JSON.parse(JSON.stringify(value));
function ordered(value) {
  return Array.isArray(value) ? value.map(ordered) : value && typeof value === 'object'
    ? Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value;
}
const same = (a, b) => JSON.stringify(ordered(a)) === JSON.stringify(ordered(b));
const fail = (message, status = 0) => Object.assign(new Error(message), {status});
const text = (value, label, max = 2000) => {
  const result = String(value ?? '').trim();
  if (!result || result.length > max || /[\x00-\x1f\x7f]/.test(result)) throw fail(label + ' vollständig angeben.');
  return result;
};
export const PAYROLL_FACT_KINDS = {
  employment_terms: 'Beschäftigung und Entgelt', work_schedule: 'Datierter Arbeitsplan', period_case: 'Bestätigter Monatsfall',
};
export const PAYROLL_PRORATION = {
  calendar_days_actual: 'Tatsächliche Kalendertage laut Vertrag', contractual_30_days: 'Vertraglich belegtes 30-Tage-Verfahren',
  scheduled_workdays: 'Belegte Sollarbeitstage', scheduled_seconds: 'Belegte Sollarbeitszeit',
};
export const PAYROLL_FACT_STATES = {
  BW:'Baden-Württemberg', BY:'Bayern', BE:'Berlin', BB:'Brandenburg', HB:'Bremen', HH:'Hamburg', HE:'Hessen', MV:'Mecklenburg-Vorpommern',
  NI:'Niedersachsen', NW:'Nordrhein-Westfalen', RP:'Rheinland-Pfalz', SL:'Saarland', SN:'Sachsen', ST:'Sachsen-Anhalt', SH:'Schleswig-Holstein', TH:'Thüringen',
};
export const PAYROLL_ENTITLEMENTS = {
  ordinary_work:'Gewöhnliche Arbeit', public_holiday:'Gesetzlicher Feiertag', vacation:'Urlaub', sickness_continued_pay:'Krankheit mit belegtem Entgeltfortzahlungsanspruch',
  unpaid_leave:'Unbezahlte Freistellung', sickness_after_entitlement:'Krankheit nach Ende des Entgeltanspruchs',
};
export function payrollFactDate(value, optional = false) {
  const result = String(value ?? '').trim();
  if (!result && optional) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(result)) throw fail('Tatsächliches vollständiges Datum angeben.');
  const date = new Date(result + 'T00:00:00Z');
  if (!Number.isFinite(date.valueOf()) || date.toISOString().slice(0, 10) !== result) throw fail('Ein gültiges Kalendertagsdatum angeben.');
  return result;
}
export function payrollFactMonth(value) {
  if (typeof value !== 'string' || !/^2026-(0[1-9]|1[0-2])$/.test(value)) throw fail('Einen belegten Kalendermonat 2026 im Format JJJJ-MM wählen.');
  return value;
}
export function payrollFactSeconds(value) {
  const match = /^(\d{1,2}):([0-5]\d)(?::([0-5]\d))?$/.exec(String(value ?? '').trim());
  if (!match) throw fail('Sollzeit ausdrücklich als Stunden:Minuten angeben, auch bekannte 00:00.');
  const seconds = Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3] || 0);
  if (seconds > 86400) throw fail('Eine Tages-Sollzeit darf 24 Stunden nicht überschreiten.');
  return seconds;
}
export function payrollFactTime(seconds) {
  if (!Number.isSafeInteger(seconds) || seconds < 0 || seconds > 86400) throw fail('Die belegte Sollzeit ist ungültig.');
  const parts = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map(n => String(n).padStart(2, '0'));
  return parts.slice(0, seconds % 60 ? 3 : 2).join(':');
}
export function payrollFactDates(month) {
  payrollFactMonth(month);
  const count = new Date(Number(month.slice(0, 4)), Number(month.slice(5)), 0).getDate();
  return Array.from({length: count}, (_, index) => month + '-' + String(index + 1).padStart(2, '0'));
}
export function payrollFactRef(value) {
  if (!value || !ID.test(value.id || '') || !Number.isSafeInteger(value.revision) || value.revision < 1 || !HASH.test(value.content_hash || '')) throw fail('Eine genaue belegte Quellenfassung auswählen.');
  return {id: value.id, revision: value.revision, content_hash: value.content_hash};
}
export function payrollFactRights(caps) {
  const permissions = new Set(caps?.permissions || []);
  const read = caps?.features?.includes('payroll_period_facts') === true && caps?.capabilities?.includes('business_payroll_facts') === true && permissions.has('personnel.read');
  const writable = read && caps.readonly === false;
  return {read, write: writable && permissions.has('personnel.write'), approve: writable && permissions.has('personnel.approve'),
    enabled: writable && caps.organization?.modules?.personnel?.enabled !== false};
}
export function payrollFactRecord(value, employeeId, kind = null) {
  payrollFactRef(value);
  if (value.employee_id !== employeeId || !Object.hasOwn(PAYROLL_FACT_KINDS, value.kind) || kind && value.kind !== kind ||
      !['active', 'void'].includes(value.status) || !value.details || Array.isArray(value.details) || !value.sources ||
      !HASH.test(value.source_hash || '') || !Array.isArray(value.source_file_ids) || !value.source_file_ids.length ||
      value.source_file_ids.some(id => !ID.test(id)) || new Set(value.source_file_ids).size !== value.source_file_ids.length ||
      (value.kind === 'period_case' ? !value.plan || typeof value.plan !== 'object' || !HASH.test(value.preview_hash || '') : value.plan !== null || value.preview_hash !== null) ||
      (value.revision === 1 ? value.previous_hash !== null : !HASH.test(value.previous_hash || ''))) throw fail('Der Faktennachweis ist nicht eindeutig an Mitarbeiter, Art und ursprüngliche Fassung gebunden.');
  payrollFactDate(value.effective_from); payrollFactDate(value.effective_to, true);
  const dates = value.kind === 'employment_terms' ? [value.details.employment_from, value.details.employment_to] : payrollFactDates(value.details.month);
  if (value.effective_from !== dates[0] || value.effective_to !== dates.at(-1)) throw fail('Der Gültigkeitszeitraum widerspricht den belegten Fakten.');
  return value;
}
export function payrollFactSources(value, employeeId) {
  if (!ID.test(employeeId || '') || !value || value.employee_id !== employeeId || value.employee?.id !== employeeId ||
      !Number.isSafeInteger(value.employee.revision) || value.employee.revision < 1 ||
      ['files', 'agreements', 'preparations', 'profiles', 'identities', 'facts', 'absences'].some(key => !Array.isArray(value[key])) ||
      ['can_write', 'can_approve', 'writes_enabled'].some(key => typeof value[key] !== 'boolean')) throw fail('Die privaten Lohnquellen gehören nicht eindeutig zum gewählten Mitarbeiter.');
  for (const key of ['files', 'agreements', 'preparations', 'profiles', 'identities', 'facts', 'absences']) {
    const ids = new Set();
    for (const item of value[key]) {
      if (item.employee_id !== employeeId || !ID.test(item.id || '') || ids.has(item.id)) throw fail('Eine private Quelle gehört zu einer anderen Person oder ist mehrfach enthalten.');
      ids.add(item.id);
      if (key === 'files') {
        if (item.purpose !== 'personnel' || !HASH.test(item.sha256 || '') || !HASH.test(item.content_hash || '') || !Number.isSafeInteger(item.size) || item.size < 1) throw fail('Ein geschützter Personaloriginalnachweis fehlt.');
      } else if (key === 'absences') {
        if (item.status !== 'approved' || payrollFactDate(item.start_date) > payrollFactDate(item.end_date) || Object.hasOwn(item, 'details')) throw fail('Eine genehmigte Abwesenheitsquelle ist unvollständig oder enthält unnötige private Angaben.');
      } else payrollFactRef(item);
      if (key === 'facts') payrollFactRecord(item, employeeId);
    }
  }
  return value;
}
export async function payrollFactsAuthorize(api, employeeId, kind = null, {replay = false} = {}) {
  const caps = await api.get('/business/capabilities'), rights = payrollFactRights(caps);
  if (!rights.read || kind && !rights[kind === 'period_case' ? 'approve' : 'write']) throw fail('Aktuelle globale Personalrechte für diesen Faktenvorgang fehlen.', 403);
  const sources = payrollFactSources(await api.get('/business/payroll/facts/sources?employee_id=' + employeeId), employeeId);
  if (kind && !sources[kind === 'period_case' ? 'can_approve' : 'can_write']) throw fail('Die aktuelle Freigabe für den Mitarbeiter fehlt.', 403);
  if (kind && !replay && (!rights.enabled || !sources.writes_enabled)) throw fail('Neue Lohnfakten sind im deaktivierten Personalbereich gesperrt.', 423);
  return {caps, rights, sources};
}
export async function payrollFactsPendingAuthorize(api, operation) {
  const match = /^payroll-facts-([a-f0-9]{32})$/.exec(operation?.key || '');
  const body = api.pendingCommandValues(operation?.key, operation?.path);
  if (!match || operation.path !== '/business/payroll/facts' || body?.employee_id !== match[1] || !Object.hasOwn(PAYROLL_FACT_KINDS, body?.kind)) throw fail('Der ursprüngliche private Faktenauftrag ist nicht verfügbar.', 409);
  return payrollFactsAuthorize(api, match[1], body.kind, {replay: true});
}
function selection(items, ids, employeeId, label, {optional = false, kind = null} = {}) {
  if (!Array.isArray(ids) || new Set(ids).size !== ids.length || !optional && !ids.length) throw fail(label + ' ausdrücklich auswählen.');
  return [...ids].sort().map(id => {
    const value = items.find(item => item.id === id && item.employee_id === employeeId && (!kind || item.kind === kind) && item.status !== 'void');
    if (!value) throw fail(label + ' gehört nicht zum aktuellen Mitarbeiterstand.');
    return payrollFactRef(value);
  });
}
export function payrollFactInput(employeeId, sources, kind, values, previous = null) {
  payrollFactSources(sources, employeeId);
  if (!Object.hasOwn(PAYROLL_FACT_KINDS, kind)) throw fail('Unbekannte Lohnfaktenart.');
  const ids = values.source_file_ids;
  if (!Array.isArray(ids) || !ids.length || ids.length > 20 || new Set(ids).size !== ids.length || ids.some(id => !sources.files.some(file => file.id === id))) throw fail('Ein bis zwanzig unterschiedliche geschützte Personaloriginale auswählen.');
  const body = {employee_id: employeeId, employee_revision: sources.employee.revision, kind, revision: previous?.revision || 0, status: 'active', details: {}, source_file_ids: [...ids].sort(), confirmed: true};
  if (previous) {
    payrollFactRecord(previous, employeeId, kind);
    Object.assign(body, {id: previous.id, correction_reason: text(values.correction_reason, 'Korrekturgrund', 1000)});
  }
  if (kind === 'employment_terms') {
    const from = payrollFactDate(values.employment_from), to = payrollFactDate(values.employment_to, true);
    if (to && to < from) throw fail('Das Beschäftigungsende darf nicht vor dem Beginn liegen.');
    if (from !== sources.employee.employment_from || to !== (sources.employee.employment_to || null)) throw fail('Beschäftigungsdaten zuerst mit dem aktuellen Personalstamm abgleichen.');
    if (!Object.hasOwn(PAYROLL_PRORATION, values.proration_method)) throw fail('Die belegte Teilentgeltmethode ausdrücklich wählen.');
    body.details = {employment_from: from, employment_to: to, agreement_refs: selection(sources.agreements, values.agreement_ids, employeeId, 'Entgeltvereinbarungen'), proration_method: values.proration_method, reason: text(values.reason, 'Vertragsgrund')};
  } else if (kind === 'work_schedule') {
    const month = payrollFactMonth(values.month), dates = payrollFactDates(month);
    if (!Array.isArray(values.days) || values.days.length !== dates.length) throw fail('Jeden Kalendertag des Monats einschließlich arbeitsfreier Tage ausdrücklich belegen.');
    const days = values.days.map((day, index) => {
      if (day.date !== dates[index] || !Number.isSafeInteger(day.scheduled_seconds) || day.scheduled_seconds < 0 || day.scheduled_seconds > 86400 || !Object.hasOwn(PAYROLL_FACT_STATES, day.federal_state)) throw fail('Arbeitsplan mit eindeutigen Tagen, Sollzeiten und Bundesländern vervollständigen.');
      return {date: day.date, scheduled_seconds: day.scheduled_seconds, workplace: day.scheduled_seconds ? text(day.workplace, 'Arbeitsort', 500) : String(day.workplace ?? '').trim(), federal_state: day.federal_state};
    });
    body.details = {month, days, reason: text(values.reason, 'Arbeitsplangrund')};
  } else {
    const month = payrollFactMonth(values.month);
    const preparation = selection(sources.preparations, [values.preparation_id], employeeId, 'Monatsvorbereitung')[0];
    if (sources.preparations.find(p => p.id === preparation.id)?.month !== month) throw fail('Die HR-Vorbereitung gehört zu einem anderen Monat.');
    const terms = selection(sources.facts, [values.employment_terms_id], employeeId, 'Beschäftigungsnachweis', {kind: 'employment_terms'})[0];
    const schedule = values.work_schedule_id ? selection(sources.facts, [values.work_schedule_id], employeeId, 'Arbeitsplan', {kind: 'work_schedule'})[0] : null;
    if (schedule && sources.facts.find(f => f.id === schedule.id)?.details.month !== month) throw fail('Der Arbeitsplan gehört zu einem anderen Monat.');
    if (values.tax_treatment !== 'domestic_running_wages') throw fail('Die steuerliche Einordnung ausdrücklich bestätigen.');
    const decisions = values.entitlement_decisions || [];
    if (!Array.isArray(decisions)) throw fail('Anspruchsentscheidungen strukturiert angeben.');
    body.details = {month, preparation_ref: preparation, employment_terms_ref: terms, work_schedule_ref: schedule,
      profile_refs: selection(sources.profiles, values.profile_ids, employeeId, 'Lohnprofile'), identity_refs: selection(sources.identities, values.identity_ids, employeeId, 'Identitätsnachweise'), tax_treatment: values.tax_treatment,
      entitlement_decisions: decisions.map(value => {
        if (!Object.hasOwn(PAYROLL_ENTITLEMENTS, value.kind)) throw fail('Anspruchsart ausdrücklich wählen.');
        const from = payrollFactDate(value.from), to = payrollFactDate(value.to);
        if (from > to || from.slice(0, 7) !== month || to.slice(0, 7) !== month || value.source_absence_id !== null && !ID.test(value.source_absence_id || '')) throw fail('Anspruchszeitraum und Abwesenheitsquelle prüfen.');
        if (value.source_absence_id !== null && !sources.absences.some(item => item.id === value.source_absence_id && item.start_date <= from && item.end_date >= to)) throw fail('Die Anspruchszeit liegt nicht in der gewählten genehmigten Abwesenheit dieses Mitarbeiters.');
        if (!Array.isArray(value.source_file_ids) || !value.source_file_ids.length || new Set(value.source_file_ids).size !== value.source_file_ids.length || value.source_file_ids.some(id => !ids.includes(id))) throw fail('Anspruchsoriginale zusätzlich unter den gesamten Personaloriginalen auswählen.');
        return {kind: value.kind, from, to, source_absence_id: value.source_absence_id, source_file_ids: [...value.source_file_ids].sort(), reason: text(value.reason, 'Anspruchsgrund')};
      }).sort((a, b) => (a.from + a.to + a.kind).localeCompare(b.from + b.to + b.kind)), verification_note: text(values.verification_note, 'Prüfvermerk')};
  }
  return body;
}
export function payrollFactPreviewInput(body) {
  if (body.kind !== 'period_case') throw fail('Eine Periodenvorschau benötigt einen Monatsfall.');
  return copy({employee_id: body.employee_id, employee_revision: body.employee_revision, details: body.details, source_file_ids: body.source_file_ids});
}
export function payrollFactPreview(value, body) {
  const snapshot = value?.source_snapshot, details = body.details;
  if (!value || value.employee_id !== body.employee_id || value.month !== details.month || !HASH.test(value.source_hash || '') || !HASH.test(value.preview_hash || '') ||
      !snapshot || snapshot.schema_version !== 1 || snapshot.employee_id !== body.employee_id || snapshot.month !== details.month || !same(snapshot.case_details, details) ||
      !same(payrollFactRef(snapshot.preparation), details.preparation_ref) || !same(payrollFactRef(snapshot.employment_terms), details.employment_terms_ref) ||
      !same(snapshot.work_schedule === null ? null : payrollFactRef(snapshot.work_schedule), details.work_schedule_ref) ||
      !Array.isArray(snapshot.profiles) || !same(snapshot.profiles.map(payrollFactRef), details.profile_refs) ||
      !Array.isArray(snapshot.identities) || !same(snapshot.identities.map(payrollFactRef), details.identity_refs) ||
      !Array.isArray(snapshot.source_files) || !same(snapshot.source_files.map(f => f.id).sort(), [...body.source_file_ids].sort()) ||
      !value.plan || !Array.isArray(value.plan.blockers) || ['can_confirm', 'can_calculate', 'can_write', 'can_approve', 'writes_enabled'].some(key => typeof value[key] !== 'boolean') ||
      value.can_calculate && (!value.can_confirm || value.plan.blockers.length)) throw fail('Die Periodenvorschau ist nicht an die ausdrücklich ausgewählten Monatsquellen gebunden.');
  for (const source of [...snapshot.profiles, ...snapshot.identities, snapshot.preparation, snapshot.employment_terms, ...snapshot.work_schedule ? [snapshot.work_schedule] : [], ...snapshot.source_files]) {
    if (source.employee_id !== body.employee_id) throw fail('Die Periodenvorschau enthält eine fremde Personalquelle.');
  }
  return value;
}
export function payrollFactValidator(body, previous = null, preview = null) {
  const frozen = copy(body), prior = previous ? copy(previous) : null, proof = preview ? copy(preview) : null;
  return value => {
    payrollFactRecord(value, frozen.employee_id, frozen.kind);
    if (value.revision !== frozen.revision + 1 || frozen.id && value.id !== frozen.id || value.previous_hash !== (prior?.content_hash || null) ||
        value.status !== frozen.status || !same(value.details, frozen.details) || !same(value.source_file_ids, frozen.source_file_ids) || value.correction_reason !== (frozen.correction_reason || '') ||
        frozen.kind === 'period_case' && value.preview_hash !== frozen.preview_hash || frozen.status === 'void' && (!prior || !same(value.sources, prior.sources) || value.source_hash !== prior.source_hash || !same(value.plan, prior.plan)) ||
        proof && (!same(value.sources, proof.source_snapshot) || value.source_hash !== proof.source_hash || !same(value.plan, proof.plan))) throw fail('Die Bestätigung passt nicht zum geprüften Faktenauftrag. Die ursprüngliche Anfrage bleibt erhalten.');
    return value;
  };
}
export function payrollFactRunInput(fact) {
  payrollFactRecord(fact, fact.employee_id, 'period_case');
  if (fact.status !== 'active') throw fail('Ein aufgehobener Monatsfall kann keine neue Abrechnung begründen.');
  if (fact.plan.can_calculate !== true || fact.plan.blockers?.length) throw fail('Der bestätigte Monatsfall ist noch nicht vollständig berechenbar.');
  return {source_schema_version: 2, employee_id: fact.employee_id, period_case_ref: payrollFactRef(fact)};
}

export function payrollFactsUi(h) {
  const {api, biz, el, button, field, form, dialog, panel, notice, table} = h;
  let active = null;
  const action = fn => h.action(fn, active), key = employee => 'payroll-facts-' + employee.id;
  const path = biz('/payroll/facts'), label = ref => 'Fassung ' + ref.revision;
  const available = () => payrollFactRights(h.caps()).read;
  async function fresh(employee, kind = null, replay = false) {
    const stamp = h.stamp(), result = await payrollFactsAuthorize(api, employee.id, kind, {replay});
    if (stamp !== h.stamp() || !available()) throw fail('Die private Ansicht oder Personalberechtigung wurde geändert.', 403);
    return result;
  }
  function show(employee, title, body) {
    if (!available()) throw fail('Aktuelle Personal-Leserechte fehlen.', 403);
    active = body; body.setAttribute('data-payroll-facts', employee.id); body.setAttribute('data-payroll', employee.id);
    dialog(title, body);
  }
  const options = (items, title = item => item.name || item.filename || item.month || item.id) => [['', 'Bitte ausdrücklich auswählen'], ...items.map(item => [item.id, title(item) + ' · ' + (item.revision ? label(item) : 'Original')])];
  function fileFields(sources, previous, extra = []) {
    const superseded = new Set(sources.files.map(file => file.supersedes).filter(Boolean));
    return [field('source_file_ids', 'Geschützte Personaloriginale dieses Nachweises', 'multi', previous?.source_file_ids || [], {required: true, options: sources.files.filter(file => !superseded.has(file.id)).map(file => [file.id, file.filename])}), ...extra,
      ...previous ? [field('correction_reason', 'Nachvollziehbarer Korrekturgrund', 'text', '', {required: true})] : [],
      field('confirmed', 'Ich bestätige die ausdrücklich gewählten Quellen und die belegten Angaben.', 'checkbox', false, {required: true})];
  }
  function basics(value) {
    const rows = [['Stand', value.status === 'active' ? 'Aktiv' : 'Aufgehoben'], ['Gültig ab', h.formatDate(value.effective_from)], ['Gültig bis', value.effective_to ? h.formatDate(value.effective_to) : 'Kein belegtes Ende'], ['Fassung', String(value.revision)]];
    if (value.correction_reason) rows.push(['Korrekturgrund', value.correction_reason]);
    return table(['Nachweis', 'Belegter Wert'], rows);
  }
  function planView(plan) {
    const sections = [];
    for (const [name, heading] of [['employment_intervals', 'Beschäftigung'], ['earnings', 'Entgeltanspruch'], ['tax_periods', 'Steuerzeitraum'], ['social_periods', 'Sozialversicherung']]) {
      const items = plan[name];
      if (Array.isArray(items) && items.length) sections.push(panel(heading, ...items.map(item => detailValue(item))));
    }
    sections.push(panel('Offene Nachweise', ...(plan.blockers?.length ? plan.blockers.map(block => notice(block.explanation || block.message || block.code)) : [notice('Für diesen Periodenplan sind keine offenen Punkte ausgewiesen. Die eigentliche Lohnberechnung wird gesondert geprüft.')])));
    return el('div', {class: 'stack'}, ...sections);
  }
  const names = {start:'Von', end:'Bis', caps:'Beitragsbemessungsgrenzen', full_month:'Vollständiger SV-Monat', inputs:'Steuerliche Eingaben', approved_work_seconds:'Freigegebene Arbeitszeit (Sekunden)', pay_basis:'Vereinbarte Entgeltbasis', from:'Von', to:'Bis', calendar_days:'Kalendertage', tax_days:'Steuertage', sv_days:'SV-Tage', days:'SV-Tage', lzz:'Steuerlicher Lohnzahlungszeitraum', gross_minor:'Belegtes Brutto', cap_minor:'Beitragsbemessungsgrenze', scheduled_seconds:'Sollzeit (Sekunden)', numerator:'Zähler', denominator:'Nenner', proration_method:'Vertragliche Entgeltmethode', ratio:'Belegte Entgeltquote', branches:'Versicherungszweige', health:'Krankenversicherung', care:'Pflegeversicherung', pension:'Rentenversicherung', unemployment:'Arbeitslosenversicherung', reason:'Beleggrund', daily_input_minor:'Tägliche PAP-Eingabe', daily_input_remainder:'Rest der täglichen Eingabe', allowance_input_minor:'PAP-Freibetrag', addition_input_minor:'PAP-Hinzurechnung', minimum_pension_basis_minor:'RV-Mindestbasis', transition_basis:'Übergangsbereichsgrundlage', method:'Methode', kind:'Art'};
  function detailValue(value) {
    if (Array.isArray(value)) return el('div', {class: 'stack'}, ...value.map(detailValue));
    if (value && typeof value === 'object') return table(['Angabe', 'Belegter Wert'], Object.entries(value).filter(([k]) => !['source_ref', 'evidence_refs', 'profile_ref', 'tax_evidence_ref', 'agreement_ref'].includes(k)).map(([k, v]) => [names[k] || k, v && typeof v === 'object' ? detailValue(v) : k.endsWith('_minor') && Number.isSafeInteger(v) ? h.formatMoney((v / 100).toFixed(2)) : k === 'proration_method' ? PAYROLL_PRORATION[v] || v : String(v ?? 'Nicht ermittelt')]));
    return el('span', {}, String(value ?? 'Nicht ermittelt'));
  }
  function detailsView(value) {
    const d = value.details;
    if (value.kind === 'employment_terms') return panel('Belegte Entgeltgrundlage', table(['Angabe', 'Belegter Wert'], [['Beschäftigungsbeginn', h.formatDate(d.employment_from)], ['Beschäftigungsende', d.employment_to ? h.formatDate(d.employment_to) : 'Kein belegtes Ende'], ['Teilentgeltmethode', PAYROLL_PRORATION[d.proration_method]], ['Vertragsgrund', d.reason]]));
    if (value.kind === 'work_schedule') return panel('Arbeitsplan · ' + d.month, el('p', {}, d.reason), table(['Datum', 'Sollzeit', 'Arbeitsort', 'Bundesland'], d.days.map(day => [h.formatDate(day.date), payrollFactTime(day.scheduled_seconds), day.workplace || 'Arbeitsfrei', PAYROLL_FACT_STATES[day.federal_state]])));
    return el('div', {class: 'stack'}, notice(d.verification_note), planView(value.plan));
  }
  async function inspect(employee, value, historical = false) {
    const access = await fresh(employee);
    payrollFactRecord(value, employee.id);
    const body = el('div', {class: 'stack'}, basics(value), detailsView(value));
    for (const id of value.source_file_ids) {
      const file = access.sources.files.find(file => file.id === id) || value.sources?.source_files?.find(file => file.id === id);
      if (file) body.append(button('Personaloriginal: ' + file.filename, () => action(async () => {await fresh(employee); await h.onOriginal(employee, file);}), 'small'));
    }
    if (!historical) body.append(button('Faktenhistorie öffnen', () => action(async () => {
      await fresh(employee); const stamp = h.stamp(), page = await api.get(biz('/payroll/facts/' + value.id + '/history'));
      if (stamp !== h.stamp()) return;
      if (page.employee_id !== employee.id || !Array.isArray(page.items) || page.items.some((item, index) => payrollFactRecord(item, employee.id, value.kind).id !== value.id || item.revision !== index + 1)) throw fail('Die Historie gehört nicht zum ausgewählten Faktennachweis.');
      show(employee, 'Faktenhistorie · ' + PAYROLL_FACT_KINDS[value.kind], el('div', {class: 'stack'}, ...page.items.map(item => panel('Fassung ' + item.revision, basics(item), button('Diese historische Fassung öffnen', () => action(() => inspect(employee, item, true)), 'small')))));
    }), 'small'));
    const permitted = value.kind === 'period_case' ? access.rights.approve && access.sources.can_approve : access.rights.write && access.sources.can_write;
    if (!historical && permitted && access.sources.writes_enabled && !api.pendingCommandValues(key(employee), path)) {body.append(button('Nachweis korrigieren', () => action(() => edit(employee, value.kind, value)), 'small')); if (value.status === 'active') body.append(button('Fälschlichen Nachweis aufheben', () => action(() => cancel(employee, value)), 'small'));}
    if (value.kind === 'period_case' && value.status === 'active' && value.plan.can_calculate === true && !value.plan.blockers?.length && access.rights.read && h.onCalculate) body.append(button('Lohn aus diesem Fall berechnen', () => action(async () => {await fresh(employee); await h.onCalculate(employee, value);}), 'primary'));
    show(employee, (historical ? 'Historischer Nachweis · ' : '') + PAYROLL_FACT_KINDS[value.kind], body);
  }
  async function save(employee, body, previous, preview = null) {
    const pending = api.pendingCommandValues(key(employee), path);
    if (pending && !same(pending, body)) throw fail('Zuerst den unbestätigten ursprünglichen Faktenauftrag unverändert klären.', 409);
    await fresh(employee, body.kind, !!pending);
    const result = pending ? await api.retry(key(employee)) : await api.mutate(key(employee), path, body, {validate: payrollFactValidator(body, previous, preview)});
    await fresh(employee); await inspect(employee, result);
    return result;
  }
  async function confirm(employee, body, previous) {
    const stamp = h.stamp(), preview = payrollFactPreview(await api.post(biz('/payroll/periods/preview'), payrollFactPreviewInput(body)), body);
    if (stamp !== h.stamp()) return;
    await fresh(employee);
    const full = {...body, preview_hash: preview.preview_hash};
    const view = el('div', {class: 'stack'}, notice(preview.can_calculate ? 'Der bestätigte Periodenplan kann anschließend als Quelle einer gesonderten Lohnberechnung gewählt werden.' : 'Dieser Nachweis ist noch nicht vollständig berechenbar. Die offenen Punkte bleiben auch nach dem Speichern bestehen.'), planView(preview.plan));
    if (preview.can_confirm && preview.can_approve && preview.writes_enabled) view.append(form('', [field('accepted', 'Ich bestätige genau diesen geprüften Periodenplan und seine Quellen.', 'checkbox', false, {required: true})], async values => {if (!values.accepted) throw fail('Den geprüften Periodenplan ausdrücklich bestätigen.'); await save(employee, full, previous, preview); return undefined;}, {key: 'payroll-facts-confirm-' + employee.id, submit: 'Geprüften Fallnachweis festhalten'}));
    else view.append(notice('Die aktuelle Freigabe oder die gebundene Quellenlage erlaubt keine Bestätigung.'));
    show(employee, 'Periodenplan prüfen · ' + preview.month, view);
  }
  async function cancel(employee, previous) {
    await fresh(employee, previous.kind);
    if (api.pendingCommandValues(key(employee), path)) return open(employee);
    show(employee, 'Fälschlichen Faktennachweis aufheben', form('', [field('correction_reason', 'Belegter Grund für die Aufhebung', 'text', '', {required: true}), field('confirmed', 'Ich bestätige die Aufhebung dieses Nachweises; historische Abrechnungen bleiben unverändert.', 'checkbox', false, {required: true})], async values => {
      if (values.confirmed !== true) throw fail('Die belegte Aufhebung ausdrücklich bestätigen.');
      const current = await fresh(employee, previous.kind), body = {employee_id: employee.id, employee_revision: current.sources.employee.revision, kind: previous.kind, revision: previous.revision, id: previous.id, status: 'void', details: copy(previous.details), source_file_ids: [...previous.source_file_ids], confirmed: true, correction_reason: text(values.correction_reason, 'Aufhebungsgrund', 1000), ...(previous.kind === 'period_case' ? {preview_hash: previous.preview_hash} : {})};
      await save(employee, body, previous); return undefined;
    }, {key: 'payroll-facts-void-' + employee.id, submit: 'Aufhebung belegt festhalten', extra: detailsView(previous)}));
  }
  async function edit(employee, kind, previous = null) {
    const access = await fresh(employee, kind), sources = access.sources, d = previous?.details || {};
    if (api.pendingCommandValues(key(employee), path)) return open(employee);
    if (kind === 'work_schedule') return schedule(employee, sources, previous);
    const fields = kind === 'employment_terms' ? [
      field('employment_from', 'Belegter Beschäftigungsbeginn', 'date', d.employment_from || '', {required: true}), field('employment_to', 'Belegtes Beschäftigungsende, falls vorhanden', 'date', d.employment_to || ''),
      field('agreement_ids', 'Gültige Entgeltvereinbarungen', 'multi', (d.agreement_refs || []).map(ref => ref.id), {required: true, options: sources.agreements.map(item => [item.id, h.formatDate(item.effective_from) + ' · ' + label(item)])}),
      field('proration_method', 'Vertraglich belegte Teilentgeltmethode', 'select', d.proration_method || '', {required: true, options: [['', 'Methode ausdrücklich auswählen'], ...Object.entries(PAYROLL_PRORATION)]}), field('reason', 'Vertragliche Grundlage der Entgeltaufteilung', 'text', d.reason || '', {required: true}),
    ] : [
      field('month', 'Belegter Abrechnungsmonat (JJJJ-MM)', 'text', d.month || '', {required: true}),
      field('preparation_id', 'Abgeschlossene HR-Monatsvorbereitung', 'select', d.preparation_ref?.id || '', {required: true, options: options(sources.preparations, item => item.month)}),
      field('employment_terms_id', 'Belegter Beschäftigungsnachweis', 'select', d.employment_terms_ref?.id || '', {required: true, options: options(sources.facts.filter(item => item.kind === 'employment_terms' && item.status === 'active'), item => h.formatDate(item.effective_from))}),
      field('work_schedule_id', 'Datierter Arbeitsplan, falls für die Methode erforderlich', 'select', d.work_schedule_ref?.id || '', {options: options(sources.facts.filter(item => item.kind === 'work_schedule' && item.status === 'active'), item => item.details.month)}),
      field('profile_ids', 'Alle einschlägigen gültigen Lohnprofile', 'multi', (d.profile_refs || []).map(ref => ref.id), {required: true, options: sources.profiles.map(item => [item.id, h.formatDate(item.profile.effective_from) + ' · ' + label(item)])}),
      field('identity_ids', 'Alle einschlägigen Lohnkonto-Stammnachweise', 'multi', (d.identity_refs || []).map(ref => ref.id), {required: true, options: sources.identities.map(item => [item.id, 'Stammnachweis · ' + label(item)])}),
      field('tax_treatment', 'Belegte steuerliche Einordnung', 'select', d.tax_treatment || '', {required: true, options: [['', 'Bitte ausdrücklich auswählen'], ['domestic_running_wages', 'Inländischer laufender Arbeitslohn']]}),
      field('verification_note', 'Prüfvermerk zu Beschäftigung, Merkmalen und Anspruch', 'text', d.verification_note || '', {required: true}),
    ];
    const decisions = kind === 'period_case' ? decisionEditor(sources, d.entitlement_decisions || []) : null;
    show(employee, (previous ? 'Korrigieren: ' : 'Erfassen: ') + PAYROLL_FACT_KINDS[kind], form('', [...fields, ...fileFields(sources, previous)], async values => {
      if (values.confirmed !== true) throw fail('Die belegten Quellen und Angaben ausdrücklich bestätigen.');
      await fresh(employee, kind);
      const body = payrollFactInput(employee.id, sources, kind, {...values, ...(decisions ? {entitlement_decisions: decisions.values()} : {})}, previous);
      if (kind === 'period_case') await confirm(employee, body, previous); else await save(employee, body, previous);
      return undefined;
    }, {key: 'payroll-facts-edit-' + employee.id, submit: kind === 'period_case' ? 'Periodenplan unverbindlich prüfen' : 'Belegten Nachweis speichern', extra: decisions?.node || notice('Beschäftigungsdaten im aktuellen Personalstamm: ' + (sources.employee.employment_from ? h.formatDate(sources.employee.employment_from) : 'Beginn nicht belegt') + ' bis ' + (sources.employee.employment_to ? h.formatDate(sources.employee.employment_to) : 'kein belegtes Ende'))}));
  }
  function decisionEditor(sources, previous) {
    const node = el('div', {class: 'stack'}, el('h3', {}, 'Belegte Anspruchs- und Unterbrechungsfälle')), entries = [];
    function add(value = {}) {
      const group = el('fieldset', {class: 'panel'}), controls = {}, index = entries.length + 1;
      group.append(el('legend', {}, 'Anspruchsfall ' + index));
      for (const [name, title, choices] of [['kind', 'Anspruchsart', Object.entries(PAYROLL_ENTITLEMENTS)], ['source_absence_id', 'Genehmigte Abwesenheitsquelle, falls vorhanden', (sources.absences || []).map(item => [item.id, h.formatDate(item.start_date) + ' – ' + h.formatDate(item.end_date) + ' · ' + item.kind])]]) {
        controls[name] = el('select', {'aria-label': title + ' ' + index, required: name === 'kind'}, el('option', {value: ''}, 'Bitte ausdrücklich auswählen'), ...choices.map(([id, label]) => el('option', {value: id, selected: value[name] === id}, label))); group.append(el('label', {}, title, controls[name]));
      }
      for (const [name, title, type] of [['from', 'Anspruch von', 'date'], ['to', 'Anspruch bis', 'date'], ['reason', 'Belegter Anspruchsgrund', 'text']]) {
        controls[name] = el('input', {type, value: value[name] || '', required: true, 'aria-label': title + ' ' + index}); group.append(el('label', {}, title, controls[name]));
      }
      const checkboxes = sources.files.map(file => {const input = el('input', {type: 'checkbox', value: file.id, checked: (value.source_file_ids || []).includes(file.id)});group.append(el('label', {}, input, file.filename));return input;});
      const entry = {group, controls, checkboxes}; entries.push(entry);
      group.append(button('Diesen ungespeicherten Anspruch entfernen', () => {entries.splice(entries.indexOf(entry), 1);group.remove();}, 'small'));
      node.insertBefore(group, addButton);
    }
    const addButton = button('Anspruchsfall hinzufügen', () => add(), 'small'); node.append(notice('Kein Anspruchsfall wird automatisch aus Zeitangaben abgeleitet. Bereits genehmigte Abwesenheiten bleiben als Quelle prüfpflichtig.'), addButton);
    previous.forEach(add);
    return {node, values: () => entries.map(({controls, checkboxes}) => ({...Object.fromEntries(Object.entries(controls).map(([k, v]) => [k, k === 'source_absence_id' ? v.value || null : v.value])), source_file_ids: checkboxes.filter(v => v.checked).map(v => v.value)}))};
  }
  async function schedule(employee, sources, previous = null) {
    async function days(month) {
      const dates = payrollFactDates(month), previousDays = previous?.details?.month === month ? previous.details.days : [], controls = [];
      const editor = el('div', {class: 'stack'}, notice('Jeden Tag ausdrücklich prüfen. Auch bekannte arbeitsfreie Tage brauchen 00:00 und die belegte Feiertagsregion.'));
      for (const date of dates) {
        const old = previousDays.find(day => day.date === date), row = el('fieldset', {class: 'panel'}, el('legend', {}, h.formatDate(date)));
        const time = el('input', {type: 'text', value: old ? payrollFactTime(old.scheduled_seconds) : '', required: true, placeholder: 'HH:MM', 'aria-label': 'Sollzeit ' + date});
        const workplace = el('input', {type: 'text', value: old?.workplace || '', 'aria-label': 'Arbeitsort ' + date});
        const state = el('select', {required: true, 'aria-label': 'Bundesland ' + date}, el('option', {value: ''}, 'Region ausdrücklich wählen'), ...Object.entries(PAYROLL_FACT_STATES).map(([id, name]) => el('option', {value: id, selected: old?.federal_state === id}, name)));
        row.append(el('label', {}, 'Sollzeit (HH:MM)', time), el('label', {}, 'Arbeitsort', workplace), el('label', {}, 'Feiertagsregion', state)); editor.append(row); controls.push({date, time, workplace, state});
      }
      show(employee, 'Datierter Arbeitsplan · ' + month, form('', [field('reason', 'Beleggrund des vollständigen Arbeitsplans', 'text', previous?.details?.reason || '', {required: true}), ...fileFields(sources, previous)], async values => {
        if (values.confirmed !== true) throw fail('Den vollständig belegten Arbeitsplan ausdrücklich bestätigen.');
        await fresh(employee, 'work_schedule'); const body = payrollFactInput(employee.id, sources, 'work_schedule', {...values, month, days: controls.map(row => ({date: row.date, scheduled_seconds: payrollFactSeconds(row.time.value), workplace: row.workplace.value, federal_state: row.state.value}))}, previous);
        await save(employee, body, previous); return undefined;
      }, {key: 'payroll-facts-schedule-' + employee.id, submit: 'Belegten Arbeitsplan speichern', extra: editor}));
    }
    if (previous) return days(previous.details.month);
    show(employee, 'Arbeitsplanmonat wählen', form('', [field('month', 'Belegter Kalendermonat (JJJJ-MM)', 'text', '', {required: true})], async values => {await days(payrollFactMonth(values.month)); return undefined;}, {key: 'payroll-facts-month-' + employee.id, submit: 'Datierte Tage einzeln belegen'}));
  }
  async function open(employee) {
    const access = await fresh(employee), sources = access.sources, pending = api.pendingCommandValues(key(employee), path);
    const body = el('div', {class: 'stack'}, notice('Belegte Beschäftigung, Entgeltvereinbarungen, Arbeitspläne und Monatsfälle. Gesetzliche Steuer- und SV-Tage werden aus den Quellen berechnet. Hier wird weder gezahlt noch amtlich gemeldet.'));
    if (pending) body.append(panel('Faktenbestätigung noch offen', notice('Dieser Auftrag kann bereits gespeichert sein. Nur die ursprünglichen Angaben mit derselben Anfragekennung erneut prüfen.'), button('Ursprünglichen Faktenauftrag erneut senden', () => action(async () => {await fresh(employee, pending.kind, true);await api.retry(key(employee));await open(employee);}), 'primary')));
    for (const [kind, title] of Object.entries(PAYROLL_FACT_KINDS)) {
      const items = sources.facts.filter(value => value.kind === kind), allowed = kind === 'period_case' ? access.rights.approve && sources.can_approve : access.rights.write && sources.can_write;
      body.append(panel(title, ...items.map(value => panel((value.details.month || h.formatDate(value.effective_from)) + ' · ' + label(value), notice(value.status === 'void' ? 'Nachweis aufgehoben; Historie bleibt erhalten.' : 'Belegter aktiver Nachweis'), button('Nachweis öffnen', () => action(() => inspect(employee, value)), 'small'))), !items.length ? notice('Noch kein belegter Nachweis.') : null,
        allowed && sources.writes_enabled && !pending ? button(title + ' erfassen', () => action(() => edit(employee, kind)), 'primary') : null));
    }
    if (!sources.writes_enabled) body.append(notice('Das Personalmodul ist deaktiviert. Historische Nachweise und die Klärung bereits angenommener Originalaufträge bleiben zugänglich.'));
    show(employee, 'Lohnzeitachsen und Teilmonate · ' + employee.name, body);
  }
  return {available, open, edit, inspect};
}

export function payrollPeriodCalculation(value) {
  const detail = value?.period_details, complete = value?.scope !== 'unsupported';
  if (value?.rule_version !== 'de_2026_periods_pap_v4' || !detail || !HASH.test(detail.plan_hash || '') || !HASH.test(detail.source_snapshot_hash || '') ||
      ['employment_intervals','earnings','tax_periods','social_periods'].some(key => !Array.isArray(detail[key]) || complete && !detail[key].length)) throw fail('Die Teilmonatsberechnung besitzt keine vollständige Quellen- und Periodenbindung.');
  payrollFactMonth(value.month);
  for (const group of ['employment_intervals','tax_periods','social_periods']) for (const period of detail[group]) {
    payrollFactDate(period.start); payrollFactDate(period.end);
    if (period.start > period.end || period.start.slice(0,7) !== value.month || period.end.slice(0,7) !== value.month) throw fail('Ein Teilzeitraum gehört nicht zum Abrechnungsmonat.');
  }
  for (const period of detail.social_periods) {
    if (!Number.isSafeInteger(period.days) || period.days < 0 || period.days > 30 || complete && period.days === 0 || typeof period.full_month !== 'boolean' || ['health_minor','care_minor','pension_minor','unemployment_minor'].some(key => !Number.isSafeInteger(period.caps?.[key]) || period.caps[key] < 0)) throw fail('SV-Tage und Teil-Bemessungsgrenzen sind nicht eindeutig belegt.');
  }
  for (const period of detail.tax_periods) if (![2,4].includes(period.lzz) || !Number.isSafeInteger(period.tax_days) || period.tax_days < 1 || period.tax_days > 31) throw fail('Der steuerliche Lohnzahlungszeitraum ist nicht eindeutig belegt.');
  if (complete && detail.earnings.reduce((sum, item) => sum + (Number.isSafeInteger(item.gross_minor) && item.gross_minor >= 0 ? item.gross_minor : NaN), 0) !== value.gross_minor) throw fail('Die belegten Entgeltpositionen stimmen nicht mit dem Brutto überein.');
  if (complete && value.scope.startsWith('regular_')) {
    const tax = detail.tax_calculation, care = detail.care_adjustments;
    if (!tax || tax.totals?.LSTLZZ !== value.individual_wage_tax_minor || tax.totals?.SOLZLZZ !== value.solidarity_minor || !care || ['employee_before_adjustments_minor','childless_surcharge_minor','children_discount_minor'].some(key => !Number.isSafeInteger(care[key]) || care[key] < 0) || care.employee_before_adjustments_minor + care.childless_surcharge_minor - care.children_discount_minor !== value.employee_contributions.care) throw fail('Tagessteuern und PV-Anpassungen passen nicht zur Beitragsaufstellung.');
    for (const key of ['health_general','health_additional','pension','unemployment','care']) {
      const b = detail.branch_bases?.[key];
      if (!b || !Number.isSafeInteger(b.total_minor) || !Number.isSafeInteger(b.employee_minor) || b.total_minor < b.employee_minor || b.employee_minor < 0) throw fail('Die getrennten Teilmonats-Beitragsgrundlagen sind unvollständig.');
    }
  }
  if (value.scope === 'regular_transition_period') {
    const t = detail.transition;
    if (!t || !['within_transition_area','below_or_at_lower_limit','above_upper_limit'].includes(t.regime) || !Number.isSafeInteger(t.regular_monthly_gross_minor) || t.regular_monthly_gross_minor < 60301 || t.regular_monthly_gross_minor > 200000 || !same(t.branch_bases, detail.branch_bases) || !same(t.ratio, detail.social_periods[0].transition_ratio)) throw fail('Die Teilmonatsprognose ist nicht an die belegte Entgeltquote gebunden.');
  }
  return detail;
}
export function payrollPeriodSource(value, input) {
  const source = value?.source, calculation = value?.calculation, fact = source?.period_case;
  payrollFactRecord(fact, input.employee_id, 'period_case');
  payrollPeriodCalculation(calculation);
  if (source.source_schema_version !== 2 || !same(source.input, input) || !same(payrollFactRef(fact), input.period_case_ref) || source.employee_id !== input.employee_id || fact.status !== 'active' ||
      source.month !== fact.details.month || calculation.month !== source.month || !same(source.preparation, fact.sources.preparation) ||
      !fact.sources.profiles.some(profile => same(profile, source.profile) && same(payrollFactRef(profile), fact.plan.selected_profile_ref)) ||
      calculation.period_details.plan_hash !== fact.plan.plan_hash || calculation.period_details.source_snapshot_hash !== fact.source_hash || calculation.gross_minor !== fact.plan.gross_minor || value.can_finalize !== calculation.payroll_calculation_complete) throw fail('Die neue Lohnvorschau gehört nicht zum bestätigten ursprünglichen Monatsfall.');
  return value;
}
