import {payrollFactSources,payrollFactRef,payrollFactDate} from './payroll-facts.js';

export const PAYROLL_ENTITLEMENT_KINDS={sickness_history:'Krankheitsverlauf und Vorzeiten',regular_absence:'Belegte regelmäßige Ausfallvergütung',vacation_reference:'Urlaubsentgelt aus 13 Wochen',unpaid_continuation:'Unbezahlte Unterbrechung und SV-Fortbestand'};
export const PAYROLL_ABSENCE_KINDS={public_holiday:'Gesetzlicher Feiertag',sickness:'Krankheit mit geprüftem Anspruch',first_sickness_day_regular_wage:'Erster Krankheitstag nach begonnener Arbeit'};
export const PAYROLL_ONSETS={before_work:'Vor Arbeitsbeginn',during_work:'Während tatsächlich begonnener Arbeit',non_workday:'An einem planmäßig arbeitsfreien Tag'};
export const PAYROLL_SICKNESS_MODES={separate:'Getrennte Krankheitsfälle',combined:'Zusammenhängende Erkrankungsursachen',preemployment:'Erkrankung vor Beschäftigungsbeginn'};
const PHASE_RULES=['de_2026_sickness_phases_v3','de_2026_sickness_start_v4'];
export const PAYROLL_CONTINUATION_EXCEPTIONS={sickness_benefit:'Krankengeld',private_sickness_benefit:'Privates Krankentagegeld',injury_benefit:'Verletztengeld',social_compensation_sickness_benefit:'Krankengeld der Sozialen Entschädigung',soldier_compensation_sickness_benefit:'Soldatenentschädigungs-Krankengeld',transition_benefit:'Übergangsgeld',care_support_benefit:'Pflegeunterstützungsgeld',maternity_benefit:'Mutterschaftsgeld',child_raising_benefit:'Erziehungsgeld',parental_benefit:'Elterngeld',parental_leave:'Elternzeit',military_service:'Wehrdienst',civilian_service:'Zivildienst',care_leave_section_3:'Pflegezeit nach § 3'};
const ID=/^[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/;
const clone=value=>JSON.parse(JSON.stringify(value));
const ordered=value=>Array.isArray(value)?value.map(ordered):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,ordered(value[key])])):value;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const fail=(message,status=0)=>Object.assign(new Error(message),{status});
const supportedPlan=(plan,kind)=>plan?.schema_version===1&&plan.kind===kind&&(plan.rule_version==='de_2026_entitlements_v1'||kind==='sickness_history'&&['de_2026_sickness_v2',...PHASE_RULES].includes(plan.rule_version))&&['rules_hash','input_hash','source_hash','plan_hash'].every(k=>HASH.test(plan[k]||''))&&sicknessPlanShape(plan);
function sicknessPlanShape(plan){
 if(!PHASE_RULES.includes(plan.rule_version))return true;
 if(!Array.isArray(plan.episodes)||!Array.isArray(plan.prevention_cases)||!Array.isArray(plan.phases)||[...plan.episodes,...plan.prevention_cases,...plan.phases].some(v=>!v||typeof v!=='object'||Array.isArray(v)))return false;
 const cases=new Set(plan.prevention_cases.map(v=>v.id)),episodes=new Set(plan.episodes.map(v=>v.episode_id));let last=null;
 if(cases.size!==plan.prevention_cases.length||episodes.size!==plan.episodes.length||[...cases,...episodes].some(v=>!ID.test(v||'')))return false;
 for(const phase of plan.phases){
  if(!cases.has(phase.prevention_case_id)||!Array.isArray(phase.active_episode_ids)||!phase.active_episode_ids.length||new Set(phase.active_episode_ids).size!==phase.active_episode_ids.length||phase.active_episode_ids.some(v=>!episodes.has(v))||!phase.active_episode_ids.includes(phase.responsible_episode_id)||['entitled','first_day_remaining_regular_wage','waiting_period'].some(k=>typeof phase[k]!=='boolean'))return false;
  try{payrollFactDate(phase.from_date);payrollFactDate(phase.to_date);}catch{return false;}
  if(phase.from_date>phase.to_date||last&&phase.from_date<=last)return false;last=phase.to_date;
 }
 if(plan.rule_version==='de_2026_sickness_start_v4'&&(!HASH.test(plan.legal_projection_hash||'')||!Array.isArray(plan.preemployment_periods)||!plan.preemployment_periods.length||plan.preemployment_periods.some(v=>!episodes.has(v.episode_id)||v.employment_wage_entitlement!==false)))return false;
 return true;
}

