/* Existing maintenance contracts and their immutable scheduling history. */
const identifier = value => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
const fields = ['asset_id', 'title', 'anchor_date', 'interval_unit', 'interval_count', 'active', 'notes', 'media_ids'];
function bound(item, projectId) {
  if (!identifier(item?.id) || item.project_id !== projectId || !Number.isSafeInteger(item.revision) || item.revision < 1)
    throw new Error('Den aktuellen Wartungsvertrag im richtigen Projekt laden.');
  return item;
}
export function maintenanceContractValues(projectId, previous, values) {
  if (!identifier(projectId)) throw new Error('Ein konkretes Projekt auswählen.');
  if (previous) bound(previous, projectId);
  const result = {project_id: projectId, asset_id: values.asset_id, title: String(values.title || '').trim(),
    anchor_date: values.anchor_date, interval_unit: values.interval_unit, interval_count: values.interval_count,
    active: values.active, notes: String(values.notes || '').trim(), media_ids: [...(previous?.media_ids || [])]};
  if (!identifier(result.asset_id) || !result.title || result.title.length > 300 ||
      !['days', 'months'].includes(result.interval_unit) || !Number.isSafeInteger(result.interval_count) ||
      result.interval_count < 1 || result.interval_count > (result.interval_unit === 'months' ? 120 : 3660) ||
      typeof result.active !== 'boolean' || result.notes.length > 10000)
    throw new Error('Anlage, Bezeichnung, Intervall und Aktivierung vollständig prüfen.');
  const date = new Date(result.anchor_date + 'T00:00:00Z');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(result.anchor_date || '') || !Number.isFinite(date.getTime()) ||
      date.toISOString().slice(0, 10) !== result.anchor_date)
    throw new Error('Eine gültige erste Fälligkeit angeben.');
  if (previous) result.revision = previous.revision;
  return result;
}
export function maintenanceContractReceipt(path, body, result) {
  const match = /^\/business\/maintenance\/contracts(?:\/([a-f0-9]{32}))?$/.exec(path);
  if (!match || !identifier(result?.id) || result.project_id !== body.project_id ||
      match[1] && result.id !== match[1] || result.revision !== (body.revision || 0) + 1 ||
      fields.some(field => JSON.stringify(result[field]) !== JSON.stringify(body[field])))
    throw new Error('Die Antwort bestätigt die ursprüngliche Wartungsvertragsfassung nicht.');
  return result;
}
export async function maintenanceContractAuthorize(api, projectId, contractId = null) {
  if (!identifier(projectId) || contractId !== null && !identifier(contractId))
    throw new Error('Der Wartungsvertrag hat keine eindeutige Projektbindung.');
  const generation = api.generation;
  const caps = await api.get('/business/capabilities?project_id=' + projectId);
  if (generation !== api.generation) throw new Error('Die Sitzung wurde geändert.');
  if (caps.readonly !== false || !caps.capabilities?.includes('business_maintenance') ||
      !['documents.read', 'projects.manage'].every(value => caps.permissions?.includes(value))) {
    const error = new Error('Aktuelle Projekt- und Wartungsrechte fehlen. Der Originalauftrag bleibt erhalten.');
    error.status = 403; throw error;
  }
  if (!contractId) return null;
  const item = await api.get('/business/maintenance/contracts/' + contractId + '?project_id=' + projectId);
  if (generation !== api.generation) throw new Error('Die Sitzung wurde geändert.');
  if (item?.id !== contractId) throw new Error('Die Antwort gehört zu einem anderen Wartungsvertrag.');
  return bound(item, projectId);
}
export async function maintenanceContractPendingAuthorize(api, operation) {
  const values = api.pendingCommandValues(operation?.key, operation?.path);
  const match = /^\/business\/maintenance\/contracts(?:\/([a-f0-9]{32}))?$/.exec(operation?.path || '');
  if (!values || !match) throw new Error('Der ursprüngliche Wartungsvertragsauftrag fehlt.');
  return maintenanceContractAuthorize(api, values.project_id, match[1] || null);
}

