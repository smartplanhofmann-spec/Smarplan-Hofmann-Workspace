import {adjustmentReview,adjustmentTransition,verifyAdjustmentTransition,verifyAdjustmentPreview,verifyAdjustmentPaymentRecord} from './payroll-adjustment.js';
import {positiveCorrectionHash,source5Calculation,source5UnchangedSubject,positiveCorrectionReview,positiveCorrectionTransition,verifyPositiveCorrectionTransition,verifyPositiveCorrectionPreview,verifyPositiveCorrectionPaymentRecord} from './payroll-positive-correction.js';

export const REPAYMENT_FEATURE='payroll_source5_net_repayments';
export const REPAYMENT_REVIEW='source5_actual_net_repayment_review_v1';
export const REPAYMENT_TRANSITION='source5_net_repayment_v1';
export const REPAYMENT_PAYMENT='source5_actual_net_repayment_v4';
const ID=/^[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/;
const ordered=value=>Array.isArray(value)?value.map(ordered):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,ordered(value[k])])):value;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const clone=value=>JSON.parse(JSON.stringify(value));
function need(ok,message='Der tatsächliche Netto-Rückzahlungsfall ist nicht eindeutig an seine Originale gebunden.') {if(!ok){const e=new Error(message);e.status=409;throw e;}}
function keys(value,names){need(value&&typeof value==='object'&&!Array.isArray(value)&&same(Object.keys(value).sort(),names.split(' ').sort()));}
function integer(n,min=0){need(Number.isSafeInteger(n)&&n>=min&&n<=1e12);return n;}
function reference(value){keys(value,'id revision content_hash');need(ID.test(value.id)&&HASH.test(value.content_hash));integer(value.revision,1);return value;}
const ref=value=>reference({id:value.id,revision:value.revision,content_hash:value.content_hash});
const omit=(v,k)=>Object.fromEntries(Object.entries(v).filter(([name])=>name!==k));
const TRANSITION_KEYS='schema_version contract employee_id month previous_run_ref prior_run_ref prior_payment_ref prior_plan_hash old_composition_hash new_composition_hash component_key event_key receipt_date running_net_minor prior_total_net_minor total_net_minor net_delta_minor repayment_minor remittance_observation settlement_review transition_hash';
const PLAN_KEYS='schema_version contract employee_id month composition_hash event_key bonus_receipt_date running_net_minor one_off_net_minor total_net_minor payments allocations prior_settlement_refs preserved_prior_payment_indexes new_payment_indexes actual_payment_created cash_import_created claim_consumption_created prior_total_net_minor net_delta_minor repayment_minor prior_plan_hash transition_hash settlement_date_basis plan_hash';
const OLD_CONTRACTS={1:'source5_single_other_payment_settlement_v1',2:'source5_positive_net_correction_v2',3:'source5_positive_net_correction_v3'};

export function repaymentReview(value){
  keys(value,'schema_version contract payments_complete remittances_complete evidence_ref');
  need(value.schema_version===2&&value.contract===REPAYMENT_REVIEW&&value.payments_complete===true&&value.remittances_complete===true);
  need(reference(value.evidence_ref).revision===1);
  return value;
}

export function repaymentTransition(value,run,{previous=null}={}){
  keys(value,TRANSITION_KEYS);
  const {c,event,running,net}=source5Calculation(run);
  need(value.schema_version===2&&value.contract===REPAYMENT_TRANSITION&&value.employee_id===run.source.employee_id&&value.month===run.source.month);
  for(const k of ['previous_run_ref','prior_run_ref','prior_payment_ref'])reference(value[k]);
  need(value.prior_payment_ref.revision===1&&value.previous_run_ref.id===value.prior_run_ref.id&&value.prior_run_ref.revision<=value.previous_run_ref.revision);
  if(run.kind==='run')need(run.id===value.previous_run_ref.id&&run.revision===value.previous_run_ref.revision+1);
  repaymentReview(value.settlement_review);need(same(run.source.input.settlement_review,value.settlement_review));
  for(const k of ['prior_plan_hash','old_composition_hash','new_composition_hash','transition_hash'])need(HASH.test(value[k]));
  need(value.component_key===event.component_key&&value.event_key===event.event_key&&value.receipt_date===event.receipt_date);
  need(integer(value.running_net_minor)===running&&integer(value.total_net_minor)===net&&integer(value.prior_total_net_minor)>net&&net>=running);
  need(integer(value.net_delta_minor,-1e12)<0&&value.net_delta_minor===net-value.prior_total_net_minor&&integer(value.repayment_minor,1)===-value.net_delta_minor);
  const o=value.remittance_observation;keys(o,'schema_version head_sequence entries amounts source_hash');
  need(o.schema_version===1&&HASH.test(o.source_hash)&&Array.isArray(o.entries));integer(o.head_sequence);
  keys(o.amounts,'employee_tax employee_social employer_social employer_levies employer_flat_tax');
  let sequence=0;const ids=new Set();
  for(const entry of o.entries){keys(entry,'id revision sequence private_hash');need(ID.test(entry.id)&&entry.revision===1&&HASH.test(entry.private_hash)&&!ids.has(entry.id));integer(entry.sequence,1);need(entry.sequence>sequence&&entry.sequence<=o.head_sequence);sequence=entry.sequence;ids.add(entry.id);}
  const ceilings={employee_tax:c.employee_tax_minor,employee_social:c.employee_social_total_minor,employer_social:c.employer_social_total_minor,employer_flat_tax:c.employer_flat_tax_minor,employer_levies:Object.values(c.employer_levies).reduce((n,v)=>n+integer(v),0)};
  for(const [key,ceiling]of Object.entries(ceilings))need(integer(o.amounts[key])<=integer(ceiling));
  if(!o.entries.length)need(Object.values(o.amounts).every(n=>n===0));
  if(previous){need(same(ref(previous),value.previous_run_ref));source5UnchangedSubject(previous,run);if(same(ref(previous),value.prior_run_ref))need(source5Calculation(previous).net===value.prior_total_net_minor);}
  return value;
}