export function payrollSicknessStructure(source,mode,caseChoices=[],caseIds=[],evidenceRefs=[],commencement=null){
 const value=clone(source),episodes=value.episodes;
 if(!Object.hasOwn(PAYROLL_SICKNESS_MODES,mode)||!Array.isArray(episodes))throw fail('Die tatsächliche Form des Krankheitsverlaufs ausdrücklich wählen.');
 if(mode==='separate'){
  if(episodes.some(v=>!Object.hasOwn(PAYROLL_ONSETS,v.onset)||v.recovery_before!==true))throw fail('Getrennte Fälle benötigen belegte Arbeitsfähigkeit vor jedem neuen Fall.');
  return value;
 }
 if(caseChoices.length!==episodes.length||caseIds.length!==episodes.length||!Array.isArray(evidenceRefs)||!evidenceRefs.length)throw fail('Jede Ursache einem konkret belegten Verhinderungsfall zuordnen.');
 const cases=[],assigned=[];
 for(const [i,episode]of episodes.entries()){
  const choice=caseChoices[i];let selected;
  if(choice==='new'){
   if(episode.recovery_before!==true||episode.onset==='during_existing_au'||!ID.test(caseIds[i]||'')||cases.some(v=>v.id===caseIds[i]))throw fail('Ein neuer Verhinderungsfall benötigt eine eigene Kennung und belegte vorherige Arbeitsfähigkeit.');
   selected={id:caseIds[i],episode_ids:[],evidence_refs:clone(evidenceRefs)};cases.push(selected);
  }else if(/^same:\d+$/.test(choice||'')&&Number(choice.slice(5))<i){
   if(episode.recovery_before!==false||episode.onset!=='during_existing_au'||episode.first_scheduled_day!==null)throw fail('Ein Hinzutritt muss bei fortbestehender AU ohne erfundenen Solltag belegt sein.');
   selected=assigned[Number(choice.slice(5))];
  }else throw fail('Den zusammenhängenden Verhinderungsfall ausdrücklich auswählen.');
  selected.episode_ids.push(episode.id);assigned.push(selected);
 }
 value.prevention_cases=cases;
 if(mode==='preemployment'){
  if(!episodes.some(v=>v.onset==='before_employment')||!commencement||!Array.isArray(commencement.evidence_refs)||!commencement.evidence_refs.length)throw fail('Ursprünglichen AU-Beginn, tatsächliches Vertragsdatum und Vertragsoriginal belegen.');
  payrollFactDate(commencement.contract_concluded_on);value.employment_commencement=clone(commencement);
 }else if(episodes.some(v=>v.onset==='before_employment'))throw fail('Eine AU vor Beschäftigungsbeginn benötigt den ausdrücklichen Beginnfall.');
 return value;
}
function note(value,label){if(typeof value!=='string'||!value.trim()||value.trim().length>3000||/[\x00-\x1f\x7f]/.test(value))throw fail(label+' ausdrücklich belegen.');return value.trim();}
function normalize(value,key){if(Array.isArray(value)){const result=value.map(v=>normalize(v));const sortKey=['evidence_refs','history_evidence_refs'].includes(key)?v=>v.id+':'+v.revision:['days','reference_days','vacation_days'].includes(key)?v=>v.date:key==='episodes'?v=>v.from+v.id:key==='exceptions'?v=>v.from+v.to+v.kind:null;return sortKey?result.sort((a,b)=>sortKey(a).localeCompare(sortKey(b))):result;}return value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([k,v])=>[k,normalize(v,k)])):value;}
function refs(items,ids,employeeId,label,{kind=null,optional=false}={}){if(!Array.isArray(ids)||!optional&&!ids.length||new Set(ids).size!==ids.length)throw fail(label+' ausdrücklich auswählen.');return [...ids].sort().map(id=>{const value=items.find(v=>v.id===id&&v.employee_id===employeeId&&v.status!=='void'&&(!kind||v.kind===kind));if(!value)throw fail(label+' gehört nicht zum gewählten Mitarbeiterstand.');return payrollFactRef(value);});}
export function payrollEntitlementRights(caps){const permissions=new Set(caps?.permissions||[]),read=caps?.features?.includes('payroll_entitlements')===true&&caps?.capabilities?.includes('business_payroll_entitlements')===true&&permissions.has('personnel.read');return {read,approve:read&&caps.readonly===false&&permissions.has('personnel.approve'),enabled:read&&caps.readonly===false&&caps.organization?.modules?.personnel?.enabled!==false};}
export function payrollEntitlementRecord(value,employeeId,kind=null){
 payrollFactRef(value);
 if(value.employee_id!==employeeId||!Object.hasOwn(PAYROLL_ENTITLEMENT_KINDS,value.kind)||kind&&value.kind!==kind||!['active','void'].includes(value.status)||!value.details||!ID.test(value.details.case_key||'')||!value.sources||value.sources.employee?.id!==employeeId||!value.plan||!HASH.test(value.source_hash||'')||!HASH.test(value.preview_hash||'')||!Array.isArray(value.source_file_ids)||!value.source_file_ids.length||new Set(value.source_file_ids).size!==value.source_file_ids.length||value.source_file_ids.some(id=>!ID.test(id))||(value.revision===1?value.previous_hash!==null:!HASH.test(value.previous_hash||'')))throw fail('Der Anspruchsnachweis ist nicht eindeutig an Mitarbeiter und Originalfassung gebunden.');
 payrollFactDate(value.effective_from);payrollFactDate(value.effective_to);if(value.effective_from>value.effective_to)throw fail('Der Anspruchszeitraum ist widersprüchlich.');
 if(!same(value.details,value.sources.details)||value.kind!==value.sources.kind)throw fail('Anspruchsdetails und eingefrorene Quellen widersprechen sich.');
 if(!supportedPlan(value.plan,value.kind)||value.plan.source_hash!==value.source_hash)throw fail('Der Anspruchsnachweis verwendet keinen bekannten unveränderten Regelstand.');
 return value;
}
export function payrollEntitlementSources(value,employeeId){
 payrollFactSources(value,employeeId);
 if(!Array.isArray(value.entitlements)||!Array.isArray(value.file_references)||value.file_references.length!==value.files.length)throw fail('Die kanonischen Anspruchs- und Originalreferenzen fehlen.');
 const seen=new Set();for(const fact of value.entitlements){payrollEntitlementRecord(fact,employeeId);if(seen.has(fact.id))throw fail('Eine Anspruchsquelle ist mehrfach enthalten.');seen.add(fact.id);}
 const originalIds=new Set();for(const ref of value.file_references){payrollFactRef(ref);const file=value.files.find(v=>v.id===ref.id);if(!file||ref.revision!==1||ref.content_hash!==file.content_hash||originalIds.has(ref.id))throw fail('Die Anspruchsoriginalreferenz widerspricht der Personaldatei.');originalIds.add(ref.id);}
 return value;
}
export async function payrollEntitlementsAuthorize(api,employeeId,{write=false,replay=false}={}){
 const caps=await api.get('/business/capabilities'),rights=payrollEntitlementRights(caps);if(!rights.read||write&&!rights.approve)throw fail('Aktuelle globale Personal-Lese- und Freigaberechte fehlen.',403);
 const sources=payrollEntitlementSources(await api.get('/business/payroll/entitlements/sources?employee_id='+employeeId),employeeId);
 if(write&&!sources.can_approve)throw fail('Die aktuelle Anspruchsfreigabe für diesen Mitarbeiter fehlt.',403);
 if(write&&!replay&&(!rights.enabled||!sources.writes_enabled))throw fail('Neue Anspruchsnachweise sind im pausierten Personalbereich gesperrt.',423);
 return {caps,rights,sources};
}
export async function payrollEntitlementsPendingAuthorize(api,operation){
 const match=/^payroll-entitlements-([a-f0-9]{32})$/.exec(operation?.key||''),body=api.pendingCommandValues(operation?.key,operation?.path);
 if(!match||operation.path!=='/business/payroll/entitlements'||body?.employee_id!==match[1]||!Object.hasOwn(PAYROLL_ENTITLEMENT_KINDS,body?.kind))throw fail('Der ursprüngliche private Anspruchsauftrag fehlt.',409);
 await payrollEntitlementsAuthorize(api,match[1],{write:true,replay:true});
 return true;
}
export function payrollEntitlementEvidence(sources,ids,outerIds){
 if(!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length)throw fail('Die konkreten Anspruchsoriginale ausdrücklich auswählen.');
 return [...ids].sort().map(id=>{const ref=sources.file_references.find(v=>v.id===id);if(!ref||!outerIds.includes(id))throw fail('Jedes Anspruchsoriginal muss zusätzlich in den gesamten Personaloriginalen enthalten sein.');return payrollFactRef(ref);});
}
export function payrollEntitlementInput(employeeId,sources,kind,values,previous=null){
 payrollEntitlementSources(sources,employeeId);
 if(!Object.hasOwn(PAYROLL_ENTITLEMENT_KINDS,kind))throw fail('Unbekannte Anspruchsart.');
 if(previous)payrollEntitlementRecord(previous,employeeId,kind);
 const ids=values.source_file_ids;if(!Array.isArray(ids)||!ids.length||ids.length>20||new Set(ids).size!==ids.length||ids.some(id=>!sources.files.some(v=>v.id===id)))throw fail('Ein bis zwanzig geschützte Personaloriginale auswählen.');
 const caseKey=previous?.details.case_key||values.case_key;if(!ID.test(caseKey||''))throw fail('Die ursprüngliche Anspruchsfallkennung fehlt.');
 const terms=refs(sources.facts,[values.employment_terms_id],employeeId,'Beschäftigungsnachweis',{kind:'employment_terms'})[0];
 const agreements=refs(sources.agreements,values.agreement_ids,employeeId,'Einschlägige Entgeltvereinbarungen');
 const schedules=refs(sources.facts,values.work_schedule_ids,employeeId,'Datierte Arbeitspläne',{kind:'work_schedule',optional:true});
 const preparations=refs(sources.preparations,values.preparation_ids,employeeId,'Abgeschlossene Monatsvorbereitungen',{optional:true});
 const history=values.sickness_history_id?refs(sources.entitlements,[values.sickness_history_id],employeeId,'Geprüfter Krankheitsverlauf',{kind:'sickness_history'})[0]:null;
 if(history&&kind!=='regular_absence')throw fail('Ein Krankheitsverlauf gehört nur zur konkreten Ausfallvergütung.');
 const input=normalize(clone(values.input));if(!input||typeof input!=='object'||Array.isArray(input))throw fail('Anspruchsangaben vollständig und strukturiert belegen.');
 function evidence(value){if(Array.isArray(value))value.forEach(evidence);else if(value&&typeof value==='object')for(const [k,v]of Object.entries(value)){if(['evidence_refs','history_evidence_refs'].includes(k)){if(!Array.isArray(v)||!v.length||!same(v,payrollEntitlementEvidence(sources,v.map(r=>r.id),ids)))throw fail('Die gewählte Anspruchsoriginalfassung ist nicht eindeutig.');}else evidence(v);}}
 evidence(input);
 const details={case_key:caseKey,employment_terms_ref:terms,work_schedule_refs:schedules,preparation_refs:preparations,agreement_refs:agreements,sickness_history_ref:history,input,verification_note:note(values.verification_note,'Anspruchsprüfung')};
 return {employee_id:employeeId,employee_revision:sources.employee.revision,kind,revision:previous?.revision||0,status:'active',details,source_file_ids:[...ids].sort(),confirmed:true,...previous?{id:previous.id,correction_reason:note(values.correction_reason,'Korrekturgrund')}:{}};
}
export function payrollEntitlementPreviewInput(body){return clone(Object.fromEntries(['employee_id','employee_revision','kind','details','source_file_ids'].map(key=>[key,body[key]])));}
export function payrollEntitlementPreview(value,body){
 const s=value?.source_snapshot,d=body.details;
 if(!supportedPlan(value?.plan,body.kind)||value.plan.source_hash!==value.source_hash)throw fail('Der Anspruchsplan ist nicht an den bekannten Quellen- und Regelstand gebunden.');
 if(!value||value.employee_id!==body.employee_id||value.kind!==body.kind||!s||s.employee?.id!==body.employee_id||s.employee.revision!==body.employee_revision||s.kind!==body.kind||s.schema_version!==1||!same(s.details,d)||!HASH.test(value.source_hash||'')||!HASH.test(value.preview_hash||'')||!value.plan||['can_confirm','can_calculate','can_write','can_approve','writes_enabled'].some(k=>typeof value[k]!=='boolean'))throw fail('Die Anspruchsvorschau ist nicht an den ausdrücklich geprüften Mitarbeiterstand gebunden.');
 if(!same(payrollFactRef(s.employment_terms),d.employment_terms_ref)||!same(s.work_schedules.map(payrollFactRef),d.work_schedule_refs)||!same(s.preparations.map(payrollFactRef),d.preparation_refs)||!same(s.agreements.map(payrollFactRef),d.agreement_refs)||!same(s.sickness_history?payrollFactRef(s.sickness_history):null,d.sickness_history_ref)||!same(s.source_files.map(v=>v.id).sort(),body.source_file_ids))throw fail('Eine Anspruchsquelle wurde gegenüber der gewählten Fassung ausgetauscht.');
 for(const v of [s.employment_terms,...s.work_schedules,...s.preparations,...s.agreements,...s.source_files,...s.sickness_history?[s.sickness_history]:[]])if(v.employee_id!==body.employee_id)throw fail('Die Anspruchsvorschau enthält eine fremde private Quelle.');
 return value;
}
export function payrollEntitlementValidator(body,previous=null,preview=null){
 const original=clone(body),prior=previous?clone(previous):null,prepared=preview?clone(preview):null;
 return value=>{payrollEntitlementRecord(value,original.employee_id,original.kind);
 if(value.revision!==(prior?.revision||0)+1||prior&&value.id!==prior.id||value.previous_hash!==(prior?.content_hash||null)||value.status!==original.status||!same(value.details,original.details)||!same(value.source_file_ids,original.source_file_ids)||value.preview_hash!==original.preview_hash||value.correction_reason!==(original.correction_reason||''))throw fail('Die Anspruchsquittung gehört nicht zum unveränderten ursprünglichen Auftrag.');
 if(prepared&&(!same(value.sources,prepared.source_snapshot)||!same(value.plan,prepared.plan)||value.source_hash!==prepared.source_hash))throw fail('Die angenommene Anspruchsfassung ersetzt die ausdrücklich geprüften Quellen.');
 if(value.status==='void'&&(!prior||!same(value.sources,prior.sources)||!same(value.plan,prior.plan)||value.source_hash!==prior.source_hash||value.preview_hash!==prior.preview_hash))throw fail('Die Aufhebung darf keinen früheren Anspruchs- oder Quellenstand ersetzen.');
 return value;};
}