export function maintenanceContractsUi(h) {
  const {api, field, form, dialog, el, notice, button} = h;
  async function edit(projectId, assets, contractId = null) {
    if (!h.available(projectId)) return;
    const opening = h.stamp();
    const previous = await maintenanceContractAuthorize(api, projectId, contractId);
    if (opening !== h.stamp() || !h.available(projectId)) return;
    const key = 'maintenance-contract-' + (contractId || projectId);
    const path = '/business/maintenance/contracts' + (contractId ? '/' + contractId : '');
    const pending = () => api.pendingOperations().some(item => item.key === key && item.path === path);
    const original = api.pendingCommandValues(key, path), current = original || previous || {};
    const choices = assets.map(item => [item.id, item.name]);
    if (current.asset_id && !choices.some(item => item[0] === current.asset_id))
      choices.push([current.asset_id, 'Bisherige Anlage']);
    let box, opened, originalOnly = original !== null;
    const live = () => opened === h.stamp() && h.available(projectId) && box.isConnected;
    const lock = () => {
      if (!pending()) return;
      originalOnly = true;
      box.querySelectorAll('input,select,textarea,button[type="button"]').forEach(node => node.disabled = true);
      box.querySelectorAll('form > :not(.form-actions):not(.form-error)').forEach(node => node.hidden = true);
      if (!box.querySelector('[data-maintenance-pending]'))
        box.prepend(el('div', {'data-maintenance-pending': 'true'},
          notice('Antwort offen. Erneut prüfen übermittelt ausschließlich den ursprünglichen Auftrag.'),
          el('pre', {}, JSON.stringify(api.pendingCommandValues(key, path), null, 2))));
      box.querySelector('button[type="submit"]').textContent = 'Ursprüngliche Antwort erneut prüfen';
    };
    box = form('', [
      field('asset_id', 'Anlage', 'select', current.asset_id || '', {options: choices, required: true}),
      field('title', 'Vertragsbezeichnung', 'text', current.title || '', {required: true, maxLength: 300}),
      field('anchor_date', 'Erste Fälligkeit', 'date', current.anchor_date || h.today(), {required: true}),
      field('interval_unit', 'Intervalltyp', 'select', current.interval_unit || 'months', {options: [['months', 'Kalendermonate'], ['days', 'Tage']]}),
      field('interval_count', 'Intervall', 'integer', current.interval_count ?? 12, {required: true, min: 1, max: 3660}),
      field('active', 'Aktiv', 'checkbox', current.active ?? true),
      field('notes', 'Vertragshinweise', 'textarea', current.notes || ''),
    ], async values => {
      if (!live()) return undefined;
      try {
        // Another view may already have received this exact original receipt.
        // A locked retry form must never become a fresh edit implicitly.
        if (originalOnly && !pending()) { await h.refresh(); return undefined; }
        await maintenanceContractAuthorize(api, projectId, contractId);
        if (!live()) return undefined;
        if (originalOnly && !pending()) { await h.refresh(); return undefined; }
        const body = pending() ? api.pendingCommandValues(key, path) : maintenanceContractValues(projectId, previous, values);
        const result = pending() ? await api.retry(key, {stillCurrent: live}) : await api.mutate(key, path, body,
          {validate: value => maintenanceContractReceipt(path, body, value), stillCurrent: live});
        return live() ? result : undefined;
      } catch (error) {
        if (!live()) return undefined;
        if ([401, 403, 404].includes(error.status)) { h.closeModal(); await h.refresh(); return undefined; }
        throw error;
      } finally { if (live()) { lock(); h.updatePending(); } }
    }, {key, submit: contractId ? 'Änderungen speichern' : 'Vertrag speichern', after: h.refresh,
      extra: el('div', {}, notice('Pausieren stoppt die Erzeugung weiterer Einsätze. Bereits geplante Einsätze und Nachweise bleiben erhalten. Nach angelegten Einsätzen benötigt eine andere Serie einen neuen Vertrag.'),
        button('Aktuellen Stand laden', () => h.action(() => edit(projectId, assets, contractId)), 'small'))});
    box.setAttribute('data-maintenance-contract', projectId);
    dialog(contractId ? 'Wartungsvertrag bearbeiten' : 'Wartungsvertrag anlegen', box);
    opened = h.stamp(); lock();
  }
  return {edit};
}
