import {PAYROLL_MULTIPLE_RULE,payrollMultipleSource} from './payroll-multiple-cases.js';

export const POSITIVE_CORRECTION_FEATURE='payroll_source5_positive_corrections';
export const POSITIVE_CORRECTION_CONTRACT='source5_positive_net_correction_v1';
export const POSITIVE_PAYMENT_CONTRACT='source5_positive_net_correction_v2';
export const POSITIVE_PAYMENT_DATES_FEATURE='payroll_source5_payment_dates';
export const POSITIVE_PAYMENT_DATES_CONTRACT='source5_positive_net_correction_v3';

const ID=/^[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/;
const clone=value=>JSON.parse(JSON.stringify(value));
const ordered=value=>Array.isArray(value)?value.map(ordered):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,ordered(value[key])])):value;
const same=(left,right)=>JSON.stringify(ordered(left))===JSON.stringify(ordered(right));
function fail(message){const error=new Error(message);error.status=409;return error;}
function need(value,message='Die belegte positive Lohnkorrektur ist nicht eindeutig gebunden.'){if(!value)throw fail(message);}
function keys(value,names){need(value&&typeof value==='object'&&!Array.isArray(value)&&same(Object.keys(value).sort(),names.split(' ').sort()),'Der ursprüngliche Korrekturvertrag ist unvollständig oder unbekannt.');}
function integer(value,min=0){need(Number.isSafeInteger(value)&&value>=min&&value<=1e12,'Die Korrektur benötigt genaue belegte Centbeträge.');return value;}
function reference(value){keys(value,'id revision content_hash');need(ID.test(value.id)&&HASH.test(value.content_hash));integer(value.revision,1);return value;}
const ref=value=>reference({id:value.id,revision:value.revision,content_hash:value.content_hash});
const total=values=>integer(values.reduce((sum,value)=>sum+integer(value),0));
export const positiveCorrectionHash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(value))))),value=>value.toString(16).padStart(2,'0')).join('');
const without=(value,name)=>Object.fromEntries(Object.entries(value).filter(([key])=>key!==name));

const TRANSITION_KEYS='schema_version contract employee_id month previous_run_ref prior_run_ref prior_payment_ref prior_plan_hash old_composition_hash new_composition_hash component_key event_key receipt_date running_net_minor prior_total_net_minor total_net_minor additional_net_minor remittance_observation settlement_review transition_hash';
const PLAN_KEYS='schema_version contract employee_id month composition_hash event_key bonus_receipt_date running_net_minor one_off_net_minor total_net_minor payments allocations prior_settlement_refs preserved_prior_payment_indexes new_payment_indexes actual_payment_created cash_import_created claim_consumption_created plan_hash';
const POSITIVE_PLAN_KEYS=PLAN_KEYS+' prior_total_net_minor additional_net_minor prior_plan_hash transition_hash';
const planKeys=version=>POSITIVE_PLAN_KEYS+(version===3?' settlement_date_basis':'');
const REMITTANCE_COMPONENTS={employee_tax:'employee_tax_minor',employee_social:'employee_social_total_minor',employer_social:'employer_social_total_minor',employer_flat_tax:'employer_flat_tax_minor'};

export function positiveCorrectionReview(value){
  keys(value,'schema_version payments_complete remittances_complete evidence_ref');
  need(value.schema_version===1&&value.payments_complete===true&&value.remittances_complete===true,'Sämtliche bisherigen Zahlungen und Abführungen müssen ausdrücklich vollständig geprüft sein.');
  reference(value.evidence_ref);need(value.evidence_ref.revision===1,'Der konkrete geschützte Vollständigkeitsnachweis fehlt.');
  return value;
}