export async function verifyRepaymentTransition(value,run,options={}){
  repaymentTransition(value,run,options);
  need(await positiveCorrectionHash(omit(value,'transition_hash'))===value.transition_hash);
  need(await positiveCorrectionHash(omit(value.remittance_observation,'source_hash'))===value.remittance_observation.source_hash);
  need(await positiveCorrectionHash(run.calculation)===value.new_composition_hash);
  if(options.previous&&same(ref(options.previous),value.prior_run_ref))need(await positiveCorrectionHash(options.previous.calculation)===value.old_composition_hash);
  if(run.kind==='run')need(await positiveCorrectionHash({source:run.source,calculation:run.calculation,settlement_transition:value})===run.preview_hash);
  return value;
}

export async function verifyRepaymentPreview(value,input,options={}){
  await verifyRepaymentTransition(value.settlement_transition,value,options);
  need(same(value.source.input,input)&&await positiveCorrectionHash({source:value.source,calculation:value.calculation,settlement_transition:value.settlement_transition})===value.preview_hash);
  return value;
}

function layout(details,run,{prior=null,archived=null}={}){
  const t=repaymentTransition(run.settlement_transition,run),{event,running,net}=source5Calculation(run),parts=details.payments,allocations=details.settlement_allocations;
  need(run.kind==='run'&&run.confirmed===true&&run.status==='calculation_recorded'&&run.accepted_scope===run.calculation.scope);
  need(details.payment_source_schema_version===4&&details.run_id===run.id&&details.run_revision===run.revision&&same(details.prior_payment_ref,t.prior_payment_ref));
  const count=prior?prior.details.payments.length:archived?.preserved_prior_payment_indexes?.length;integer(count,1);
  need(Array.isArray(parts)&&parts.length>count&&parts.length<=20&&Array.isArray(allocations)&&allocations.length===parts.length);
  if(prior){
    const old=prior.sources.single_payment_plan;need(prior.kind==='payment'&&prior.confirmed===true&&prior.employee_id===run.employee_id&&same(ref(prior),t.prior_payment_ref)&&same(ref(prior.sources.run),t.prior_run_ref));
    need(Number.isSafeInteger(old.schema_version)&&OLD_CONTRACTS[old.schema_version]===old.contract&&old.plan_hash===t.prior_plan_hash);
    source5UnchangedSubject(prior.sources.run,run);
    need(same(parts.slice(0,count),prior.details.payments)&&same(allocations.slice(0,count),prior.details.settlement_allocations));
  }
  const notBefore=[event.receipt_date,...parts.slice(0,count).map(p=>p.paid_on)].sort().at(-1),seen=new Set();let repaid=0,runningSum=0,bonusSum=0;
  for(const [index,p]of parts.entries()){
    keys(p,'paid_on amount_minor payment_reference');integer(p.amount_minor,-1e12);need(p.amount_minor!==0);
    const date=p.paid_on,text=p.payment_reference;
    need(typeof date==='string'&&/^2026-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.test(date)&&new Date(date+'T00:00:00Z').toISOString().slice(0,10)===date&&date.slice(0,7)>=run.source.month);
    need(typeof text==='string'&&text.trim()===text&&text.length>0&&text.length<=200&&!/[\x00-\x1f\x7f\uD800-\uDFFF]/u.test(text));
    const key=date+'|'+text.normalize('NFKC').toLocaleLowerCase('und');need(!seen.has(key));seen.add(key);
    const a=allocations[index];keys(a,'payment_index running_minor one_off_allocations');need(a.payment_index===index&&Array.isArray(a.one_off_allocations)&&a.one_off_allocations.length<=1);integer(a.running_minor);
    let bonus=0;for(const one of a.one_off_allocations){keys(one,'event_key net_minor');bonus=integer(one.net_minor,-1e12);need(bonus!==0&&one.event_key===event.event_key&&date>=event.receipt_date);}
    need(a.running_minor+bonus===p.amount_minor);runningSum+=a.running_minor;bonusSum+=bonus;
    if(index>=count){need(p.amount_minor<0&&a.running_minor===0&&a.one_off_allocations.length===1&&date>=notBefore);repaid-=p.amount_minor;}
    else need(p.amount_minor>0);
  }
  need(repaid===t.repayment_minor&&runningSum===running&&bonusSum===net-running&&parts.reduce((n,p)=>n+p.amount_minor,0)===net&&parts.slice(0,count).reduce((n,p)=>n+p.amount_minor,0)===t.prior_total_net_minor);
  return {schema_version:4,contract:REPAYMENT_PAYMENT,employee_id:run.source.employee_id,month:run.source.month,event_key:event.event_key,bonus_receipt_date:event.receipt_date,running_net_minor:running,one_off_net_minor:net-running,total_net_minor:net,payments:clone(parts),allocations:clone(allocations),prior_settlement_refs:{run:clone(t.prior_run_ref),payment:clone(t.prior_payment_ref)},preserved_prior_payment_indexes:Array.from({length:count},(_,i)=>i),new_payment_indexes:Array.from({length:parts.length-count},(_,i)=>i+count),actual_payment_created:false,cash_import_created:false,claim_consumption_created:false,prior_total_net_minor:t.prior_total_net_minor,net_delta_minor:t.net_delta_minor,repayment_minor:repaid,prior_plan_hash:t.prior_plan_hash,transition_hash:t.transition_hash,settlement_date_basis:'actual_employee_repayment_2026'};
}

