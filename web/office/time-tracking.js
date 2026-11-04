/* Read original clock events and append an explicitly approved time correction. */
const ID = /^[a-f0-9]{32}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const ACTIONS = {start: 'Arbeitsbeginn', pause: 'Pause begonnen', resume: 'Arbeit fortgesetzt', stop: 'Arbeitsende'};

function invalid(message) { const error = new Error(message); error.status = 502; return error; }

export function timeEntry(value, expected) {
  if (!value || !ID.test(value.id || '') || value.id !== expected.id ||
      value.project_id !== expected.project_id || value.employee_id !== expected.employee_id ||
      !Number.isSafeInteger(value.worked_seconds) || value.worked_seconds < 0 ||
      !Array.isArray(value.events) || !Array.isArray(value.corrections) ||
      !Array.isArray(value.work_dates) || !Array.isArray(value.approved_work_dates) ||
      value.work_dates.some(day => !DAY.test(day)) ||
      value.approved_work_dates.some(day => !value.work_dates.includes(day)))
    throw invalid('Der Zeiteintrag konnte nicht eindeutig gelesen werden.');
  return value;
}

export function timeCorrectionInput(entry, values) {
  const minutes = values.delta_minutes;
  if (!['approved', 'partially_approved'].includes(entry.status) ||
      !entry.approved_work_dates?.includes(values.work_date))
    throw new Error('Einen freigegebenen Arbeitstag dieses Zeiteintrags wählen.');
  if (!Number.isSafeInteger(minutes) || minutes === 0 || Math.abs(minutes) > 1440)
    throw new Error('Die Änderung muss zwischen −1440 und +1440 ganzen Minuten liegen und darf nicht null sein.');
  if (typeof values.reason !== 'string' || !values.reason.trim() || values.reason.trim().length > 2000)
    throw new Error('Die Korrektur mit höchstens 2000 Zeichen begründen.');
  if (values.confirmed !== true) throw new Error('Die Zeitkorrektur ausdrücklich bestätigen.');
  return {work_date: values.work_date, delta_seconds: minutes * 60, reason: values.reason.trim()};
}

export function timeCorrectionReceipt(value, entryId, body, actorId) {
  if (!value || !ID.test(value.id || '') || value.entry_id !== entryId ||
      value.work_date !== body.work_date || value.delta_seconds !== body.delta_seconds ||
      value.reason !== body.reason || value.created_by !== actorId ||
      !Number.isFinite(Date.parse(value.created_at)))
    throw invalid('Die Bestätigung passt nicht zur gesendeten Zeitkorrektur. Die ursprüngliche Anfrage bleibt offen.');
  return value;
}

export function timeCorrectionAllowed(capabilities) {
  return capabilities?.readonly === false && capabilities.permissions?.includes('time.approve') === true &&
    capabilities.capabilities?.includes('business_time') === true &&
    capabilities.organization?.modules?.personnel?.enabled !== false &&
    (!Array.isArray(capabilities.active_capabilities) || capabilities.active_capabilities.includes('business_time'));
}

export function timeCorrectionLabel(seconds) {
  if (!Number.isSafeInteger(seconds)) throw invalid('Ungültige Zeitkorrektur.');
  const sign = seconds > 0 ? '+' : seconds < 0 ? '−' : '';
  return `${sign}${Math.abs(seconds % 60 === 0 ? seconds / 60 : seconds)} ${seconds % 60 === 0 ? 'Min.' : 'Sek.'}`;
}

