/* Private employer-wide travel flat-tax decisions; no calculated or paid tax. */
import {PAYROLL_FACT_STATES, payrollFactDate, payrollFactRef} from './payroll-facts.js';

export const PAYROLL_TRAVEL_POLICY_RULE = 'de_2026_travel_tax_policy_v1';
export const PAYROLL_TRAVEL_POLICY_KEY = 'payroll-travel-tax-policies';
export const PAYROLL_TRAVEL_POLICY_PATH = '/business/payroll/travel-tax-policies';
export const PAYROLL_TRAVEL_CHURCH_METHODS = {
  simplified: 'Vereinfachtes Verfahren für sämtliche Empfänger',
  evidence: 'Nachweisverfahren mit belegter Kirchenzugehörigkeit',
};
export const PAYROLL_TRAVEL_CHURCH_REGIONS = {
  standard: 'Allgemeine Zuständigkeit des gewählten Bundeslands',
  ni_ev_westfalen: 'Niedersachsen: Evangelische Kirche von Westfalen',
  bw_bad_wimpfen_mainz: 'Bad Wimpfen: römisch-katholische Zuständigkeit Mainz',
};
const ID = /^[a-f0-9]{32}$/, HASH = /^[a-f0-9]{64}$/;
const clone = value => JSON.parse(JSON.stringify(value));
const ordered = value => Array.isArray(value) ? value.map(ordered) : value && typeof value === 'object'
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value;
const same = (a,b) => JSON.stringify(ordered(a)) === JSON.stringify(ordered(b));
const fail = (message, status=400) => Object.assign(new Error(message), {status});
function text(value, label) {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > 3000 || /[\x00-\x1f\x7f]/.test(value)) throw fail(label+' vollständig belegen.');
  return value.trim();
}
export function payrollTravelTaxPolicyDetails(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw fail('Die betriebliche Entscheidung fehlt.');
  const from = payrollFactDate(value.filing_period_from), to = payrollFactDate(value.filing_period_to);
  const first = new Date(from+'T00:00:00Z'), last = new Date(to+'T00:00:00Z');
  const lastOf = month => new Date(Date.UTC(2026, month, 0)).toISOString().slice(0,10);
  const month = first.getUTCMonth()+1;
  const wholeMonth = first.getUTCDate()===1 && to===lastOf(month);
  const quarter = first.getUTCDate()===1 && [1,4,7,10].includes(month) && to===lastOf(month+2);
  const year = from==='2026-01-01' && to==='2026-12-31';
  if (first.getUTCFullYear()!==2026 || last.getUTCFullYear()!==2026 || !(wholeMonth||quarter||year)) throw fail('Einen vollständigen belegten Anmeldemonat, ein Quartal oder das Jahr 2026 angeben.');
  if (!Object.hasOwn(PAYROLL_FACT_STATES,value.federal_state) || !Object.hasOwn(PAYROLL_TRAVEL_CHURCH_METHODS,value.church_method) || !Object.hasOwn(PAYROLL_TRAVEL_CHURCH_REGIONS,value.church_rate_region) ||
      value.church_rate_region==='ni_ev_westfalen' && value.federal_state!=='NI' || value.church_rate_region==='bw_bad_wimpfen_mainz' && value.federal_state!=='BW' ||
      value.church_method_applies_to_all!==true || typeof value.employer_bears_tax!=='boolean') throw fail('Betriebsstätte, Zuständigkeit, einheitliches Verfahren und Kostenübernahme ausdrücklich belegen.');
  const result = {filing_period_from:from,filing_period_to:to,federal_state:value.federal_state,church_method:value.church_method,church_rate_region:value.church_rate_region,
    church_method_applies_to_all:true,employer_bears_tax:value.employer_bears_tax,verification_note:text(value.verification_note,'Betriebliche Steuerentscheidung')};
  if (Object.keys(value).some(key=>!Object.hasOwn(result,key))) throw fail('Unbekannte Angaben in der betrieblichen Steuerentscheidung.');
  return result;
}
function originals(files, ids) {
  if (!Array.isArray(files) || !Array.isArray(ids) || !ids.length || ids.length>100 || new Set(ids).size!==ids.length) throw fail('Konkrete geschützte Originale der betrieblichen Entscheidung auswählen.');
  for (const id of ids) {
    const file=files.find(v=>v.id===id);
    if (!ID.test(id) || !file || file.purpose!=='personnel' || !ID.test(file.employee_id||'') || !HASH.test(file.sha256||'') || !HASH.test(file.content_hash||'') || !Number.isSafeInteger(file.size) || file.size<1) throw fail('Die tatsächliche geschützte Originalfassung fehlt.');
  }
  return [...ids].sort();
}
export function payrollTravelTaxPolicyRecord(value) {
  payrollFactRef(value);
  const details=payrollTravelTaxPolicyDetails(value.details), sources=value.sources;
  if (value.employee_id!==null || value.kind!=='travel_tax_policy' || value.rule_version!==PAYROLL_TRAVEL_POLICY_RULE || value.source_contract_version!==1 || !['active','void'].includes(value.status) || value.plan!==null ||
      !sources || sources.schema_version!==1 || !same(sources.policy,details) || !same(value.details,details) || value.effective_from!==details.filing_period_from || value.effective_to!==details.filing_period_to ||
      !HASH.test(value.source_hash||'') || !HASH.test(value.preview_hash||'') || (value.revision===1 ? value.previous_hash!==null : !HASH.test(value.previous_hash||'')) ||
      !same(originals(sources.source_files,value.source_file_ids),value.source_file_ids) || !same(sources.source_files.map(file=>file.id).sort(),value.source_file_ids)) throw fail('Die Steuerentscheidung ist nicht an ihre ursprüngliche betriebliche Fassung gebunden.');
  return value;
}
export function payrollTravelTaxPolicySources(value) {
  if (!value || value.employee_id!==null || !Array.isArray(value.files) || !Array.isArray(value.file_references) || !Array.isArray(value.policies) ||
      ['can_write','can_approve','writes_enabled'].some(key=>typeof value[key]!=='boolean') || value.files.length!==value.file_references.length) throw fail('Der betriebliche Originalkatalog ist unvollständig.');
  const files=new Set(), policies=new Set();
  for (const file of value.files) {
    originals([file],[file.id]);
    if (files.has(file.id)) throw fail('Eine Originalfassung wurde mehrfach geliefert.');
    files.add(file.id);
  }
  const refs=new Set();
  for (const reference of value.file_references) {
    payrollFactRef(reference);
    if (reference.revision!==1 || refs.has(reference.id) || value.files.find(v=>v.id===reference.id)?.content_hash!==reference.content_hash) throw fail('Originalreferenz und geschützter Dateinachweis widersprechen sich.');
    refs.add(reference.id);
  }
  for (const policy of value.policies) {
    payrollTravelTaxPolicyRecord(policy);
    if (policies.has(policy.id)) throw fail('Eine Steuerentscheidung wurde mehrfach geliefert.');
    policies.add(policy.id);
  }
  return value;
}
export function payrollTravelTaxPolicyRights(caps) {
  const permissions=new Set(caps?.permissions||[]), read=caps?.features?.includes('payroll_calculation_cases')===true && caps?.capabilities?.includes('business_payroll_calculation_cases')===true && permissions.has('personnel.read');
  return {read,approve:read&&caps.readonly===false&&permissions.has('personnel.approve'),enabled:read&&caps.readonly===false&&caps.organization?.modules?.personnel?.enabled!==false};
}
export async function payrollTravelTaxPoliciesAuthorize(api,{write=false,replay=false}={}) {
  const caps=await api.get('/business/capabilities'), rights=payrollTravelTaxPolicyRights(caps);
  if (!rights.read || write&&!rights.approve) throw fail('Aktuelle globale Personal-Lese- und Freigaberechte fehlen.',403);
  const sources=payrollTravelTaxPolicySources(await api.get(PAYROLL_TRAVEL_POLICY_PATH+'/sources'));
  if (write&&!sources.can_approve) throw fail('Die aktuelle betriebliche Freigabeberechtigung fehlt.',403);
  if (write&&!replay&&(!rights.enabled||!sources.writes_enabled)) throw fail('Neue Steuerentscheidungen sind im pausierten Personalbereich gesperrt.',423);
  return {caps,rights,sources};
}
export async function payrollTravelTaxPoliciesPendingAuthorize(api, operation) {
  const body=api.pendingCommandValues(operation?.key,operation?.path);
  if (operation?.key!==PAYROLL_TRAVEL_POLICY_KEY || operation?.path!==PAYROLL_TRAVEL_POLICY_PATH || body?.employee_id!==null || body?.employee_revision!==null || body?.kind!=='travel_tax_policy' || body?.rule_version!==PAYROLL_TRAVEL_POLICY_RULE || body?.source_contract_version!==1) throw fail('Der ursprüngliche betriebliche Steuerauftrag fehlt.',409);
  await payrollTravelTaxPoliciesAuthorize(api,{write:true,replay:true});
  return true;
}
export function payrollTravelTaxPolicyInput(sources, values, previous=null) {
  payrollTravelTaxPolicySources(sources);
  if (previous) payrollTravelTaxPolicyRecord(previous);
  const details=payrollTravelTaxPolicyDetails(values.details);
  if (previous && ['filing_period_from','filing_period_to','federal_state','church_rate_region'].some(k=>details[k]!==previous.details[k])) throw fail('Zeitraum und Betriebsstätten-Zuständigkeit der ursprünglichen Entscheidung bleiben bei einer Korrektur erhalten.');
  return {employee_id:null,employee_revision:null,kind:'travel_tax_policy',rule_version:PAYROLL_TRAVEL_POLICY_RULE,source_contract_version:1,revision:previous?.revision||0,status:'active',
    details,source_file_ids:originals(sources.files,values.source_file_ids),confirmed:true,...previous?{id:previous.id,correction_reason:text(values.correction_reason,'Korrekturgrund')}:{}};
}
export function payrollTravelTaxPolicyPreviewInput(body) {
  return clone(Object.fromEntries(['employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids'].map(key=>[key,body[key]])));
}
export function payrollTravelTaxPolicyPreview(value,body) {
  if (!value || value.employee_id!==null || value.kind!=='travel_tax_policy' || value.plan!==null || value.source_snapshot?.schema_version!==1 || !same(value.source_snapshot.policy,body.details) ||
      !same(originals(value.source_snapshot.source_files,body.source_file_ids),body.source_file_ids) || !same(value.source_snapshot.source_files.map(file=>file.id).sort(),body.source_file_ids) || !HASH.test(value.source_hash||'') || !HASH.test(value.preview_hash||'') ||
      ['can_confirm','can_calculate','can_write','can_approve','writes_enabled'].some(key=>typeof value[key]!=='boolean')) throw fail('Die Vorschau gehört nicht zur gewählten betrieblichen Steuerentscheidung.');
  return value;
}
export function payrollTravelTaxPolicyValidator(body, previous=null, preview=null) {
  const frozen=clone(body), prior=previous?clone(previous):null, proof=preview?clone(preview):null;
  return value=>{
    payrollTravelTaxPolicyRecord(value);
    if (value.revision!==frozen.revision+1 || frozen.id&&value.id!==frozen.id || value.previous_hash!==(prior?.content_hash||null) || value.status!==frozen.status || !same(value.details,frozen.details) ||
        !same(value.source_file_ids,frozen.source_file_ids) || value.preview_hash!==frozen.preview_hash || value.correction_reason!==(frozen.correction_reason||'') ||
        proof&&(!same(value.sources,proof.source_snapshot)||value.source_hash!==proof.source_hash) || frozen.status==='void'&&(!prior||!same(value.sources,prior.sources)||value.source_hash!==prior.source_hash)) throw fail('Die Antwort bestätigt nicht den unveränderten geprüften Steuerauftrag. Die ursprüngliche Anfrage bleibt erhalten.',502);
    return value;
  };
}