export function payrollEntitlementMoney(value){
 const text=String(value??'').trim().replace(',','.');
 if(!/^\d{1,9}(?:\.\d{1,2})?$/.test(text))throw fail('Einen belegten EUR-Betrag ausdrücklich angeben, auch bekannte 0,00.');
 const [whole,fraction='']=text.split('.');return Number(BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0')));
}
export function payrollEntitlementDays(from,to){
 payrollFactDate(from);payrollFactDate(to);if(from>to)throw fail('Das Ende liegt vor dem Beginn.');
 const days=[];for(let day=new Date(from+'T12:00:00Z');day.toISOString().slice(0,10)<=to;day.setUTCDate(day.getUTCDate()+1)){if(days.length>=10000)throw fail('Den belegten Zeitraum eingrenzen.');days.push(day.toISOString().slice(0,10));}return days;
}
export function payrollEntitlementDaySource(sources,values,date){
 const schedules=sources.facts.filter(v=>values.work_schedule_ids.includes(v.id)&&v.kind==='work_schedule'),preparations=sources.preparations.filter(v=>values.preparation_ids.includes(v.id)),agreements=sources.agreements.filter(v=>values.agreement_ids.includes(v.id)&&v.effective_from<=date).sort((a,b)=>a.effective_from.localeCompare(b.effective_from));
 const days=schedules.flatMap(v=>v.details.days.filter(v=>v.date===date)),prepared=preparations.filter(v=>v.month===date.slice(0,7)),agreement=agreements.at(-1);
 if(days.length!==1||prepared.length!==1||!agreement)throw fail('Für '+date+' genau einen datierten Arbeitsplan, die abgeschlossene Monatsvorbereitung und die einschlägige Vereinbarung auswählen.');
 const worked=prepared[0].snapshot.approved_days.filter(v=>v.date===date).reduce((sum,v)=>sum+v.net_seconds,0);
 return {scheduled:days[0].scheduled_seconds,worked,agreement,federal_state:days[0].federal_state};
}

export function payrollEntitlementsUi(h){
 const {api,biz,el,button,field,form,panel,table,notice}=h;let active=null;
 const path=biz('/payroll/entitlements'),key=employee=>'payroll-entitlements-'+employee.id;
 const available=()=>payrollEntitlementRights(h.caps()).read;
 const action=fn=>h.action(async()=>{try{return await fn();}catch(error){if([401,403,404].includes(error.status)&&active?.isConnected)active.replaceChildren(notice('Die private Anspruchsfreigabe wurde entzogen.'));throw error;}},active);
 const money=value=>value===null||value===undefined?'Nicht ermittelt':h.formatMoney((value/100).toFixed(2));
 const options=(items,label)=>items.map(v=>[v.id,label(v)]);
 const originalOptions=sources=>options(sources.files,v=>v.filename);
 const boolValue=value=>value===true?'yes':value===false?'no':'';
 const yesNo=(name,label,value,required=true)=>field(name,label,'select',boolValue(value),{required,options:[['','Bitte ausdrücklich wählen'],['yes','Ja, belegt'],['no','Nein, belegt']]});
 const boolean=(value,label)=>{if(!['yes','no'].includes(value))throw fail(label+' ausdrücklich mit Ja oder Nein belegen.');return value==='yes';};
 const uid=()=>crypto.randomUUID().replaceAll('-','');
 async function fresh(employee,write=false,replay=false){const stamp=h.stamp(),access=await payrollEntitlementsAuthorize(api,employee.id,{write,replay});if(stamp!==h.stamp()||!available())throw fail('Die private Personalansicht wurde geändert.',403);return access;}
 function show(employee,title,body){if(!available())throw fail('Aktuelle globale Personalrechte fehlen.',403);active=body;body.setAttribute('data-payroll',employee.id);body.setAttribute('data-payroll-entitlement',employee.id);h.dialog(title,body);}
 function originals(sources,ids,name,label){return field(name,label,'multi',ids||[],{required:true,options:originalOptions(sources)});}
 function planView(kind,plan){
  const rows=[];
  if(kind==='sickness_history'){
   for(const [i,p]of (plan.prevention_cases||[]).entries())rows.push(panel('Zusammenhängender Verhinderungsfall '+(i+1),table(['Anspruch','Geprüfter Wert'],[['Ursprünglicher AU-Beginn',h.formatDate(p.original_au_from||p.from_date)],['Zählung in dieser Beschäftigung ab',h.formatDate(p.count_from)],['Anfangsrest',p.initial_remaining_days+' Kalendertage'],['Gemeinsames Fristende',h.formatDate(p.statutory_deadline)],['Entgeltfortzahlung',p.entitlement_calendar_days+' Kalendertage']])));
   if(plan.preemployment_periods?.length)rows.push(panel('Belegter Zeitraum vor Beschäftigungsbeginn',table(['Von','Bis','Anspruch aus dieser Beschäftigung'],plan.preemployment_periods.map(p=>[h.formatDate(p.from_date),h.formatDate(p.to_date),'Kein Entgeltanspruch vor dem vereinbarten Beginn']))));
   if(plan.phases)rows.push(panel('Geprüfte Phasen ohne doppelte Tageszählung',table(['Von','Bis','Maßgebende Ursache','Anspruch'],plan.phases.map(p=>[h.formatDate(p.from_date),h.formatDate(p.to_date),'Vorzeitenfall '+((plan.episodes||[]).findIndex(v=>v.episode_id===p.responsible_episode_id)+1),p.first_day_remaining_regular_wage?'Gewöhnlicher Restlohn des begonnenen Arbeitstags':p.entitled?'Entgeltfortzahlung':p.waiting_period?'Wartezeit':'Kein Entgeltfortzahlungsanspruch']))));
   for(const p of plan.episodes||[])rows.push(panel('Belegter Krankheitsfall '+h.formatDate(p.from_date)+' – '+h.formatDate(p.to_date),table(['Anspruch','Geprüfter Wert'],[['Zählung ab',h.formatDate(p.count_from)],['Wartezeit bis',h.formatDate(p.waiting_period_end)],['Entgeltfortzahlung von',p.entitlement_from?h.formatDate(p.entitlement_from):'Kein belegter Anspruch'],['Entgeltfortzahlung bis',p.entitlement_to?h.formatDate(p.entitlement_to):'Kein belegter Anspruch'],['Verbrauchte Vortage',String(p.prior_used_days)],['Verbleibende Tage',String(p.remaining_days)],['Restlicher erster Arbeitstag',p.first_day_remaining_regular_wage?h.formatDate(p.first_day_remaining_regular_wage):'Nicht einschlägig']])));
  }
  if(kind==='regular_absence')rows.push(table(['Anspruchstag','Bezahlte Ausfallzeit (Sekunden)','Tatsächliche Arbeitszeit (Sekunden)'],(plan.days||[]).map(v=>[h.formatDate(v.date),String(v.paid_absence_seconds),String(v.actual_work_seconds)])),notice('Belegtes Ausfallentgelt: '+money(plan.gross_minor)+'. Tatsächliche Projektzeit bleibt unverändert.'));
  if(kind==='vacation_reference')rows.push(table(['Urlaubsgrundlage','Geprüfter Wert'],[['Referenz von',h.formatDate(plan.reference_from)],['Referenz bis',h.formatDate(plan.reference_to)],['Tagesmittel als exakter Quotient',plan.workday_average?.numerator+' / '+plan.workday_average?.denominator],['Belegte Urlaubstage',(plan.vacation_days||[]).map(v=>h.formatDate(v)).join(', ')],['Urlaubsentgelt',money(plan.gross_minor)],['Sachbezugsersatz',money(plan.in_kind_cash_compensation_minor)],['Fällig vor',h.formatDate(plan.due_before)]]));
  if(kind==='unpaid_continuation')rows.push(table(['Unterbrechungszeitraum','Beitragspflichtige Beschäftigung besteht fort','Kalendertage'],(plan.intervals||[]).map(v=>[h.formatDate(v.from)+' – '+h.formatDate(v.to),v.employment_for_contributions_continues?'Ja':'Nein',String(v.calendar_days)])),...(plan.continuation_windows||[]).map(v=>notice('Gesetzliche Monatsfrist bis '+h.formatDate(v.statutory_deadline)+'. Steuer-Lohnzahlungszeitraum und tatsächliche Versicherungsmitgliedschaft werden nicht automatisch daraus abgeleitet.')));
  return el('div',{class:'stack'},...rows,notice('Dieser Nachweis bestätigt nur den ausgewiesenen Anspruchsbaustein. Die vollständige Lohnberechnung, eine Zahlung und amtliche Meldungen bleiben getrennte Vorgänge.'));
 }
 async function inspect(employee,value,historical=false){
  const access=await fresh(employee);payrollEntitlementRecord(value,employee.id);
  const body=el('div',{class:'stack'},table(['Anspruchsnachweis','Stand'],[['Art',PAYROLL_ENTITLEMENT_KINDS[value.kind]],['Fassung',String(value.revision)],['Status',value.status==='active'?'Aktiv':'Aufgehoben'],['Zeitraum',h.formatDate(value.effective_from)+' – '+h.formatDate(value.effective_to)],['Prüfvermerk',value.details.verification_note],['Korrekturgrund',value.correction_reason||'Ersterfassung']]),planView(value.kind,value.plan));
  for(const id of value.source_file_ids){const file=value.sources.source_files.find(v=>v.id===id);if(file&&h.onOriginal)body.append(button('Personaloriginal: '+file.filename,()=>action(async()=>{await fresh(employee);await h.onOriginal(employee,file);}), 'small'));}
  if(!historical)body.append(button('Anspruchshistorie öffnen',()=>action(async()=>{await fresh(employee);const stamp=h.stamp(),page=await api.get(biz('/payroll/entitlements/'+value.id+'/history'));if(stamp!==h.stamp())return;if(page.employee_id!==employee.id||!Array.isArray(page.items)||page.items.some((v,i)=>payrollEntitlementRecord(v,employee.id,value.kind).id!==value.id||v.revision!==i+1))throw fail('Die Anspruchshistorie stimmt nicht mit dem gewählten Nachweis überein.');show(employee,'Anspruchshistorie',el('div',{class:'stack'},...page.items.map(v=>panel('Fassung '+v.revision,el('p',{},v.correction_reason||'Ersterfassung'),button('Diese Anspruchsfassung öffnen',()=>action(()=>inspect(employee,v,true)),'small')))));}),'small'));
  if(!historical&&value.status==='active'&&access.rights.approve&&access.sources.can_approve&&access.sources.writes_enabled&&!api.pendingCommandValues(key(employee),path))body.append(button('Anspruch korrigieren',()=>action(()=>edit(employee,value.kind,value)),'small'),button('Fälschlichen Anspruch aufheben',()=>action(()=>cancel(employee,value)),'small'));
  body.append(button('Zur Anspruchsübersicht',()=>action(()=>open(employee)),'small'));show(employee,(historical?'Historische Anspruchsfassung · ':'')+PAYROLL_ENTITLEMENT_KINDS[value.kind],body);
 }
 async function save(employee,body,previous,preview=null){
  const pending=api.pendingCommandValues(key(employee),path);if(pending&&!same(pending,body))throw fail('Zuerst den unverändert offenen Anspruchsauftrag klären.',409);
  await fresh(employee,true,!!pending);const result=pending?await api.retry(key(employee)):await api.mutate(key(employee),path,body,{validate:payrollEntitlementValidator(body,previous,preview)});await fresh(employee);await inspect(employee,result);
 }
 async function confirm(employee,body,previous){
  await fresh(employee);const stamp=h.stamp(),preview=payrollEntitlementPreview(await api.post(biz('/payroll/entitlements/preview'),payrollEntitlementPreviewInput(body)),body);if(stamp!==h.stamp())return;await fresh(employee);
  const complete={...body,preview_hash:preview.preview_hash},content=el('div',{class:'stack'},planView(body.kind,preview.plan));
  if(preview.can_confirm&&preview.can_approve&&preview.writes_enabled)content.append(form('',[field('accepted','Ich bestätige genau diesen geprüften Anspruchsbaustein und seine Originale.','checkbox',false,{required:true})],async values=>{if(values.accepted!==true)throw fail('Den geprüften Anspruch ausdrücklich bestätigen.');await save(employee,complete,previous,preview);},{key:'payroll-entitlement-confirm-'+employee.id,submit:'Geprüften Anspruchsbaustein festhalten'}));else content.append(notice('Der aktuelle Quellenstand oder die Freigabe erlaubt keine Bestätigung.'));
  show(employee,'Anspruchsbaustein prüfen',content);
 }
 async function cancel(employee,previous){
  await fresh(employee,true);show(employee,'Fälschlichen Anspruch aufheben',form('',[field('correction_reason','Belegter Aufhebungsgrund','text','',{required:true}),field('confirmed','Ich bestätige die Aufhebung; frühere Abrechnungen bleiben unverändert.','checkbox',false,{required:true})],async values=>{if(values.confirmed!==true)throw fail('Die Aufhebung ausdrücklich bestätigen.');const access=await fresh(employee,true);await save(employee,{employee_id:employee.id,employee_revision:access.sources.employee.revision,kind:previous.kind,id:previous.id,revision:previous.revision,status:'void',details:clone(previous.details),source_file_ids:[...previous.source_file_ids],preview_hash:previous.preview_hash,correction_reason:note(values.correction_reason,'Aufhebungsgrund'),confirmed:true},previous);},{key:'payroll-entitlement-void-'+employee.id,submit:'Anspruch belegt aufheben',extra:planView(previous.kind,previous.plan)}));
 }
 async function open(employee){
  const access=await fresh(employee),pending=api.pendingCommandValues(key(employee),path),body=el('div',{class:'stack'},notice('Private Nachweise zu Krankheitsvorzeiten, regelmäßiger Ausfallvergütung, Urlaubsentgelt und unbezahlten Unterbrechungen.'));
  if(pending)body.append(panel('Anspruchsbestätigung offen',notice('Der Auftrag kann bereits gespeichert sein. Die Wiederholung verwendet dieselben Werte und dieselbe Vorgangskennung.'),access.rights.approve&&access.sources.can_approve?button('Ursprünglichen Anspruchsauftrag erneut senden',()=>action(async()=>{await fresh(employee,true,true);const result=await api.retry(key(employee));await inspect(employee,result);}),'primary'):null));
  for(const [kind,label]of Object.entries(PAYROLL_ENTITLEMENT_KINDS))body.append(panel(label,!pending&&access.rights.approve&&access.sources.can_approve&&access.sources.writes_enabled?button(label+' erfassen',()=>action(()=>edit(employee,kind)),'primary'):null,...access.sources.entitlements.filter(v=>v.kind===kind).map(v=>el('div',{class:'list-row'},el('div',{},h.formatDate(v.effective_from)+' – '+h.formatDate(v.effective_to)+' · Fassung '+v.revision+(v.status==='void'?' · aufgehoben':'')),button('Anspruchsnachweis öffnen',()=>action(()=>inspect(employee,v)),'small')))));
  show(employee,'Private Anspruchsnachweise · '+employee.name,body);
 }
 async function edit(employee,kind,previous=null){
  const {sources}=await fresh(employee,true);if(api.pendingCommandValues(key(employee),path))return open(employee);
  const d=previous?.details||{},input=d.input||{},caseKey=d.case_key||uid();
  const common=[field('employment_terms_id','Belegte Beschäftigungsfassung','select',d.employment_terms_ref?.id||'',{required:true,options:[['','Bitte ausdrücklich wählen'],...options(sources.facts.filter(v=>v.kind==='employment_terms'&&v.status==='active'),v=>h.formatDate(v.effective_from)+' · Fassung '+v.revision)]}),
   field('agreement_ids','Alle einschlägigen Entgeltvereinbarungen','multi',(d.agreement_refs||[]).map(v=>v.id),{required:true,options:options(sources.agreements,v=>h.formatDate(v.effective_from)+' · '+money(v.amount_minor)+(v.pay_basis==='hourly'?' / Stunde':' / Monat')+' · Fassung '+v.revision)}),
   field('work_schedule_ids','Gebundene datierte Arbeitspläne','multi',(d.work_schedule_refs||[]).map(v=>v.id),{options:options(sources.facts.filter(v=>v.kind==='work_schedule'&&v.status==='active'),v=>v.details.month+' · Fassung '+v.revision)}),
   field('preparation_ids','Gebundene abgeschlossene Monatsvorbereitungen','multi',(d.preparation_refs||[]).map(v=>v.id),{options:options(sources.preparations,v=>v.month+' · Fassung '+v.revision)}),
   originals(sources,previous?.source_file_ids,'source_file_ids','Geschützte Originale für diesen Anspruch'),
   field('verification_note','Nachvollziehbarer Anspruchsprüfvermerk','text',d.verification_note||'',{required:true}),
   ...previous?[field('correction_reason','Belegter Korrekturgrund','text','',{required:true})]:[]];
  const extra=[];
  if(kind==='sickness_history')extra.push(field('sickness_mode','Belegte Form des Krankheitsverlaufs','select',input.employment_commencement?'preemployment':input.prevention_cases?'combined':previous?'separate':'',{required:true,options:[['','Bitte ausdrücklich wählen'],...Object.entries(PAYROLL_SICKNESS_MODES)]}),field('complete_from','Belegte vollständige Vorzeiten ab','date',input.complete_from||'',{required:true}),field('complete_through','Belegte vollständige Vorzeiten bis','date',input.complete_through||'',{required:true}),field('count','Anzahl vollständig belegter Krankheitsfälle, auch bekannte 0','integer',input.episodes?.length??'',{required:true,min:0,max:2000}));
  if(kind==='regular_absence')extra.push(field('absence_kind','Belegte Art der regelmäßigen Ausfallvergütung','select',input.kind||'',{required:true,options:[['','Bitte ausdrücklich wählen'],...Object.entries(PAYROLL_ABSENCE_KINDS)]}),field('sickness_history_id','Geprüfter Krankheitsverlauf bei Krankheit','select',d.sickness_history_ref?.id||'',{options:[['','Kein Krankheitsverlauf für einen eigenständigen Feiertag'],...options(sources.entitlements.filter(v=>v.kind==='sickness_history'&&v.status==='active'),v=>h.formatDate(v.effective_from)+' – '+h.formatDate(v.effective_to)+' · Fassung '+v.revision)]}),field('from','Erster tatsächlich zu prüfender Ausfalltag','date',input.days?.[0]?.date||'',{required:true}),field('to','Letzter tatsächlich zu prüfender Ausfalltag','date',input.days?.at(-1)?.date||'',{required:true}));
  if(kind==='vacation_reference')extra.push(field('vacation_from','Erster tatsächlicher Urlaubstag','date',input.vacation_from||'',{required:true}),field('vacation_to','Letzter tatsächlicher Urlaubstag','date',input.vacation_to||'',{required:true}),field('in_kind_daily','Belegter täglicher Sachbezugsersatz (EUR), auch bekannte 0','decimal',input.in_kind_daily_minor===undefined?'':(input.in_kind_daily_minor/100).toFixed(2),{required:true}));
  if(kind==='unpaid_continuation')extra.push(field('from','Tatsächlicher Beginn ohne Entgeltanspruch','date',input.from||'',{required:true}),field('to','Tatsächliches Ende des zu prüfenden Zeitraums','date',input.to||'',{required:true}),field('count','Anzahl belegter Ausnahmetatbestände, auch bekannte 0','integer',input.exceptions?.length??'',{required:true,min:0,max:2000}),field('employment_continues','Das Beschäftigungsverhältnis besteht nach Beleg fort.','checkbox',false,{required:true}),field('no_wage_claim','Für diesen Zeitraum besteht nach Beleg kein Entgeltanspruch.','checkbox',false,{required:true}),field('no_intervening_paid_days','Es gibt keine dazwischenliegenden entgeltberechtigten Tage.','checkbox',false,{required:true}));
  show(employee,(previous?'Korrigieren: ':'Erfassen: ')+PAYROLL_ENTITLEMENT_KINDS[kind],form('',[...common,...extra],async values=>{await fresh(employee,true);await typed(employee,sources,kind,{...values,case_key:caseKey},previous);},{key:'payroll-entitlement-sources-'+employee.id,submit:'Konkrete Anspruchsangaben belegen'}));
 }
 async function typed(employee,sources,kind,values,previous){
  const prior=previous?.details.input||{},fields=[],explanation=[];
  const outer=values.source_file_ids;
  if(!Array.isArray(outer)||!outer.length)throw fail('Geschützte Anspruchsoriginale auswählen.');
  const evidence=(name,label,selected)=>originals({...sources,files:sources.files.filter(v=>outer.includes(v.id))},selected,name,label);
  const fileRefs=(name,input)=>payrollEntitlementEvidence(sources,input[name],outer);
  const terms=sources.facts.find(v=>v.id===values.employment_terms_id&&v.kind==='employment_terms'&&v.status==='active');
  if(!terms)throw fail('Die konkrete Beschäftigungsfassung auswählen.');
  const agreements=sources.agreements.filter(v=>values.agreement_ids.includes(v.id));
  if(!agreements.length)throw fail('Einschlägige Entgeltvereinbarungen auswählen.');
  let assemble;
  if(kind==='sickness_history'){
   if(agreements.some(v=>v.pay_basis!==agreements[0].pay_basis))throw fail('Wechselnde Entgeltbasen benötigen getrennte belegte Verhinderungsverläufe.');
   payrollEntitlementDays(values.complete_from,values.complete_through);
   const mode=values.sickness_mode,phased=mode!=='separate';
   if(!Object.hasOwn(PAYROLL_SICKNESS_MODES,mode))throw fail('Die tatsächliche Form des Krankheitsverlaufs ausdrücklich wählen.');
   const episodes=Array.from({length:values.count},(_,i)=>({id:prior.episodes?.[i]?.id||uid(),group:uid(),caseId:uid(),old:prior.episodes?.[i]||{}}));
   const priorCase=old=>(prior.prevention_cases||[]).find(v=>v.episode_ids.includes(old.id));
   fields.push(evidence('history_files','Originale für die Vollständigkeit der Vorzeiten',prior.history_evidence_refs?.map(v=>v.id)));
   if(phased)fields.push(evidence('prevention_files','Originale für die zusammenhängenden Verhinderungsfälle und ihre Zuordnung',[...new Set((prior.prevention_cases||[]).flatMap(v=>v.evidence_refs.map(r=>r.id)))]));
   if(mode==='preemployment')fields.push(field('contract_concluded_on','Tatsächliches Datum des Vertragsabschlusses vor der Erkrankung','date',prior.employment_commencement?.contract_concluded_on||'',{required:true}),evidence('commencement_files','Vertragsoriginal für den vereinbarten Beschäftigungsbeginn',prior.employment_commencement?.evidence_refs.map(v=>v.id)));
   explanation.push(notice(phased?'Hinzutretende Ursachen erhalten keine zusätzliche Sechswochenfrist. Ordnen Sie jede Ursache ausdrücklich einem belegten Verhinderungsfall zu.':'Jeder getrennte Verhinderungsfall benötigt belegte vorherige Arbeitsfähigkeit.'));
   for(const [i,item]of episodes.entries()){
    const p='episode_'+i+'_',old=item.old,groupIndex=prior.episodes?.findIndex(v=>v.continuation_group===old.continuation_group)??-1,oldCase=priorCase(old),caseIndex=oldCase?episodes.findIndex(v=>oldCase.episode_ids.includes(v.id)):-1;
    item.caseId=oldCase&&caseIndex===i?oldCase.id:item.caseId;
    fields.push(field(p+'from','Vorzeitenfall '+(i+1)+': Beginn','date',old.from||'',{required:true}),field(p+'to','Vorzeitenfall '+(i+1)+': Ende','date',old.to||'',{required:true}),field(p+'onset','Vorzeitenfall '+(i+1)+': tatsächlicher Beginn zur Arbeit','select',old.onset||'',{required:true,options:[['','Bitte ausdrücklich wählen'],...Object.entries(PAYROLL_ONSETS),...phased?[['during_existing_au','Hinzugetreten während bestehender Arbeitsunfähigkeit']]:[],...mode==='preemployment'?[['before_employment','Nach Vertragsabschluss, vor Beschäftigungsbeginn']]:[]]}),field(p+'first_scheduled_day','Vorzeitenfall '+(i+1)+': erster ausgefallener Solltag nur bei Stundenlohn-AU am freien Tag','date',old.first_scheduled_day||''),field(p+'group','Vorzeitenfall '+(i+1)+': belegter Fortsetzungszusammenhang','select',old.continuation_group?(groupIndex<i?'same:'+groupIndex:'new'):'',{required:true,options:[['','Bitte ausdrücklich wählen'],['new','Eigenständiger Fortsetzungsfall'],...episodes.slice(0,i).map((_,j)=>['same:'+j,'Derselbe Fortsetzungsfall wie Vorzeitenfall '+(j+1)])]}));
    if(phased)fields.push(field(p+'case','Vorzeitenfall '+(i+1)+': belegter Verhinderungsfall','select',oldCase?(caseIndex<i?'same:'+caseIndex:'new'):'',{required:true,options:[['','Bitte ausdrücklich wählen'],['new','Neuer Verhinderungsfall nach belegter Arbeitsfähigkeit'],...episodes.slice(0,i).map((_,j)=>['same:'+j,'Hinzugetreten zum Verhinderungsfall von Vorzeitenfall '+(j+1)])]}),yesNo(p+'recovery_before','Vorzeitenfall '+(i+1)+': vorherige Arbeitsfähigkeit belegt (Nein bei fortbestehender AU)',undefined));
    else fields.push(field(p+'recovery_before','Vorzeitenfall '+(i+1)+': Erholung vor dem neuen Verhinderungsfall ist belegt.','checkbox',false,{required:true}));
    fields.push(field(p+'unculpable','Vorzeitenfall '+(i+1)+': Unverschuldete Arbeitsverhinderung ist belegt.','checkbox',false,{required:true}),evidence(p+'files','Vorzeitenfall '+(i+1)+': konkrete Originale',old.evidence_refs?.map(v=>v.id)));
   }
   assemble=input=>{
    const rows=[];
    for(const [i,item]of episodes.entries()){
     const p='episode_'+i+'_',choice=input[p+'group'];let group;
     if(choice==='new')group=prior.episodes?.findIndex(v=>v.continuation_group===item.old.continuation_group)===i?item.old.continuation_group:item.group;
     else if(/^same:\d+$/.test(choice||'')&&Number(choice.slice(5))<i)group=rows[Number(choice.slice(5))].continuation_group;
     else throw fail('Den Fortsetzungszusammenhang ausdrücklich wählen.');
     const recovery=phased?boolean(input[p+'recovery_before'],'Belegte vorherige Arbeitsfähigkeit'):input[p+'recovery_before'];
     if(typeof recovery!=='boolean'||!phased&&recovery!==true||input[p+'unculpable']!==true)throw fail('Ungeklärte Verhinderung oder Verschulden bleibt gesondert zu klären.');
     rows.push({id:item.id,from:payrollFactDate(input[p+'from']),to:payrollFactDate(input[p+'to']),onset:input[p+'onset'],first_scheduled_day:payrollFactDate(input[p+'first_scheduled_day'],true),continuation_group:group,recovery_before:recovery,unculpable:true,evidence_refs:fileRefs(p+'files',input)});
    }
    return payrollSicknessStructure({employment_from:terms.details.employment_from,employment_to:terms.details.employment_to,pay_basis:agreements[0].pay_basis,complete_from:values.complete_from,complete_through:values.complete_through,history_evidence_refs:fileRefs('history_files',input),episodes:rows},mode,episodes.map((_,i)=>input['episode_'+i+'_case']),episodes.map(v=>v.caseId),phased?fileRefs('prevention_files',input):[],mode==='preemployment'?{contract_concluded_on:payrollFactDate(input.contract_concluded_on),evidence_refs:fileRefs('commencement_files',input)}:null);
   };
  }else if(kind==='regular_absence'){
   const dates=payrollEntitlementDays(values.from,values.to);if(dates.length>366)throw fail('Höchstens 366 konkrete Ausfalltage je Anspruch wählen.');
   const history=sources.entitlements.find(v=>v.id===values.sickness_history_id&&v.kind==='sickness_history');
   if(values.absence_kind!=='public_holiday'&&!history)throw fail('Für Krankheit den berechneten Vorzeiten-/Anspruchsnachweis auswählen.');
   if(values.absence_kind==='public_holiday'&&history)throw fail('Ein eigenständiger Feiertagsfall verwendet keinen Krankheitsverlauf.');
   const days=dates.map(date=>({date,...payrollEntitlementDaySource(sources,values,date)}));
   if(days.some(v=>v.agreement.pay_basis!=='hourly'||v.agreement.amount_minor!==days[0].agreement.amount_minor))throw fail('Diese Ausfallvergütung benötigt einen unveränderten belegten regelmäßigen Stundenlohn.');
   fields.push(evidence('case_files','Originale für die regelmäßige Ausfallvergütung',prior.evidence_refs?.map(v=>v.id)));
   explanation.push(table(['Ausfalltag','Gebundene Sollzeit (Sekunden)','Freigegebene Istzeit (Sekunden)'],days.map(v=>[h.formatDate(v.date),String(v.scheduled),String(v.worked)])),notice('Belegter regelmäßiger Stundenlohn: '+money(days[0].agreement.amount_minor)+'. Die Zeiten und der Krankheitsanspruch stammen aus den gewählten Quellen.'));
   for(const [i,day]of days.entries()){const old=prior.days?.find(v=>v.date===day.date)||{},p='day_'+i+'_';fields.push(yesNo(p+'only','Ausfalltag '+day.date+': Abwesenheit ist alleiniger Ausfallgrund',old.absence_is_only_cause),...(values.absence_kind==='public_holiday'?[yesNo(p+'adjacent','Feiertag '+day.date+': Unentschuldigtes Fehlen unmittelbar davor oder danach',old.holiday_adjacent_unexcused)]:[]),evidence(p+'files','Ausfalltag '+day.date+': konkrete Originale',old.evidence_refs?.map(v=>v.id)));}
   assemble=input=>({kind:values.absence_kind,hourly_rate_minor:days[0].agreement.amount_minor,evidence_refs:fileRefs('case_files',input),days:days.map((day,i)=>{const p='day_'+i+'_',episodes=history?.plan.episodes||[],entitled=values.absence_kind==='public_holiday'||episodes.some(v=>values.absence_kind==='first_sickness_day_regular_wage'?v.first_day_remaining_regular_wage===day.date:v.entitlement_from&&v.entitlement_from<=day.date&&v.entitlement_to>=day.date);return {date:day.date,scheduled_regular_seconds:day.scheduled,worked_regular_seconds:day.worked,entitled:!!entitled,absence_is_only_cause:boolean(input[p+'only'],'Alleiniger Ausfallgrund'),holiday_adjacent_unexcused:values.absence_kind==='public_holiday'?boolean(input[p+'adjacent'],'Feiertagsausschluss'):null,evidence_refs:fileRefs(p+'files',input)};})});
  }else if(kind==='vacation_reference'){
   const vacation=payrollEntitlementDays(values.vacation_from,values.vacation_to),first=new Date(values.vacation_from+'T12:00:00Z'),last=new Date(first);first.setUTCDate(first.getUTCDate()-91);last.setUTCDate(last.getUTCDate()-1);
   const reference=payrollEntitlementDays(first.toISOString().slice(0,10),last.toISOString().slice(0,10));
   const scheduled=date=>{const rows=sources.facts.filter(v=>values.work_schedule_ids.includes(v.id)&&v.kind==='work_schedule').flatMap(v=>v.details.days.filter(v=>v.date===date));if(rows.length!==1)throw fail('Für den Referenztag '+date+' fehlt eine eindeutige belegte Sollplanfassung.');return rows[0].scheduled_seconds;};
   const actual=vacation.map(date=>({date,...payrollEntitlementDaySource(sources,values,date)})).filter(v=>v.scheduled>0);
   if(!actual.length)throw fail('Keine belegten Soll-Urlaubstage im gewählten Zeitraum.');reference.forEach(scheduled);
   fields.push(evidence('case_files','Originale für die gesamte Urlaubsreferenz',prior.evidence_refs?.map(v=>v.id)));
   for(const [i,date]of reference.entries()){const p='reference_'+i+'_',old=prior.reference_days?.find(v=>v.date===date)||{};for(const [name,label]of [['base_earnings_minor','Belegter Grundverdienst'],['overtime_earnings_minor','Darin enthaltene Überstundenvergütung'],['protected_reduction_minor','Belegte geschützte Entgeltminderung'],['permanent_raise_minor','Belegte dauerhafte Verdiensterhöhung']])fields.push(field(p+name,date+': '+label+' (EUR), auch bekannte 0','decimal',old[name]===undefined?'':(old[name]/100).toFixed(2),{required:true}));fields.push(evidence(p+'files',date+': konkrete Referenzoriginale',old.evidence_refs?.map(v=>v.id)));}
   for(const [i,day]of actual.entries())fields.push(evidence('vacation_'+i+'_files','Urlaubstag '+day.date+': konkrete Originale',prior.vacation_days?.find(v=>v.date===day.date)?.evidence_refs?.map(v=>v.id)));
   explanation.push(notice('Die Referenz umfasst genau 91 Kalendertage. Vertragliche Arbeitstage und Sollzeiten stammen aus den gebundenen Plänen. Jeder Geldbetrag ist ausdrücklich zu belegen; leere Angaben werden nicht zu 0,00.'));
   assemble=input=>({vacation_from:values.vacation_from,vacation_to:values.vacation_to,in_kind_daily_minor:payrollEntitlementMoney(values.in_kind_daily),evidence_refs:fileRefs('case_files',input),reference_days:reference.map((date,i)=>{const p='reference_'+i+'_';return {date,contractual_workday:scheduled(date)>0,...Object.fromEntries(['base_earnings_minor','overtime_earnings_minor','protected_reduction_minor','permanent_raise_minor'].map(k=>[k,payrollEntitlementMoney(input[p+k])])),evidence_refs:fileRefs(p+'files',input)};}),vacation_days:actual.map((v,i)=>({date:v.date,scheduled_regular_seconds:v.scheduled,evidence_refs:fileRefs('vacation_'+i+'_files',input)}))});
  }else{
   payrollEntitlementDays(values.from,values.to);if(values.employment_continues!==true||values.no_wage_claim!==true||values.no_intervening_paid_days!==true)throw fail('Fortbestehende Beschäftigung, fehlenden Entgeltanspruch und fehlende Zwischentage ausdrücklich belegen.');
   fields.push(evidence('case_files','Originale für die unbezahlte Unterbrechung',prior.evidence_refs?.map(v=>v.id)));
   for(let i=0;i<values.count;i++){const old=prior.exceptions?.[i]||{},p='exception_'+i+'_';fields.push(field(p+'kind','Ausnahmetatbestand '+(i+1)+': belegte Art','select',old.kind||'',{required:true,options:[['','Bitte ausdrücklich wählen'],...Object.entries(PAYROLL_CONTINUATION_EXCEPTIONS)]}),field(p+'from','Ausnahmetatbestand '+(i+1)+': von','date',old.from||'',{required:true}),field(p+'to','Ausnahmetatbestand '+(i+1)+': bis','date',old.to||'',{required:true}),field(p+'scope','Ausnahmetatbestand '+(i+1)+': betrifft nach Beleg dieses Beschäftigungsverhältnis.','checkbox',false,{required:true}),evidence(p+'files','Ausnahmetatbestand '+(i+1)+': konkrete Originale',old.evidence_refs?.map(v=>v.id)));}
   assemble=input=>({from:values.from,to:values.to,employment_to:terms.details.employment_to,employment_continues:true,no_wage_claim:true,intervening_paid_days:[],evidence_refs:fileRefs('case_files',input),exceptions:Array.from({length:values.count},(_,i)=>{const p='exception_'+i+'_';if(input[p+'scope']!==true)throw fail('Die Ausnahme ausdrücklich diesem Beschäftigungsverhältnis zuordnen.');return {kind:input[p+'kind'],from:payrollFactDate(input[p+'from']),to:payrollFactDate(input[p+'to']),employment_scope:'this_employment',evidence_refs:fileRefs(p+'files',input)};})});
  }
  fields.push(field('confirmed','Ich bestätige diese konkreten Anspruchsangaben und Originale.','checkbox',false,{required:true}));
  show(employee,'Konkrete Angaben: '+PAYROLL_ENTITLEMENT_KINDS[kind],form('',fields,async input=>{if(input.confirmed!==true)throw fail('Die konkreten Anspruchsangaben ausdrücklich bestätigen.');const body=payrollEntitlementInput(employee.id,sources,kind,{...values,input:assemble(input)},previous);await confirm(employee,body,previous);},{key:'payroll-entitlement-details-'+employee.id,submit:'Anspruch unverbindlich prüfen',extra:el('div',{class:'stack'},...explanation)}));
 }
 return {available,open};
}