export function timeTrackingUi(ui) {
  const {api, biz, query, el, button, panel, notice, table, field, form, dialog, action, mutation, formatDate, duration} = ui;
  const active = stamp => stamp === ui.stamp() && ui.allowed();

  function history(entry) {
    return panel('Original und Korrekturverlauf',
      el('p', {}, `Projekt: ${ui.projectName(entry.project_id)}`),
      el('p', {}, `Gestempelte Arbeitszeit: ${duration(entry.worked_seconds)} · Pause: ${duration(entry.break_seconds || 0)}`),
      notice('Die ursprünglichen Stempelzeiten bleiben erhalten. Korrekturen ändern die freigegebene Zeit und werden zusätzlich protokolliert.'),
      table(['Originalereignis', 'Zeitpunkt'], entry.events.map(event => [ACTIONS[event.action] || event.action, formatDate(event.occurred_at, true)])),
      entry.corrections.length ? el('div', {class: 'list'}, entry.corrections.map(correction =>
        el('article', {class: 'list-row'}, el('div', {class: 'body'},
          el('h3', {}, `${formatDate(correction.work_date)} · ${timeCorrectionLabel(correction.delta_seconds)}`),
          el('p', {}, correction.reason),
          el('p', {class: 'caption'}, `Erfasst am ${formatDate(correction.created_at, true)}`)))))
        : el('p', {class: 'muted'}, 'Noch keine Zeitkorrekturen.'));
  }

  async function correct(entry) {
    if (!ui.writable()) return;
    const key = `time-correction-${entry.id}`, path = `/time/entries/${entry.id}/correct`;
    const pending = api.pendingCommandValues(key, biz(path));
    let stamp, editor;
    const freezePending = () => {
      const waiting = api.pendingCommandValues(key, biz(path));
      if (waiting) {
        for (const {input} of editor.controls.values()) input.disabled = true;
        editor.querySelector('button[type="submit"]').textContent = 'Dieselbe Zeitkorrektur erneut senden';
      }
    };
    editor = form('', [
      field('work_date', 'Freigegebener Arbeitstag', 'select', pending?.work_date || entry.approved_work_dates[0],
        {required: true, options: entry.approved_work_dates.map(day => [day, formatDate(day)])}),
      field('delta_minutes', 'Änderung in Minuten', 'integer', pending ? pending.delta_seconds / 60 : '',
        {required: true, min: -1440, max: 1440, help: 'Zum Beispiel −30 zum Abziehen oder 15 zum Ergänzen. Der bestehende Zeiteintrag wird nicht überschrieben.'}),
      field('reason', 'Begründung der Zeitkorrektur', 'textarea', pending?.reason || '', {required: true, maxLength: 2000}),
      field('confirmed', 'Ich habe den Originaleintrag und die Zeitänderung geprüft.', 'checkbox', !!pending, {required: true}),
    ], async values => {
      if (!active(stamp)) return;
      if (!ui.writable()) throw new Error('Zeitkorrekturen sind aktuell nicht freigegeben.');
      const caps = await api.get(query(biz('/capabilities'), {project_id: entry.project_id}));
      if (!active(stamp)) return;
      if (!timeCorrectionAllowed(caps)) throw new Error('Keine aktuelle Schreibfreigabe für diese Zeitkorrektur.');
      const original = api.pendingCommandValues(key, biz(path));
      const body = original || timeCorrectionInput(entry, values);
      try {
        const result = await mutation(key, path, body, {validate: value => timeCorrectionReceipt(value, entry.id, body, ui.userId())});
        return active(stamp) ? result : undefined;
      } catch (error) { freezePending(); throw error; }
    }, {key, submit: pending ? 'Dieselbe Zeitkorrektur erneut senden' : 'Zeitkorrektur speichern', extra: history(entry),
      description: pending ? 'Die ursprüngliche Antwort ist noch unklar. Nur die unveränderte Zeitkorrektur wird erneut gesendet.' : 'Die Änderung betrifft genau den ausgewählten freigegebenen Tag und bleibt im Verlauf nachvollziehbar.'});
    dialog('Freigegebene Zeit korrigieren', editor);
    stamp = ui.stamp();
    freezePending();
  }

  async function open(expected) {
    const stamp = ui.stamp();
    if (!ui.allowed()) return;
    const entry = timeEntry(await api.get(biz('/time/entries/' + expected.id)), expected);
    if (!active(stamp)) return;
    dialog('Zeiteintrag prüfen', el('div', {class: 'stack'}, history(entry),
      ['approved', 'partially_approved'].includes(entry.status) && entry.approved_work_dates.length && ui.writable()
        ? button('Freigegebene Zeit korrigieren', () => action(() => correct(entry)), 'primary')
        : notice(entry.approved_work_dates.length ? 'Für Zeitkorrekturen ist die Freigabeberechtigung erforderlich.' : 'Zeitkorrekturen sind nach der Tagesfreigabe verfügbar.')));
  }
  return {open};
}