export function createPayrollTravelTaxPolicyUi(h) {
  const {api,el,button,field,form,dialog,panel,notice,table}=h;
  let active=null, selectedCallback=null;
  const action=fn=>h.action(fn,active), pending=()=>api.pendingCommandValues(PAYROLL_TRAVEL_POLICY_KEY,PAYROLL_TRAVEL_POLICY_PATH);
  const available=()=>payrollTravelTaxPolicyRights(h.caps()).read;
  async function fresh(write=false,replay=false) {
    const stamp=h.stamp(), result=await payrollTravelTaxPoliciesAuthorize(api,{write,replay});
    if (stamp!==h.stamp() || !available()) throw fail('Die private Ansicht oder Berechtigung wurde geändert.',403);
    return result;
  }
  function show(title, body) {
    if (!available()) throw fail('Aktuelle globale Personal-Leserechte fehlen.',403);
    active=body;body.setAttribute('data-payroll','employer');body.setAttribute('data-payroll-travel-tax-policies','');dialog(title,body);
  }
  function detailsView(d) {
    return table(['Betriebliche Entscheidung','Belegter Wert'],[
      ['Anmeldezeitraum',h.formatDate(d.filing_period_from)+' – '+h.formatDate(d.filing_period_to)],
      ['Lohnsteuerliche Betriebsstätte',PAYROLL_FACT_STATES[d.federal_state]],
      ['Kirchensteuerverfahren',PAYROLL_TRAVEL_CHURCH_METHODS[d.church_method]],
      ['Zuständigkeit',PAYROLL_TRAVEL_CHURCH_REGIONS[d.church_rate_region]],
      ['Wirtschaftliche Steuerkosten',d.employer_bears_tax?'Arbeitgeber übernimmt die Steuerkosten':'Arbeitnehmerabzug nur mit eigener belegter Vereinbarung'],
      ['Prüfvermerk',d.verification_note],
    ]);
  }
  async function save(body,previous=null,preview=null) {
    const original=pending();
    if(original) {
      if(!same(original,body))throw fail('Nur den unveränderten ursprünglichen Steuerauftrag erneut prüfen.',409);
      await fresh(true,true);
      await inspect(await api.retry(PAYROLL_TRAVEL_POLICY_KEY));
      return;
    }
    await fresh(true);
    if (pending()) throw fail('Zuerst den ursprünglichen noch offenen Steuerauftrag klären.',409);
    const value=await api.mutate(PAYROLL_TRAVEL_POLICY_KEY,PAYROLL_TRAVEL_POLICY_PATH,body,{validate:payrollTravelTaxPolicyValidator(body,previous,preview)});
    await inspect(value);
  }
  async function inspect(value,historical=false) {
    const access=await fresh();payrollTravelTaxPolicyRecord(value);
    const body=el('div',{class:'stack'},notice('Fassung '+value.revision+' · '+(value.status==='active'?'Aktiv':'Aufgehoben')),detailsView(value.details));
    for (const file of value.sources.source_files) body.append(h.onOriginal?button('Geschütztes Original: '+file.filename,()=>action(async()=>{await fresh();await h.onOriginal({id:file.employee_id},file);}), 'small'):notice('Geschütztes Original: '+file.filename));
    if (!historical) body.append(button('Entscheidungshistorie öffnen',()=>action(async()=>{
      await fresh();const stamp=h.stamp(), page=await api.get(PAYROLL_TRAVEL_POLICY_PATH+'/'+value.id+'/history');
      if(stamp!==h.stamp())return;
      if(!Array.isArray(page.items)||page.items.some((item,i)=>payrollTravelTaxPolicyRecord(item).id!==value.id||item.revision!==i+1||item.previous_hash!==(i?page.items[i-1].content_hash:null)))throw fail('Die Historie gehört nicht vollständig zur ausgewählten Entscheidung.');
      show('Historie der betrieblichen Steuerentscheidung',el('div',{class:'stack'},...page.items.map(item=>panel('Fassung '+item.revision,detailsView(item.details),button('Diese historische Fassung öffnen',()=>action(()=>inspect(item,true)),'small')))));
    }), 'small'));
    if(!historical&&access.rights.approve&&access.sources.can_approve&&access.sources.writes_enabled&&!pending()) {
      body.append(button('Entscheidung korrigieren',()=>action(()=>edit(value)),'small'));
      if(value.status==='active')body.append(button('Fälschliche Entscheidung aufheben',()=>action(()=>voidPolicy(value)),'small'));
    }
    if(!historical&&value.status==='active'&&selectedCallback)body.append(button('Diese aktuelle Entscheidung auswählen',()=>action(async()=>{
      const current=await fresh(), exact=current.sources.policies.find(v=>v.id===value.id);
      if(!exact||exact.status!=='active'||!same(payrollFactRef(exact),payrollFactRef(value)))throw fail('Die Entscheidung wurde inzwischen geändert. Aktuelle Fassung neu auswählen.',409);
      const callback=selectedCallback;selectedCallback=null;await callback(clone(exact));
    }),'primary'));
    show((historical?'Historische ':'')+'Betriebliche Reise-Pauschalsteuer',body);
  }
  async function preview(body,previous=null) {
    await fresh(true);const stamp=h.stamp(), proof=payrollTravelTaxPolicyPreview(await api.post(PAYROLL_TRAVEL_POLICY_PATH+'/preview',payrollTravelTaxPolicyPreviewInput(body)),body);
    if(stamp!==h.stamp())return;
    const confirmed={...body,preview_hash:proof.preview_hash};
    show('Betriebliche Steuerentscheidung prüfen',el('div',{class:'stack'},detailsView(body.details),notice('Diese Entscheidung gilt einheitlich für den Anmeldezeitraum. Die tatsächliche Steuererfassung erfolgt erst mit einem gesondert bestätigten Lohnabschluss.'),
      form('',[field('confirmed','Ich bestätige die belegten Originale und die einheitliche betriebliche Entscheidung.','checkbox',false,{required:true})],async values=>{
        if(values.confirmed!==true)throw fail('Die betriebliche Entscheidung ausdrücklich bestätigen.');
        if(!proof.can_confirm)throw fail('Diese Vorschau kann noch nicht bestätigt werden.');
        await save(confirmed,previous,proof);
      },{key:'travel-tax-policy-confirm',submit:'Geprüfte Entscheidung festhalten'})));
  }
  async function edit(previous=null) {
    const {sources}=await fresh(true);if(pending())return open();const d=previous?.details||{};
    const fields=[field('filing_period_from','Tatsächlicher Anmeldezeitraum ab','date',d.filing_period_from||'',{required:true}),field('filing_period_to','Tatsächlicher Anmeldezeitraum bis','date',d.filing_period_to||'',{required:true}),
      field('federal_state','Bundesland der lohnsteuerlichen Betriebsstätte','select',d.federal_state||'',{required:true,options:[['','Bitte ausdrücklich wählen'],...Object.entries(PAYROLL_FACT_STATES)]}),
      field('church_method','Einheitliches Kirchensteuerverfahren','select',d.church_method||'',{required:true,options:[['','Bitte ausdrücklich wählen'],...Object.entries(PAYROLL_TRAVEL_CHURCH_METHODS)]}),
      field('church_rate_region','Belegte kirchensteuerliche Zuständigkeit','select',d.church_rate_region||'',{required:true,options:[['','Bitte ausdrücklich wählen'],...Object.entries(PAYROLL_TRAVEL_CHURCH_REGIONS)]}),
      field('cost_bearer','Wirtschaftliche Übernahme der Steuerkosten','select',typeof d.employer_bears_tax==='boolean'?(d.employer_bears_tax?'employer':'employee'):'',{required:true,options:[['','Bitte ausdrücklich wählen'],['employer','Arbeitgeber übernimmt die Steuerkosten'],['employee','Arbeitnehmerabzug nur mit gesondertem Vereinbarungsnachweis']]}),
      field('source_file_ids','Geschützte Originale der betrieblichen Entscheidung','multi',previous?.source_file_ids||[],{required:true,options:sources.files.map(v=>[v.id,v.filename])}),
      field('verification_note','Nachvollziehbarer betrieblicher Prüfvermerk','text',d.verification_note||'',{required:true}),
      field('church_method_applies_to_all','Dieses Verfahren gilt einheitlich für den gesamten Anmeldezeitraum und Tatbestand.','checkbox',false,{required:true}),
      ...previous?[field('correction_reason','Belegter Korrekturgrund','text','',{required:true})]:[]];
    show(previous?'Betriebliche Steuerentscheidung korrigieren':'Betriebliche Steuerentscheidung erfassen',form('',fields,async values=>{
      const current=await fresh(true);
      if(!['employer','employee'].includes(values.cost_bearer))throw fail('Kostenübernahme ausdrücklich wählen.');
      const details=Object.fromEntries(['filing_period_from','filing_period_to','federal_state','church_method','church_rate_region','church_method_applies_to_all','verification_note'].map(k=>[k,values[k]]));
      details.employer_bears_tax=values.cost_bearer==='employer';
      await preview(payrollTravelTaxPolicyInput(current.sources,{...values,details},previous),previous);
    },{key:'travel-tax-policy-editor',submit:'Betriebliche Entscheidung unverbindlich prüfen'}));
  }
  async function voidPolicy(previous) {
    await fresh(true);
    show('Fälschliche betriebliche Entscheidung aufheben',form('',[field('correction_reason','Belegter Aufhebungsgrund','text','',{required:true}),field('confirmed','Ich bestätige die Aufhebung. Frühere Lohn- und Steuererfassungen bleiben erhalten.','checkbox',false,{required:true})],async values=>{
      if(values.confirmed!==true)throw fail('Aufhebung ausdrücklich bestätigen.');
      const body={...payrollTravelTaxPolicyPreviewInput(previous),employee_revision:null,id:previous.id,revision:previous.revision,status:'void',preview_hash:previous.preview_hash,confirmed:true,correction_reason:text(values.correction_reason,'Aufhebungsgrund')};
      await save(body,previous);
    },{key:'travel-tax-policy-void',submit:'Entscheidung belegt aufheben',extra:detailsView(previous.details)}));
  }
  async function open(options={}) {
    if(Object.hasOwn(options,'onSelected'))selectedCallback=options.onSelected;
    const access=await fresh(), body=el('div',{class:'stack'},notice('Betriebliche Entscheidung über die 25%-Pauschalierung zusätzlicher Reise-Verpflegung. Der Anmeldezeitraum und die Betriebsstätte müssen tatsächlich belegt sein.'));
    if(pending())body.append(panel('Steuerentscheidung noch offen',notice('Der Auftrag kann bereits gespeichert sein. Es wird nur der unveränderte ursprüngliche Auftrag erneut geprüft.'),access.rights.approve&&access.sources.can_approve?button('Ursprünglichen Steuerauftrag erneut senden',()=>action(async()=>{await fresh(true,true);await inspect(await api.retry(PAYROLL_TRAVEL_POLICY_KEY));}),'primary'):null));
    if(!pending()&&access.rights.approve&&access.sources.can_approve&&access.sources.writes_enabled)body.append(button('Betriebliche Steuerentscheidung erfassen',()=>action(()=>edit()),'primary'));
    for(const value of access.sources.policies)body.append(panel(h.formatDate(value.effective_from)+' – '+h.formatDate(value.effective_to),notice(PAYROLL_FACT_STATES[value.details.federal_state]+' · '+PAYROLL_TRAVEL_CHURCH_METHODS[value.details.church_method]+' · Fassung '+value.revision),button('Entscheidung öffnen',()=>action(()=>inspect(value)),'small')));
    if(!access.sources.policies.length)body.append(notice('Noch keine belegte betriebliche Steuerentscheidung vorhanden.'));
    show('Betriebliche Reise-Pauschalsteuer',body);
  }
  return {open,inspect,available,clear:()=>{active=null;selectedCallback=null;}};
}