function calculation(run){
  need(run?.source?.source_schema_version===5&&run.calculation?.rule_version===PAYROLL_MULTIPLE_RULE);
  payrollMultipleSource({...run,can_finalize:true},run.source.input);
  const c=run.calculation,d=c.multiple_one_off_details;
  need(c.payroll_calculation_complete===true&&d.components.length===1&&d.receipt_events.length===1);
  return {c,d,event:d.receipt_events[0],running:integer(c.running_calculation.net_minor-c.running_calculation.net_deductions_minor),net:integer(c.net_minor-c.net_deductions_minor)};
}

function sameSubject(previous,current){
  const before=calculation(previous),after=calculation(current);
  const oldSource=previous.source.multiple_one_off_case.sources.calculation_source,newSource=current.source.multiple_one_off_case.sources.calculation_source;
  const oldExtra=before.d.single_original_calculation.one_off_details,newExtra=after.d.single_original_calculation.one_off_details;
  need(previous.source.employee_id===current.source.employee_id&&previous.source.month===current.source.month&&same(previous.source.calculation_case,current.source.calculation_case)&&same(before.c.running_calculation,after.c.running_calculation));
  need(same(oldSource.components,newSource.components)&&same(before.d.components,after.d.components)&&same(before.d.receipt_events,after.d.receipt_events),'Die Korrektur darf laufende Originale, Anspruch, Brutto oder Zuflusstag nicht ersetzen.');
  need(['tax_year','social_year','assigned_period_ref','assigned_period_end'].every(key=>same(oldExtra.assignment[key],newExtra.assignment[key]))&&same(oldExtra.assigned_part_key,newExtra.assigned_part_key),'Geänderte Steuer- oder Sozialversicherungszuordnungen benötigen einen eigenen Korrekturweg.');
}

// Shared original-subject checks; neither grants a correction or changes money.
export function source5Calculation(run){return calculation(run);}
export function source5UnchangedSubject(previous,current){sameSubject(previous,current);}

export function positiveCorrectionTransition(value,run,{previous=null}={}){
  keys(value,TRANSITION_KEYS);
  const {c,d,event,running,net}=calculation(run);
  need(value.schema_version===1&&value.contract===POSITIVE_CORRECTION_CONTRACT);
  need(value.employee_id===run.source.employee_id&&value.month===run.source.month);
  for(const key of ['previous_run_ref','prior_run_ref','prior_payment_ref'])reference(value[key]);
  need(value.prior_payment_ref.revision===1,'Revidierte frühere Zahlungsnachweise benötigen ihren eigenen Korrekturweg.');
  positiveCorrectionReview(value.settlement_review);
  need(same(run.source.input.settlement_review,value.settlement_review),'Die Vollständigkeitsbestätigung gehört nicht zu dieser ursprünglichen Korrekturanfrage.');
  for(const key of ['prior_plan_hash','old_composition_hash','new_composition_hash','transition_hash'])need(HASH.test(value[key]));
  need(value.previous_run_ref.id===value.prior_run_ref.id&&value.prior_run_ref.revision<=value.previous_run_ref.revision);
  if(run.id!==undefined)need(value.previous_run_ref.id===run.id&&value.previous_run_ref.revision===run.revision-1);
  need(value.component_key===d.components[0].component_key&&value.event_key===event.event_key&&value.receipt_date===event.receipt_date);
  integer(value.running_net_minor);integer(value.prior_total_net_minor);integer(value.total_net_minor);integer(value.additional_net_minor,1);
  need(value.running_net_minor===running&&value.total_net_minor===net&&value.prior_total_net_minor+value.additional_net_minor===net&&value.prior_total_net_minor>running);
  need(value.old_composition_hash!==value.new_composition_hash);
  const observation=value.remittance_observation;
  keys(observation,'schema_version head_sequence entries amounts source_hash');
  need(observation.schema_version===1&&HASH.test(observation.source_hash)&&Array.isArray(observation.entries));integer(observation.head_sequence);
  keys(observation.amounts,'employee_tax employee_social employer_social employer_levies employer_flat_tax');
  let sequence=0;const ids=new Set();
  for(const item of observation.entries){
    keys(item,'id revision sequence private_hash');need(ID.test(item.id)&&!ids.has(item.id)&&item.revision===1&&HASH.test(item.private_hash));
    integer(item.sequence,1);need(item.sequence>sequence&&item.sequence<=observation.head_sequence);sequence=item.sequence;ids.add(item.id);
  }
  for(const [component,field]of Object.entries(REMITTANCE_COMPONENTS))need(integer(observation.amounts[component])<=integer(c[field]),'Bereits abgeführte Beträge übersteigen die korrigierte Schuld. Dieser Fall benötigt einen anderen Korrekturweg.');
  need(integer(observation.amounts.employer_levies)<=total(Object.values(c.employer_levies)),'Bereits abgeführte Umlagen übersteigen die korrigierte Schuld.');
  if(!observation.entries.length)need(Object.values(observation.amounts).every(amount=>amount===0),'Ohne Abführungsoriginale darf kein abgeführter Betrag angenommen werden.');
  if(previous){
    need(same(ref(previous),value.previous_run_ref));
    need(previous.employee_id===value.employee_id);sameSubject(previous,run);
    if(same(ref(previous),value.prior_run_ref))need(calculation(previous).net===value.prior_total_net_minor,'Die bisher bezahlte Nettoverpflichtung stimmt nicht mit ihrem Original überein.');
  }
  return value;
}

