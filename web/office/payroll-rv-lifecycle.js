/* Private originals for a single continuous commercial-minijob RV episode. */
import {payrollFactDate,payrollFactMonth,payrollFactRef} from './payroll-facts.js';

export const RV_RULE='de_2026_minijob_rv_revocation_v1';
export const RV_RULE_HASH='0d63413c7af9c81ebcb99244d98945060198a28c72ac0631b5e605a7304a93e8';
export const RV_PATH='/business/payroll/rv-lifecycle';
export const RV_STATUS={exempt:'RV-Befreiung belegt',compulsory_after_revocation:'RV-Pflicht nach belegter Aufhebung',unresolved:'RV-Status noch ungeklärt'};
const HASH=/^[a-f0-9]{64}$/,ID=/^[a-f0-9]{32}$/;
const copy=v=>JSON.parse(JSON.stringify(v));
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const fail=(message,status=400)=>Object.assign(new Error(message),{status});
const key=id=>'payroll-rv-lifecycle-'+id;
const shape=(v,fields)=>{if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join('|')!==fields.split(' ').sort().join('|'))throw fail('Die vollständigen ursprünglichen RV-Angaben fehlen.');};
const note=v=>{if(typeof v!=='string'||!v.trim()||v.length>3000||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(v))throw fail('Den tatsächlichen RV-Prüfvermerk vollständig angeben.');return v;};
const hash=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(v))))),b=>b.toString(16).padStart(2,'0')).join('');
const ref=v=>{shape(v,'id revision content_hash');return payrollFactRef(v);};
export const payrollRvSelection=value=>{const r=payrollFactRef(value);return r.id+'/'+r.revision+'/'+r.content_hash;};
const refs=values=>{
 if(!Array.isArray(values)||values.length>100)throw fail('Der vollständige bisherige RV-Verlauf fehlt.');
 const result=values.map(ref).sort((a,b)=>a.id.localeCompare(b.id)||a.revision-b.revision);
 if(new Set(result.map(r=>r.id+'/'+r.revision)).size!==result.length)throw fail('Jede ursprüngliche RV-Fassung genau einmal angeben.');
 return result;
};

export function payrollRvAssessment(a){
 shape(a,'schema_version employee_id episode_id employment_from employment_to target_month reviewed_as_of sole_continuous_commercial_minijob_confirmed no_old_age_or_other_exclusion_confirmed established_exemption revocation review_note');
 if(a.schema_version!==1||!ID.test(a.employee_id||'')||a.episode_id!==a.employee_id)throw fail('Die tatsächliche Person und durchgehende Beschäftigung fehlen.');
 for(const k of ['employment_from','reviewed_as_of'])payrollFactDate(a[k]);
 payrollFactDate(a.employment_to,true);payrollFactMonth(a.target_month);note(a.review_note);
 for(const k of ['sole_continuous_commercial_minijob_confirmed','no_old_age_or_other_exclusion_confirmed'])if(typeof a[k]!=='boolean')throw fail('Den tatsächlichen Beschäftigungsumfang ausdrücklich prüfen.');
 const e=a.established_exemption;shape(e,'effective_from profile_ref evidence_ref established_status_confirmed');
 payrollFactDate(e.effective_from);ref(e.profile_ref);ref(e.evidence_ref);
 if(typeof e.established_status_confirmed!=='boolean')throw fail('Die bereits bestehende RV-Befreiung ausdrücklich prüfen.');
 const r=a.revocation;
 if(r!==null){
  shape(r,'received_on request_format request_ref notification_received_on notification_ref authority_status objection_deadline_on deadline_ref deadline_review_confirmed authority_status_on authority_evidence_ref review_note');
  payrollFactDate(r.received_on);ref(r.request_ref);note(r.review_note);
  if(r.received_on<'2026-07-01'||!['written','electronic'].includes(r.request_format)||!['not_notified','pending','non_objection_verified','objected'].includes(r.authority_status)||typeof r.deadline_review_confirmed!=='boolean')throw fail('Antragseingang, Antragsform und tatsächlichen Verfahrensstand ausdrücklich belegen.');
  for(const [date,file]of [['notification_received_on','notification_ref'],['objection_deadline_on','deadline_ref'],['authority_status_on','authority_evidence_ref']]){
   if((r[date]===null)!==(r[file]===null))throw fail('Jeder Verfahrenszeitpunkt benötigt sein unverändertes Original.');
   if(r[date]!==null){payrollFactDate(r[date]);ref(r[file]);if(date!=='objection_deadline_on'&&r[date]>a.reviewed_as_of)throw fail('Zukünftige Verfahrensereignisse sind nicht bestätigt.');}
  }
  if(r.authority_status==='non_objection_verified'&&(!r.notification_ref||!r.deadline_ref||!r.deadline_review_confirmed||!r.authority_evidence_ref||r.authority_status_on<=r.objection_deadline_on))throw fail('Den abgeschlossenen Nichtwiderspruch samt tatsächlich geprüfter Frist belegen.');
 }
 return a;
}

