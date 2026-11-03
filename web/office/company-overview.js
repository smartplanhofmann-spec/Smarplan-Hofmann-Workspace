/* The server owns arithmetic and authorization; every card retains its source. */
export function overviewModel(value) {
  const amount = v => v === null || typeof v === 'string' && /^-?\d+\.\d{2}$/.test(v);
  const count = v => Number.isSafeInteger(v) && v >= 0;
  if (value?.schema_version !== 1 || !['authorized_projects','selected_project'].includes(value.scope) ||
      !count(value.project_count) || !count(value.task_count) || !count(value.appointment_count) ||
      !Array.isArray(value.tasks) || !Array.isArray(value.appointments) || !Array.isArray(value.finance?.projects) ||
      !count(value.finance.project_count) || typeof value.accounting?.available !== 'boolean' ||
      !['revenue_net','costs_net','contribution_net','receipts_gross','refunds_gross','open_gross','overdue_gross'].every(key=>amount(value.finance[key])) ||
      !/^[a-f0-9]{64}$/.test(value.source_hash)) throw new Error('Die Unternehmensübersicht ist unvollständig. Bitte erneut laden.');
  if ((!value.finance.complete_for_recorded_sources && value.finance.contribution_net !== null) ||
      value.finance.project_count === 0 && value.finance.revenue_net !== null ||
      value.scope === 'selected_project' && value.accounting.available ||
      value.accounting.available && (!amount(value.accounting.totals?.euer_surplus) || value.accounting.balance !== null || value.accounting.opening_balances_available !== false))
    throw new Error('Die Kennzahlen haben keine eindeutige Berechnungsgrundlage.');
  return value;
}

export function renderCompanyOverview(raw, {el,panel,row,rows,button,notice,formatMoney,formatDate,onProject,onAccounting}) {
  const value=overviewModel(raw), finance=value.finance;
  const metric=(label,amount,detail)=>panel(label,el('div',{class:'metric'},amount),el('p',{class:'metric-sub'},detail));
  const source=(item,tab)=>button('Vorgang öffnen',()=>onProject(item.project_id,tab),'small');
  const result=el('section',{class:'stack','aria-label':'Unternehmenskennzahlen'},
    el('p',{class:'muted'},`Datenstand ${formatDate(value.as_of,true)} · ${value.project_count} freigegebene Projekte · Termine bis ${formatDate(value.appointment_until)}`),
    el('div',{class:'grid'},metric('Offene Aufgaben',String(value.task_count),`${value.overdue_task_count} überfällig`),
      metric('Anstehende Termine',String(value.appointment_count),'Nächste 30 Tage')),
    panel('Als Nächstes',rows(value.tasks,item=>row(item.title,`${item.project_name} · ${item.due_date?formatDate(item.due_date):'Ohne Frist'}${item.overdue?' · Überfällig':''}`,[source(item,'tasks')]),'Keine offenen Aufgaben.'),
      value.task_count>value.tasks.length?el('p',{class:'muted'},`Die ersten ${value.tasks.length} von ${value.task_count} Aufgaben. Weitere in den Projekten.`):null),
    panel('Anstehende Termine',rows(value.appointments,item=>row(item.title,`${item.project_name} · ${formatDate(item.start_at,true)}`,[source(item,'appointments')]),'Keine anstehenden Termine.')));
  if(finance.project_count) {
    result.append(el('div',{class:'grid'},
      metric('Rechnungsumsatz netto',formatMoney(finance.revenue_net),'Festgeschriebene Rechnungen abzüglich Gutschriften'),
      metric('Erfasste Projektkosten netto',formatMoney(finance.costs_net),'Material, Arbeit und eingeordnete Eingangsbelege'),
      metric('Projektbeitrag netto',finance.contribution_net===null?'Klärung erforderlich':formatMoney(finance.contribution_net),'Rechnungsumsatz abzüglich erfasster Projektkosten'),
      metric('Zugeordnete Kundenzahlungen',formatMoney(finance.receipts_gross),`Erstattungen ${formatMoney(finance.refunds_gross)} · jeweils brutto`),
      metric('Offene Kundensalden',formatMoney(finance.open_gross),`Davon überfällig ${formatMoney(finance.overdue_gross)} · jeweils brutto`)));
    result.append(notice(`Finanzsicht für ${finance.project_count} der ${value.project_count} freigegebenen Projekte. Erfasste Vorgänge seit Beginn; Projektbeiträge enthalten keine unzugeordneten Gemeinkosten.`));
    if(!finance.complete_for_recorded_sources)result.append(notice('Kostenquellen sind noch zu klären. Ein vollständiger Projektbeitrag ist deshalb nicht verfügbar.','warn'));
    result.append(panel('Grundlage der Projektkennzahlen',rows(finance.projects,item=>row(item.project_name,
      `Umsatz ${formatMoney(item.revenue_net)} · Kosten ${formatMoney(item.costs_net)}${item.complete?'':' · Prüfung offen'}`,[source(item,'costs')]))));
  }
  if(value.accounting.available) {
    const accounting=value.accounting;
    result.append(panel(`EÜR ${accounting.year}`,el('div',{class:'metric'},accounting.totals.euer_surplus===null?'Klärung erforderlich':formatMoney(accounting.totals.euer_surplus)),
      el('p',{},`Bestätigte Einnahmen ${formatMoney(accounting.totals.confirmed_income)} · Ausgaben ${formatMoney(accounting.totals.confirmed_expenses)} · ${accounting.issue_count} offene Prüfpunkte`),
      el('p',{class:'muted'},`Erfasste Buchungen · Buchführungsbeginn ${accounting.coverage_start?formatDate(accounting.coverage_start):'noch offen'}`),
      button('EÜR und Belege öffnen',onAccounting,'primary')));
    result.append(panel('Erfasste Geldbewegungen',notice('Anfangsbestände sind noch nicht hinterlegt. Ein aktueller Kontostand ist daher nicht verfügbar.'),
      rows(accounting.account_movements,item=>row(item.account.name||item.account.id,
        `Zuflüsse ${formatMoney(item.inflows)} · Abflüsse ${formatMoney(item.outflows)} · Veränderung ${formatMoney(item.movement_net)}`)),button('Buchungsquellen öffnen',onAccounting)));
  }
  return result;
}