export async function verifyPositiveCorrectionTransition(value,run,options={}){
  positiveCorrectionTransition(value,run,options);
  need(await positiveCorrectionHash(without(value,'transition_hash'))===value.transition_hash,'Die ursprüngliche Korrekturbindung wurde verändert.');
  need(await positiveCorrectionHash(without(value.remittance_observation,'source_hash'))===value.remittance_observation.source_hash,'Die belegte Sicht der bisherigen Abführungen wurde verändert.');
  need(await positiveCorrectionHash(run.calculation)===value.new_composition_hash,'Die Korrektur gehört zu einer anderen Berechnung.');
  if(options.previous&&same(ref(options.previous),value.prior_run_ref))need(await positiveCorrectionHash(options.previous.calculation)===value.old_composition_hash,'Die frühere bezahlte Rechnung stimmt nicht mit ihrem Originalhash überein.');
  if(run.kind==='run')need(HASH.test(run.preview_hash||'')&&await positiveCorrectionHash({source:run.source,calculation:run.calculation,settlement_transition:value})===run.preview_hash,'Der angenommene Korrekturlauf bindet eine andere Vorschau.');
  return value;
}

export async function verifyPositiveCorrectionPreview(value,input,{previous=null}={}){
  need(value?.settlement_transition,'Der bestätigte positive Korrekturübergang fehlt.');
  await verifyPositiveCorrectionTransition(value.settlement_transition,value,{previous});
  need(same(value.source.input,input)&&await positiveCorrectionHash({source:value.source,calculation:value.calculation,settlement_transition:value.settlement_transition})===value.preview_hash,'Die Vorschau bindet nicht genau diese Originalquellen und diesen Korrekturübergang.');
  return value;
}