function snapshot(s,a,employeeId){
 shape(s,'schema_version rule_version employee details original_profile source_files prior_assessments');
 shape(s.details,'assessment prior_assessment_refs');
 if(s.schema_version!==1||s.rule_version!==RV_RULE||s.employee?.id!==employeeId||!same(s.details.assessment,a)||a.employee_id!==employeeId||a.episode_id!==employeeId||a.employment_from!==s.employee.employment_from||a.employment_to!==s.employee.employment_to)throw fail('Die RV-Quellen gehören nicht unverändert zur gewählten Person.');
 const p=s.original_profile;payrollFactRef(p);
 if(p.employee_id!==employeeId||p.profile?.employment_kind!=='minijob'||p.profile.minijob_rv_exempt!==true||(p.profile.special_cases||[]).length||!same(payrollFactRef(p),a.established_exemption.profile_ref))throw fail('Das ursprüngliche befreite Minijobprofil wurde ersetzt oder enthält einen gesondert zu prüfenden Fall.');
 if(!Array.isArray(s.source_files)||!s.source_files.length||new Set(s.source_files.map(f=>f.id)).size!==s.source_files.length||s.source_files.some(f=>f.employee_id!==employeeId||f.purpose!=='personnel'||f.revision!==1||!HASH.test(f.sha256||'')))throw fail('Die privaten Personaloriginale gehören nicht zu dieser Person.');
 const originals=s.source_files.map(f=>({id:f.id,revision:1,content_hash:f.content_hash}));originals.forEach(ref);
 const required=[a.established_exemption.evidence_ref,...a.revocation?['request_ref','notification_ref','deadline_ref','authority_evidence_ref'].map(k=>a.revocation[k]).filter(Boolean):[]];
 if(required.some(r=>!originals.some(f=>same(f,r))))throw fail('Der konkrete unveränderte Verfahrensnachweis fehlt.');
 if(!Array.isArray(s.prior_assessments)||!same(refs(s.prior_assessments.map(p=>p.reference)),refs(s.details.prior_assessment_refs)))throw fail('Der vollständige frühere RV-Verlauf wurde ersetzt.');
 for(const p of s.prior_assessments){shape(p,'reference assessment');payrollRvAssessment(p.assessment);if(p.assessment.employee_id!==employeeId||p.assessment.reviewed_as_of>a.reviewed_as_of)throw fail('Der frühere RV-Verlauf gehört nicht unverändert zu dieser Prüfung.');}
 return s;
}