export function repaymentPaymentDetails(details,run,prior){need(prior);layout(details,run,{prior});return details;}
export function repaymentPaymentRecord(value){
  const run=value?.sources?.run,plan=value?.sources?.single_payment_plan;
  need(value.kind==='payment'&&value.confirmed===true&&value.employee_id===run?.employee_id);keys(plan,PLAN_KEYS);need(HASH.test(plan.composition_hash)&&HASH.test(plan.plan_hash));
  need(same(omit(omit(plan,'composition_hash'),'plan_hash'),layout(value.details,run,{archived:plan})));
  return value;
}
export async function repaymentPaymentPlan(details,run,prior){
  await verifyRepaymentTransition(run.settlement_transition,run);
  const old=prior.sources.single_payment_plan;
  if([2,3].includes(old.schema_version))await verifyPositiveCorrectionPaymentRecord(prior);
  need(same(old.payments,prior.details.payments)&&same(old.allocations,prior.details.settlement_allocations));
  need(await positiveCorrectionHash(omit(old,'plan_hash'))===old.plan_hash&&await positiveCorrectionHash(prior.sources.run.calculation)===old.composition_hash&&old.composition_hash===run.settlement_transition.old_composition_hash);
  const plan={...layout(details,run,{prior}),composition_hash:await positiveCorrectionHash(run.calculation)};
  return {...plan,plan_hash:await positiveCorrectionHash(plan)};
}
export async function verifyRepaymentPaymentRecord(value){
  repaymentPaymentRecord(value);await verifyRepaymentTransition(value.sources.run.settlement_transition,value.sources.run);
  const plan=value.sources.single_payment_plan;need(await positiveCorrectionHash(value.sources.run.calculation)===plan.composition_hash&&await positiveCorrectionHash(omit(plan,'plan_hash'))===plan.plan_hash);return value;
}

export const source5SettlementReview=value=>value?.schema_version===3?adjustmentReview(value):value?.schema_version===2?repaymentReview(value):positiveCorrectionReview(value);
export const source5SettlementTransition=(value,run,options={})=>value?.schema_version===3?adjustmentTransition(value,run,options):value?.schema_version===2?repaymentTransition(value,run,options):positiveCorrectionTransition(value,run,options);
export const verifySource5SettlementTransition=(value,run,options={})=>value?.schema_version===3?verifyAdjustmentTransition(value,run,options):value?.schema_version===2?verifyRepaymentTransition(value,run,options):verifyPositiveCorrectionTransition(value,run,options);
export const verifySource5SettlementPreview=(value,input,options={})=>value?.settlement_transition?.schema_version===3?verifyAdjustmentPreview(value,input,options):value?.settlement_transition?.schema_version===2?verifyRepaymentPreview(value,input,options):verifyPositiveCorrectionPreview(value,input,options);
export const verifySource5PaymentRecord=value=>value?.details?.payment_source_schema_version===5?verifyAdjustmentPaymentRecord(value):value?.details?.payment_source_schema_version===4?verifyRepaymentPaymentRecord(value):verifyPositiveCorrectionPaymentRecord(value);