function paymentParts(details,run){
  const {d,event,running,net}=calculation(run),parts=details.payments,allocations=details.settlement_allocations;
  need(run.kind==='run'&&run.confirmed===true&&run.status==='calculation_recorded'&&run.accepted_scope===run.calculation.scope);
  need([2,3].includes(details.payment_source_schema_version)&&details.run_id===run.id&&details.run_revision===run.revision);
  need(Array.isArray(parts)&&parts.length>=2&&parts.length<=20&&Array.isArray(allocations)&&allocations.length===parts.length);
  const seen=new Set();let runningSum=0,bonusSum=0;
  for(const [i,part]of parts.entries()){
    keys(part,'paid_on amount_minor payment_reference');integer(part.amount_minor,1);
    const date=part.paid_on,text=part.payment_reference;
    need(typeof date==='string'&&/^2026-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.test(date)&&new Date(date+'T00:00:00Z').toISOString().slice(0,10)===date&&date.slice(0,7)>=run.source.month);
    need(typeof text==='string'&&text.trim()===text&&text.length>=1&&text.length<=200&&!/[\x00-\x1f\x7f]/.test(text));
    const key=date+'|'+text.normalize('NFKC').toLocaleLowerCase('und');need(!seen.has(key),'Ein tatsächlicher Zahlungsteil darf nicht doppelt vorkommen.');seen.add(key);
    const allocation=allocations[i];keys(allocation,'payment_index running_minor one_off_allocations');integer(allocation.running_minor);
    need(allocation.payment_index===i&&Array.isArray(allocation.one_off_allocations)&&allocation.one_off_allocations.length<=1);
    let bonus=0;
    for(const oneoff of allocation.one_off_allocations){keys(oneoff,'event_key net_minor');bonus=integer(oneoff.net_minor,1);need(oneoff.event_key===event.event_key&&(details.payment_source_schema_version===3?date>=event.receipt_date:date===event.receipt_date),'Die Nettozahlung muss dasselbe ursprüngliche Bruttoereignis erfüllen.');}
    need(allocation.running_minor+bonus===part.amount_minor);runningSum+=allocation.running_minor;bonusSum+=bonus;
  }
  need(runningSum===running&&bonusSum===net-running&&total(parts.map(part=>part.amount_minor))===net,'Alle belegten Zahlungsteile müssen das korrigierte Netto genau erfüllen.');
  return {d,event,running,net,parts,allocations};
}

function layout(details,run,{prior=null,archivedPlan=null}={}){
  const t=positiveCorrectionTransition(run.settlement_transition,run);
  const {event,running,net,parts,allocations}=paymentParts(details,run);
  need(same(details.prior_payment_ref,t.prior_payment_ref));
  const count=prior?prior.details.payments.length:archivedPlan?.preserved_prior_payment_indexes?.length;
  integer(count,1);need(count<parts.length);
  const version=details.payment_source_schema_version;
  if(prior){
    need(prior.kind==='payment'&&prior.confirmed===true&&prior.employee_id===run.employee_id&&same(ref(prior),t.prior_payment_ref));
    const old=prior.sources?.run,oldPlan=prior.sources?.single_payment_plan,before=calculation(old);
    need(same(ref(old),t.prior_run_ref)&&old.employee_id===run.employee_id);sameSubject(old,run);
    need(before.net===t.prior_total_net_minor&&oldPlan?.plan_hash===t.prior_plan_hash);
    need(version===3||oldPlan.schema_version!==3,'Ein später datierter Zahlungspräfix benötigt weiterhin Zahlungsfassung 3.');
    need(same(parts.slice(0,count),prior.details.payments)&&same(allocations.slice(0,count),prior.details.settlement_allocations),'Alle bereits belegten Zahlungen und Zuordnungen müssen unverändert am Anfang stehen.');
  }
  need(total(parts.slice(0,count).map(part=>part.amount_minor))===t.prior_total_net_minor);
  need(total(allocations.slice(0,count).map(part=>part.running_minor))===running);
  const notBefore=[event.receipt_date,...parts.slice(0,count).map(p=>p.paid_on)].sort().at(-1);
  need(parts.slice(count).every((part,index)=>(version===3?part.paid_on>=notBefore:part.paid_on===event.receipt_date)&&allocations[count+index].running_minor===0&&allocations[count+index].one_off_allocations.length===1));
  need(total(parts.slice(count).map(part=>part.amount_minor))===t.additional_net_minor);
  return {schema_version:version,contract:version===3?POSITIVE_PAYMENT_DATES_CONTRACT:POSITIVE_PAYMENT_CONTRACT,employee_id:run.employee_id,month:run.source.month,
    event_key:event.event_key,bonus_receipt_date:event.receipt_date,running_net_minor:running,one_off_net_minor:net-running,total_net_minor:net,
    payments:clone(parts),allocations:clone(allocations),prior_settlement_refs:{run:clone(t.prior_run_ref),payment:clone(t.prior_payment_ref)},
    preserved_prior_payment_indexes:Array.from({length:count},(_,i)=>i),new_payment_indexes:Array.from({length:parts.length-count},(_,i)=>i+count),
    actual_payment_created:false,cash_import_created:false,claim_consumption_created:false,prior_total_net_minor:t.prior_total_net_minor,
    additional_net_minor:t.additional_net_minor,prior_plan_hash:t.prior_plan_hash,transition_hash:t.transition_hash,
    ...(version===3?{settlement_date_basis:'actual_positive_transfer_2026'}:{})};
}