function checkPlan(p,s){
 const a=s.details.assessment;payrollRvAssessment(a);
 if(!p||p.rule_version!==RV_RULE||p.rules_sha256!==RV_RULE_HASH||p.employee_id!==a.employee_id||p.episode_id!==a.episode_id||p.month!==a.target_month||!Object.hasOwn(RV_STATUS,p.status)||!Array.isArray(p.blockers)||p.can_bind_payroll!==(p.blockers.length===0)||p.can_determine!==p.can_bind_payroll||p.minijob_rv_exempt!==(p.can_bind_payroll?p.status==='exempt':null)||['creates_profile','payment_created','external_transmission','official_system_approval'].some(k=>p[k]!==false)||!HASH.test(p.source_hash||'')||!HASH.test(p.source_snapshot_hash||''))throw fail('Der RV-Prüfstand enthält keine eindeutige belegte Entscheidung.');
 const r=a.revocation;
 let effect=null;
 if(r){const d=new Date(r.received_on+'T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+1,1);effect=d.toISOString().slice(0,10);}
 if(p.candidate_effective_from!==effect||p.can_bind_payroll&&(!a.sole_continuous_commercial_minijob_confirmed||!a.no_old_age_or_other_exclusion_confirmed||!a.established_exemption.established_status_confirmed||a.target_month>a.reviewed_as_of.slice(0,7)||effect&&a.target_month+'-01'>=effect&&(r.authority_status!=='non_objection_verified'||p.status!=='compulsory_after_revocation')))throw fail('Die RV-Wirkung ist nicht durch genau diesen Antrag und Prüfstand belegt.');
 return p;
}

export async function payrollRvPreview(v,b){
 const s=snapshot(v?.source_snapshot,b.details.assessment,b.employee_id),p=checkPlan(v.plan,s);
 if(v.employee_id!==b.employee_id||v.kind!=='rv_lifecycle_assessment'||!same(s.details,b.details)||v.can_confirm!==true||v.can_determine!==p.can_determine||v.source_hash!==await hash(s)||p.source_snapshot_hash!==v.source_hash||v.preview_hash!==await hash({source_snapshot:s,plan:p})||p.source_hash!==await hash({assessment:s.details.assessment,original_profile:s.original_profile,source_files:s.source_files,prior_assessments:s.prior_assessments.map(p=>p.assessment)}))throw fail('Die RV-Vorschau wurde von ihren ursprünglichen Angaben oder Nachweisen getrennt.');
 if(!same([...b.source_file_ids].sort(),s.source_files.map(f=>f.id).sort()))throw fail('Die ausgewählten Personaloriginale wurden ersetzt.');
 return v;
}

export function payrollRvRecord(v,employeeId){
 payrollFactRef(v);shape(v.details,'assessment prior_assessment_refs');const a=payrollRvAssessment(v.details.assessment),s=snapshot(v.sources,a,employeeId);checkPlan(v.plan,s);
 if(v.employee_id!==employeeId||v.kind!=='rv_lifecycle_assessment'||v.rule_version!==RV_RULE||v.source_contract_version!==1||v.status!=='active'||v.effective_from!==a.employment_from||v.effective_to!==a.employment_to||!HASH.test(v.source_hash||'')||!HASH.test(v.preview_hash||'')||v.plan.source_snapshot_hash!==v.source_hash||(v.revision===1?v.previous_hash!==null:!HASH.test(v.previous_hash||'')))throw fail('Diese RV-Fassung gehört nicht zum ursprünglichen Beschäftigungsverlauf.');
 return v;
}
export async function payrollRvRecordHashes(v,employeeId){
 payrollRvRecord(v,employeeId);
 await payrollRvPreview({employee_id:employeeId,kind:v.kind,source_snapshot:v.sources,source_hash:v.source_hash,
  plan:v.plan,preview_hash:v.preview_hash,can_confirm:true,can_determine:v.plan.can_determine},
  {employee_id:employeeId,details:v.details,source_file_ids:v.source_file_ids});
 return v;
}

export function payrollRvSources(s,employeeId){
 if(s?.employee_id!==employeeId||s.employee?.id!==employeeId||s.episode_id!==employeeId||!Number.isSafeInteger(s.employee.revision)||s.employee.revision<1||['files','file_references','profiles','history','prior_assessment_refs'].some(k=>!Array.isArray(s[k]))||['can_write','can_approve','writes_enabled'].some(k=>typeof s[k]!=='boolean'))throw fail('Die privaten RV-Quellen gehören nicht eindeutig zur gewählten Person.');
 if(!same(refs(s.history.map(payrollFactRef)),refs(s.prior_assessment_refs))||!same(refs(s.file_references),refs(s.files.map(f=>({id:f.id,revision:1,content_hash:f.content_hash})))))throw fail('Die vollständigen Originalfassungen fehlen.');
 for(const p of s.profiles)if(p.employee_id!==employeeId||p.kind!=='profile')throw fail('Ein Lohnprofil gehört zu einer anderen Person.');else payrollFactRef(p);
 for(const f of s.files)if(f.employee_id!==employeeId||f.purpose!=='personnel')throw fail('Ein privates Original gehört zu einer anderen Person.');
 for(const v of s.history)payrollRvRecord(v,employeeId);
 return s;
}

export function payrollRvInput(s,values,previous=null){
 payrollRvSources(s,s.employee_id);const employee=s.employee;
 const original=(selection,items=s.file_references,versioned=false)=>{const found=items.find(v=>(versioned?payrollRvSelection(v):v.id)===selection);if(!found)throw fail('Die ausgewählte Originalfassung wurde geändert oder fehlt. Quellen neu laden und ausdrücklich prüfen.',409);return payrollFactRef(found);};
 const old=previous?.details.assessment;
 const exemption=old?copy(old.established_exemption):{effective_from:payrollFactDate(values.exempt_from),profile_ref:original(values.original_profile_id,s.profiles,true),evidence_ref:original(values.exemption_file_id),established_status_confirmed:false};
 exemption.established_status_confirmed=values.established_status_confirmed===true;
 let revocation=null;
 if(!['none','received'].includes(values.request_state))throw fail('Den tatsächlichen Antragseingang ausdrücklich auswählen.');
 if(values.request_state==='received')revocation={received_on:payrollFactDate(values.received_on),request_format:values.request_format,request_ref:original(values.request_file_id),notification_received_on:payrollFactDate(values.notification_received_on,true),notification_ref:values.notification_file_id?original(values.notification_file_id):null,authority_status:values.authority_status,objection_deadline_on:payrollFactDate(values.objection_deadline_on,true),deadline_ref:values.deadline_file_id?original(values.deadline_file_id):null,deadline_review_confirmed:values.deadline_review_confirmed===true,authority_status_on:payrollFactDate(values.authority_status_on,true),authority_evidence_ref:values.authority_file_id?original(values.authority_file_id):null,review_note:note(values.procedure_note)};
 const assessment=payrollRvAssessment({schema_version:1,employee_id:employee.id,episode_id:employee.id,employment_from:employee.employment_from,employment_to:employee.employment_to||null,target_month:payrollFactMonth(values.target_month),reviewed_as_of:payrollFactDate(values.reviewed_as_of),sole_continuous_commercial_minijob_confirmed:values.sole_continuous_commercial_minijob_confirmed===true,no_old_age_or_other_exclusion_confirmed:values.no_old_age_or_other_exclusion_confirmed===true,established_exemption:exemption,revocation,review_note:note(values.review_note)});
 const ids=[...new Set([exemption.evidence_ref,...revocation?['request_ref','notification_ref','deadline_ref','authority_evidence_ref'].map(k=>revocation[k]).filter(Boolean):[]].map(r=>r.id))].sort();
 return {employee_id:employee.id,employee_revision:employee.revision,kind:'rv_lifecycle_assessment',rule_version:RV_RULE,source_contract_version:1,revision:previous?.revision||0,status:'active',details:{assessment,prior_assessment_refs:copy(s.prior_assessment_refs)},source_file_ids:ids,confirmed:true,...previous?{id:previous.id,correction_reason:note(values.correction_reason)}:{}};
}
export const payrollRvPreviewInput=b=>Object.fromEntries(['employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids'].map(k=>[k,copy(b[k])]));
export function payrollRvValidator(body,preview,previous=null){const b=copy(body),p=copy(preview),old=previous?copy(previous):null;return async v=>{
 payrollRvRecord(v,b.employee_id);
 if(v.revision!==b.revision+1||(old&&v.id!==old.id)||v.previous_hash!==(old?.content_hash||null)||!same(v.details,b.details)||!same(v.source_file_ids,b.source_file_ids)||!same(v.sources,p.source_snapshot)||!same(v.plan,p.plan)||v.preview_hash!==p.preview_hash||v.preview_hash!==b.preview_hash||v.source_hash!==p.source_hash||v.correction_reason!==(b.correction_reason||''))throw fail('Die RV-Annahme passt nicht zum unveränderten geprüften Auftrag.');
 await payrollRvPreview({...p,source_snapshot:v.sources,plan:v.plan},b);return v;
};}

export function payrollRvRights(c){const read=c?.features?.includes('payroll_rv_lifecycle')===true&&c.capabilities?.includes('business_payroll_rv_lifecycle')===true&&c.permissions?.includes('personnel.read')===true;return{read,approve:read&&c.readonly===false&&c.permissions.includes('personnel.approve'),enabled:read&&c.readonly===false&&c.organization?.modules?.personnel?.enabled!==false};}
export async function payrollRvAuthorize(api,id,{write=false,replay=false}={}){
 const c=await api.get('/business/capabilities'),rights=payrollRvRights(c);
 if(!rights.read||write&&!rights.approve)throw fail('Die aktuellen privaten Personalrechte fehlen.',403);
 const sources=payrollRvSources(await api.get(RV_PATH+'/sources?employee_id='+id),id);
 for(const v of sources.history)await payrollRvRecordHashes(v,id);
 if(write&&!sources.can_approve)throw fail('Die aktuelle Mitarbeiterfreigabe fehlt.',403);
 if(write&&!replay&&(!rights.enabled||!sources.writes_enabled))throw fail('Der Personalbereich ist für neue RV-Nachweise pausiert.',423);
 return{rights,sources};
}
export async function payrollRvPendingAuthorize(api,operation){const match=/^payroll-rv-lifecycle-([a-f0-9]{32})$/.exec(operation?.key||'');if(!match||operation.path!==RV_PATH)return false;const b=api.pendingCommandValues(operation.key,operation.path);if(!b||b.employee_id!==match[1]||b.kind!=='rv_lifecycle_assessment'||b.rule_version!==RV_RULE||b.source_contract_version!==1)throw fail('Die offene RV-Anfrage gehört nicht unverändert zu dieser Person.',409);payrollRvAssessment(b.details?.assessment);await payrollRvAuthorize(api,match[1],{write:true,replay:true});return true;}

export function payrollRvProfileBinding(s,values){
 payrollRvSources(s,s.employee_id);
 const latest=s.history.at(-1);
 if(!latest){if(values.rv_lifecycle_id)throw fail('Die ausgewählte RV-Originalfassung fehlt.',409);return{};}
 if(values.rv_lifecycle_id!==payrollRvSelection(latest))throw fail('Der RV-Nachweis wurde geändert oder noch nicht ausdrücklich gewählt. Quellen neu laden und die genaue Fassung prüfen.',409);
 return{rv_lifecycle_source_contract_version:1,rv_lifecycle_ref:payrollFactRef(latest)};
}

export function payrollRvUi(h){
 const {api,el,button,field,form,dialog,panel,notice,table}=h;
 let employee=null,active=null,epoch=0;
 const available=()=>payrollRvRights(h.caps()).read;
 const action=fn=>h.action(fn,active);
 const pending=e=>api.pendingCommandValues(key(e.id),RV_PATH);
 async function fresh(e,write=false,replay=false){try{const stamp=h.stamp(),current=epoch,result=await payrollRvAuthorize(api,e.id,{write,replay});if(stamp!==h.stamp()||current!==epoch||employee?.id!==e.id||!available())throw fail('Die private RV-Ansicht wurde geschlossen oder geändert.',403);return result;}catch(error){if([401,403,404].includes(error.status)){epoch++;employee=null;active?.replaceChildren(notice('Die aktuelle private Personalfreigabe fehlt. Die angezeigten RV-Daten wurden geschlossen.','error'));}throw error;}}
 function show(e,title,content){if(employee?.id!==e.id||!available())throw fail('Die private RV-Ansicht wurde geschlossen.',403);active=content;content.setAttribute('data-payroll',e.id);content.setAttribute('data-rv-lifecycle','');dialog(title,content);}
 function summary(v){const a=v.details.assessment,p=v.plan;return el('div',{class:'stack'},notice(RV_STATUS[p.status],p.can_bind_payroll?'info':'warn'),table(['Prüfangabe','Belegter Stand'],[['Abrechnungsmonat',a.target_month],['Tatsächlich geprüft bis',a.reviewed_as_of],['Bereits bestehende Befreiung ab',a.established_exemption.effective_from],['Antrag beim Arbeitgeber eingegangen',a.revocation?.received_on||'Kein Antrag belegt'],['Möglicher Wirkungsbeginn',p.candidate_effective_from||'Kein Aufhebungsantrag'],['Verfahrensstand',a.revocation?{not_notified:'Meldung noch nicht belegt',pending:'Widerspruchsverfahren noch offen',non_objection_verified:'Nichtwiderspruch nach geprüfter Frist belegt',objected:'Widerspruch belegt'}[a.revocation.authority_status]:'Bestehende Befreiung'],['Prüfvermerk',a.review_note]]),notice('Diese Prüfung versendet keine Meldung und erzeugt weder ein Lohnprofil noch eine Zahlung. Den belegten RV-Status anschließend ausdrücklich im Lohnprofil auswählen.'));
 }
 async function inspect(e,v,historical=false){await fresh(e);payrollRvRecord(v,e.id);const actions=[];
  if(!historical)actions.push(button('Vollständige RV-Historie öffnen',()=>action(async()=>{const stamp=epoch;await fresh(e);const page=await api.get(RV_PATH+'/'+v.id+'/history');await fresh(e);if(stamp!==epoch)return;if(!Array.isArray(page.items)||page.items.some((item,i)=>payrollRvRecord(item,e.id).id!==v.id||item.revision!==i+1||item.previous_hash!==(i?page.items[i-1].content_hash:null)))throw fail('Die ursprüngliche RV-Historie ist unvollständig.');show(e,'RV-Nachweishistorie',el('div',{class:'stack'},...page.items.map(item=>panel('Fassung '+item.revision,summary(item)))));}), 'small'));
  if(!historical)actions.push(button('Prüfstand mit Originalen fortschreiben',()=>action(()=>edit(e,v)),'small'));
  show(e,'RV-Nachweis · '+e.name,el('div',{class:'stack'},notice('Unveränderte Fassung '+v.revision),summary(v),...v.sources.source_files.map(f=>h.onOriginal?button('Geschütztes Original: '+f.filename,()=>action(async()=>{await fresh(e);return h.onOriginal(e,f);}), 'small'):notice(f.filename)),...actions));
 }
 async function edit(e,previous=null){const access=await fresh(e,true);if(pending(e))return open(e);const s=access.sources,a=previous?.details.assessment||{},r=a.revocation||{},x=a.established_exemption||{};
  const fileOptions=[['','Original ausdrücklich wählen'],...s.files.map(f=>[f.id,f.filename])];
  const select=(name,label,value,options=fileOptions,required=false)=>field(name,label,'select',value||'',{options,required});
  const date=(name,label,value,required=false)=>field(name,label,'date',value||'',{required});
  const check=(name,label,value=false)=>field(name,label,'checkbox',value===true);
  const fields=[field('target_month','Tatsächlicher Abrechnungsmonat (JJJJ-MM)','text',a.target_month||'',{required:true}),date('reviewed_as_of','Tatsächlicher Prüfstand bis',a.reviewed_as_of,true),check('sole_continuous_commercial_minijob_confirmed','Einziger durchgehender gewerblicher Minijob nach 2012 geprüft',a.sole_continuous_commercial_minijob_confirmed),check('no_old_age_or_other_exclusion_confirmed','Keine Altersrenten- oder sonstigen Ausschlussfälle geprüft',a.no_old_age_or_other_exclusion_confirmed),...previous?[]:[date('exempt_from','Bereits bestehende Befreiung ab',x.effective_from,true),select('original_profile_id','Ursprüngliches befreites Minijobprofil','',[['','Profil ausdrücklich wählen'],...s.profiles.filter(p=>p.profile.employment_kind==='minijob'&&p.profile.minijob_rv_exempt).map(p=>[payrollRvSelection(p),p.profile.effective_from+' · Fassung '+p.revision])],true),select('exemption_file_id','Original zur bereits bestehenden Befreiung','',fileOptions,true)],check('established_status_confirmed','Bereits bestehende Befreiung anhand der Originale bestätigt',x.established_status_confirmed),select('request_state','Aufhebungsantrag tatsächlich eingegangen',previous?(a.revocation?'received':'none'):'',[['','Bitte ausdrücklich wählen'],['none','Kein Aufhebungsantrag belegt'],['received','Tatsächlicher Antrag belegt']],true),date('received_on','Antrag beim Arbeitgeber eingegangen am',r.received_on),select('request_format','Tatsächliche Antragsform',r.request_format,[['','Bitte wählen'],['written','Schriftlich'],['electronic','Elektronisch']]),select('request_file_id','Original des eingegangenen Antrags',r.request_ref?.id),date('notification_received_on','Meldung bei der Minijob-Zentrale eingegangen am',r.notification_received_on),select('notification_file_id','Original zum Eingang der Meldung',r.notification_ref?.id),select('authority_status','Tatsächlicher Widerspruchsstand',r.authority_status,[['','Bitte wählen'],['not_notified','Meldung noch nicht belegt'],['pending','Verfahren offen'],['non_objection_verified','Nichtwiderspruch nach Fristprüfung belegt'],['objected','Widerspruch belegt']]),date('objection_deadline_on','Tatsächlich geprüfte Widerspruchsfrist bis',r.objection_deadline_on),select('deadline_file_id','Original der tatsächlichen Fristprüfung',r.deadline_ref?.id),check('deadline_review_confirmed','Anwendbare Frist einschließlich Feiertagen fachlich geprüft',r.deadline_review_confirmed),date('authority_status_on','Belegter Abschluss-/Widerspruchsstand vom',r.authority_status_on),select('authority_file_id','Original zum tatsächlichen Verfahrensstand',r.authority_evidence_ref?.id),field('procedure_note','Prüfvermerk zum tatsächlichen Verfahren','textarea',r.review_note||''),field('review_note','Prüfvermerk zum vollständigen RV-Verlauf','textarea',a.review_note||'',{required:true}),...previous?[field('correction_reason','Grund der Fortschreibung','textarea','',{required:true})]:[]];
  const opened=epoch;show(e,'Minijob-RV anhand der Originale prüfen',form('',fields,async values=>{const current=await fresh(e,true);if(opened!==epoch)throw fail('Der private RV-Entwurf wurde geschlossen.',403);const b=payrollRvInput(s,values,previous),p=await payrollRvPreview(await api.post(RV_PATH+'/preview',payrollRvPreviewInput(b)),b);await fresh(e,true);if(opened!==epoch)return;show(e,'RV-Prüfstand bestätigen',el('div',{class:'stack'},summary({details:b.details,plan:p.plan}),form('',[field('confirmed','Genau diesen Prüfstand und seine Originale ausdrücklich bestätigen','checkbox',false,{required:true})],async value=>{if(value.confirmed!==true)throw fail('Den Prüfstand ausdrücklich bestätigen.');await fresh(e,true);const body={...b,preview_hash:p.preview_hash};const result=await api.mutate(key(e.id),RV_PATH,body,{validate:payrollRvValidator(body,p,previous)});await fresh(e);return inspect(e,result);},{key:'rv-confirm-'+e.id,submit:'Geprüften RV-Verlauf festhalten'})));},{key:'rv-preview-'+e.id,submit:'RV-Wirkung unverbindlich prüfen'}));
 }
 async function open(e){employee=e;const access=await fresh(e),s=access.sources,last=s.history.at(-1);const content=el('div',{class:'stack'},notice('Belegte bestehende RV-Befreiung und ein tatsächlicher Aufhebungsantrag im einzigen durchgehenden gewerblichen Minijob. Weitere Beschäftigungs- und Rentenfälle benötigen ihre eigene Prüfung.'));
  if(pending(e))content.append(notice('Die ursprüngliche Speicherantwort ist offen. Zuerst denselben Auftrag klären.','warn'),button('Ursprüngliche RV-Anfrage unverändert prüfen',()=>action(async()=>{await fresh(e,true,true);return inspect(e,await api.retry(key(e.id)));}),'primary'));
  else if(last)content.append(summary(last),button('Aktuellen RV-Nachweis öffnen',()=>action(()=>inspect(e,last)),'small'));
  if(!pending(e)&&access.rights.approve&&s.can_approve&&s.writes_enabled)content.append(button(last?'Prüfstand mit Originalen fortschreiben':'RV-Verlauf anhand der Originale aufnehmen',()=>action(()=>edit(e,last||null)),'primary'));
  show(e,'Minijob-RV · '+e.name,content);
 }
 return{available,open,clear(){epoch++;employee=active=null;}};
}
