/* Public actual travel cash: intentionally independent of private travel UI. */
const ID = /^[a-f0-9]{32}$/, HASH = /^[a-f0-9]{64}$/;
const fail = message => Object.assign(new Error(message), {status: 0});
export const TRAVEL_CASH_CATEGORIES = {travel_allowance: 'Belegte Reisekostenerstattung'};
function shape(value, keys) {
  return value && !Array.isArray(value) && Object.keys(value).every(key => keys.includes(key));
}
function cents(value) {
  if (typeof value !== 'string' || !/^(?:0|[1-9]\d{0,12})\.\d{2}$/.test(value)) throw fail('Genaue belegte EUR-Cents erwartet.');
  return BigInt(value.replace('.', ''));
}
function account(value) {
  return shape(value, ['id', 'code', 'name', 'kind', 'currency', 'active', 'revision', 'created_by', 'created_at']) &&
    ID.test(value.id ?? '') && value.currency === 'EUR' && Number.isSafeInteger(value.revision) && value.revision > 0;
}
function date(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(value + 'T00:00:00Z');
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
export function travelCashPublic(source) {
  if (!shape(source, ['kind', 'id', 'revision', 'instance_id', 'status', 'date', 'cash_movements', 'source_path', 'source_hash', 'proof_hash']) ||
      source.kind !== 'travel_cash' || !ID.test(source.id ?? '') || !ID.test(source.instance_id ?? '') ||
      !HASH.test(source.source_hash ?? '') || !HASH.test(source.proof_hash ?? '') ||
      !Number.isSafeInteger(source.revision) || source.revision < 1 || !['active', 'void'].includes(source.status) ||
      !date(source.date) || !Array.isArray(source.cash_movements) ||
      source.source_path !== `/personnel/travel/financial/${source.id}?revision=${source.revision}` ||
      source.cash_movements.length !== (source.status === 'void' ? 0 : 1)) {
    throw fail('Die öffentliche Reisezahlungsquelle ist nicht eindeutig und datensparsam bestätigt.');
  }
  for (const movement of source.cash_movements) {
    if (!shape(movement, ['id', 'date', 'account', 'direction', 'amount', 'categories']) || !ID.test(movement.id ?? '') ||
        !date(movement.date) || movement.date !== source.date || !account(movement.account) ||
        !['in', 'out'].includes(movement.direction) || !shape(movement.categories, ['travel_allowance']) ||
        Object.keys(movement.categories).length !== 1 || cents(movement.categories.travel_allowance) <= 0n ||
        cents(movement.amount) !== cents(movement.categories.travel_allowance)) {
      throw fail('Der öffentliche Reisekostenbetrag ist nicht an tatsächlichen Tag, Geldkonto und Quelle gebunden.');
    }
  }
  return source;
}
export function travelCashCategories(source) {
  travelCashPublic(source); return source.status === 'void' ? [] : ['travel_allowance'];
}
export function travelBankSource(source) {
  if (!shape(source, ['source_kind', 'source_id', 'account', 'date', 'direction', 'amount', 'source_path', 'origin_hash', 'source_hash']) ||
      source.source_kind !== 'travel_cash' || !ID.test(source.source_id ?? '') || !account(source.account) ||
      !date(source.date) || !['in', 'out'].includes(source.direction) || cents(source.amount) <= 0n ||
      !HASH.test(source.origin_hash ?? '') || !HASH.test(source.source_hash ?? '') ||
      !/^\/personnel\/travel\/financial\/[a-f0-9]{32}\?revision=[1-9]\d*$/.test(source.source_path ?? '')) {
    throw fail('Die Reisegeldquelle für den Bankabgleich enthält keinen vollständigen öffentlichen Nachweis.');
  }
  return source;
}