export function positiveCorrectionPaymentDetails(details,run,prior){
  need(prior,'Der tatsächlich belegte frühere Zahlungsnachweis fehlt.');
  layout(details,run,{prior});
  return details;
}

export function positiveCorrectionPaymentRecord(value){
  const run=value?.sources?.run,plan=value?.sources?.single_payment_plan;
  need(value.kind==='payment'&&value.confirmed===true&&value.employee_id===run?.employee_id);
  keys(plan,planKeys(value.details?.payment_source_schema_version));need(HASH.test(plan.composition_hash)&&HASH.test(plan.plan_hash));
  const expected=layout(value.details,run,{archivedPlan:plan});
  need(same(without(without(plan,'composition_hash'),'plan_hash'),expected),'Der ursprüngliche Korrektur-Zahlungsplan wurde verändert.');
  return value;
}

export async function positiveCorrectionPaymentPlan(details,run,prior){
  need(prior?.sources?.single_payment_plan,'Den tatsächlich belegten vorherigen Zahlungsnachweis ausdrücklich auswählen.');
  await verifyPositiveCorrectionTransition(run.settlement_transition,run);
  const oldPlan=prior.sources.single_payment_plan,old=prior.sources.run;
  keys(oldPlan,oldPlan.schema_version===1?PLAN_KEYS:planKeys(oldPlan.schema_version));
  need((oldPlan.schema_version===1&&oldPlan.contract==='source5_single_other_payment_settlement_v1')||(oldPlan.schema_version===2&&oldPlan.contract===POSITIVE_PAYMENT_CONTRACT)||(oldPlan.schema_version===3&&oldPlan.contract===POSITIVE_PAYMENT_DATES_CONTRACT));
  if([2,3].includes(oldPlan.schema_version))await verifyPositiveCorrectionPaymentRecord(prior);
  need(same(oldPlan.payments,prior.details.payments)&&same(oldPlan.allocations,prior.details.settlement_allocations),'Die frühere Zahlung stimmt nicht mit ihren ursprünglichen Nettozuordnungen überein.');
  need(await positiveCorrectionHash(without(oldPlan,'plan_hash'))===oldPlan.plan_hash&&await positiveCorrectionHash(old.calculation)===oldPlan.composition_hash&&oldPlan.composition_hash===run.settlement_transition.old_composition_hash,'Der vorherige tatsächliche Zahlungsplan gehört zu einer anderen Originalrechnung.');
  const plan={...layout(details,run,{prior}),composition_hash:await positiveCorrectionHash(run.calculation)};
  return {...plan,plan_hash:await positiveCorrectionHash(plan)};
}

export async function verifyPositiveCorrectionPaymentRecord(value){
  positiveCorrectionPaymentRecord(value);
  const run=value.sources.run,plan=value.sources.single_payment_plan;
  await verifyPositiveCorrectionTransition(run.settlement_transition,run);
  need(await positiveCorrectionHash(run.calculation)===plan.composition_hash&&await positiveCorrectionHash(without(plan,'plan_hash'))===plan.plan_hash,'Die ursprüngliche Korrektur-Zahlungsbindung wurde verändert.');
  return value;
}
