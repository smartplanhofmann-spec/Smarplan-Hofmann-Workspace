import {payrollFactRef} from './payroll-facts.js';
import {PAYROLL_FACTOR_CLAIMS_RULE,factorClaimsPlan,factorClaimsBindings,factorClaimsInput} from './payroll-factor-claims.js';
import {PAYROLL_FACTOR_TRAVEL_RULE,factorTravelPlan,factorTravelBindings,factorTravelSources} from './payroll-factor-travel.js';

export const PAYROLL_FACTOR_CLAIM_TRAVEL_RULE='de_2026_factor_claims_paid_travel_month_v13';
export const PAYROLL_FACTOR_CLAIM_TRAVEL_FEATURE='payroll_factor_claims_paid_travel';
export const PAYROLL_FACTOR_CLAIM_TRAVEL_SCOPE='regular_standard_factor_claims_paid_travel_month';
const projections={claims:'UNCHANGED_ORIGINALS_WITH_TRAVEL_SOURCES_EMPTY_AND_FLAT_TRAVEL_TAX_NULL',paid_travel:'UNCHANGED_ORIGINALS_WITH_ENTITLEMENTS_EMPTY_FOR_TRAVEL_PROOF_ONLY'};
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const omit=(v,keys)=>Object.fromEntries(Object.entries(v).filter(([k])=>!keys.includes(k)));
const fail=message=>Object.assign(new Error(message),{status:400});
const hash=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(v))))),b=>b.toString(16).padStart(2,'0')).join('');
const HASH=/^[a-f0-9]{64}$/;
const codeOrder=(a,b)=>a.code<b.code?-1:a.code>b.code?1:0;

export function factorClaimTravelProjections(s,d=null){
 const claims={...s,rule_version:PAYROLL_FACTOR_CLAIMS_RULE,source_contract_version:4,travel_sources:[],flat_travel_tax:null};
 const paid_travel={...s,rule_version:PAYROLL_FACTOR_TRAVEL_RULE,source_contract_version:2,entitlements:[]};
 if(!d)return {claims,paid_travel};
 const claimDetails={...d,travel_settlement_refs:[]};delete claimDetails.travel_payment_refs;
 return {claims,paid_travel,claimDetails,travelDetails:{...d,entitlement_case_refs:[]}};
}

export function factorClaimTravelPlan(p){
 if(p?.rule_version!==PAYROLL_FACTOR_CLAIM_TRAVEL_RULE||p.source_contract_version!==5||!HASH.test(p.rules_sha256||'')||!same(Object.keys(p.components||{}).sort(),['claims','paid_travel']))throw fail('Vollständigen eigenen Faktor-/Anspruchs-/Reiseplan verwenden.');
 const c=p.components.claims,t=p.components.paid_travel;
 for(const [name,value,rule,contract] of [['claims',c,PAYROLL_FACTOR_CLAIMS_RULE,4],['paid_travel',t,PAYROLL_FACTOR_TRAVEL_RULE,2]]){
  if(!same(Object.keys(value||{}).sort(),['plan','plan_hash','projection','rule_version','rules_sha256','source_contract_version','source_snapshot_hash'].sort())||value.rule_version!==rule||value.source_contract_version!==contract||value.projection!==projections[name]||!HASH.test(value.source_snapshot_hash||'')||value.rules_sha256!==value.plan?.rules_sha256||value.plan_hash!==value.plan?.plan_hash||value.source_snapshot_hash!==value.plan?.source_snapshot_hash)throw fail('Die unveränderten beiden Projektionsverträge fehlen.');
 }
 factorClaimsPlan(c.plan);factorTravelPlan(t.plan);
 const satisfied=c.plan.can_calculate&&c.plan.gross_minor>0&&t.plan.blockers.some(v=>v.code==='zero_earnings_requires_review')?['zero_earnings_requires_review']:[];
 const blockers=new Map(c.plan.blockers.map(v=>[v.code,v]));
 for(const value of t.plan.blockers)if(!satisfied.includes(value.code)&&!blockers.has(value.code))blockers.set(value.code,value);
 const merged=[...blockers.values()].sort(codeOrder);
 const expected={...omit(c.plan,['plan_hash','can_confirm','can_calculate']),rule_version:PAYROLL_FACTOR_CLAIM_TRAVEL_RULE,source_contract_version:5,rules_sha256:p.rules_sha256,source_snapshot_hash:p.source_snapshot_hash,components:p.components,
  travel:t.plan.travel,travel_source_hashes:t.plan.travel_source_hashes,travel_payment_refs:t.plan.travel_payment_refs,travel_paid_minor:t.plan.travel_paid_minor,
  satisfied_travel_component_wage_reviews:satisfied,blockers:merged,plan_hash:p.plan_hash,can_confirm:true,can_calculate:merged.length===0};
 if(!same(expected,p))throw fail('Der gemeinsame Plan verändert Ansprüche, Reisebeweise oder ihre getrennten Geldbeträge.');
 return p;
}

export function factorClaimTravelBindings(s,d,p){
 if(s.rule_version!==PAYROLL_FACTOR_CLAIM_TRAVEL_RULE||s.source_contract_version!==5||!d.entitlement_case_refs?.length||!d.travel_settlement_refs?.length||!d.travel_payment_refs?.length)throw fail('Beide ursprünglichen Anspruchs- und bezahlten Reisekomponenten vollständig binden.');
 factorClaimTravelPlan(p);
 const x=factorClaimTravelProjections(s,d);
 factorClaimsBindings(x.claims,x.claimDetails,p.components.claims.plan);
 factorTravelBindings(x.paid_travel,x.travelDetails,p.components.paid_travel.plan);
}

export async function verifyFactorClaimTravelCase(v){
 const s=v.sources||v.source_snapshot,p=factorClaimTravelPlan(v.plan),x=factorClaimTravelProjections(s);
 if(await hash(s)!==v.source_hash||p.source_snapshot_hash!==v.source_hash||await hash(omit(p,['plan_hash','can_confirm','can_calculate']))!==p.plan_hash||await hash({source_snapshot:s,plan:p})!==v.preview_hash)throw fail('Die gemeinsame Vorschau bindet andere Originale oder einen anderen Gesamtplan.');
 for(const name of ['claims','paid_travel']){
  const component=p.components[name],plan=component.plan;
  if(await hash(x[name])!==component.source_snapshot_hash||await hash(omit(plan,['plan_hash','can_confirm','can_calculate']))!==component.plan_hash)throw fail('Ein ursprünglicher Komponentenplan oder seine tatsächliche Projektion wurde verändert.');
 }
 if(v.details)factorClaimTravelBindings(s,v.details,p);
 return v;
}

export async function verifyFactorClaimTravelRun(v){
 await verifyFactorClaimTravelCase(v.source?.calculation_case);
 if(await hash({source:v.source,calculation:v.calculation})!==v.preview_hash)throw fail('Die gemeinsame Lohnvorschau wurde gegenüber den belegten Originalen verändert.');
 return v;
}

export function factorClaimTravelCalculation(v){
 const d=v?.period_details,c=d?.components?.claims?.plan;
 if(!c)throw fail('Die unveränderte ursprüngliche Anspruchsrechnung fehlt.');
 factorClaimTravelPlan({...omit(c,['plan_hash','can_confirm','can_calculate']),
  rule_version:PAYROLL_FACTOR_CLAIM_TRAVEL_RULE,source_contract_version:5,rules_sha256:v.rules_sha256,
  source_snapshot_hash:d.source_snapshot_hash,gross_minor:v.gross_minor,components:d.components,
  factor_parameters:d.factor_parameters,care_contribution_method:d.care_contribution_method,
  travel:d.travel,travel_source_hashes:d.travel_source_hashes,travel_payment_refs:d.travel_payment_refs,
  travel_paid_minor:d.travel_paid_minor,satisfied_travel_component_wage_reviews:d.satisfied_travel_component_wage_reviews,
  blockers:v.blockers,plan_hash:d.plan_hash,can_confirm:true,can_calculate:v.payroll_calculation_complete});
 if(v.scope!=='unsupported'&&(v.scope!==PAYROLL_FACTOR_CLAIM_TRAVEL_SCOPE
     || d.factor_parameters.tax_factor!==v.tax_parameters?.tax_factor||v.travel_expenses_included_in_net!==false
     ||v.net_deductions_minor!==0))throw fail('Anspruchslohn und bereits gezahlte Reise dürfen kein doppeltes Netto erzeugen.');
 return v;
}

export function factorClaimTravelInput(id,s,v,previous=null){
 factorTravelSources(s,id);
 const claim=factorClaimsInput(id,s,{...v,travel_settlement_ids:[],travel_payment_ids:[]});
 const selected=(items,ids)=>{
  if(!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length)throw fail('Originalreisen und tatsächliche Zahlungsbelege ausdrücklich auswählen.');
  return [...ids].sort().map(id=>{const value=items.find(row=>row.id===id);if(!value||value.status==='void')throw fail('Eine ausgewählte Originalquelle ist nicht mehr verfügbar.');return value;});
 };
 const settlements=selected(s.travel_settlements,v.travel_settlement_ids),settlementRefs=settlements.map(payrollFactRef);
 const paymentIds=v.travel_payment_ids;
 if(!Array.isArray(paymentIds)||!paymentIds.length||new Set(paymentIds).size!==paymentIds.length)throw fail('Alle tatsächlichen Reisezahlungsfassungen auswählen.');
 // Voided payments remain part of the immutable prefix and must be retained.
 const payments=[...paymentIds].sort().map(id=>{const value=s.travel_payment_proofs.find(row=>row.id===id);if(!value)throw fail('Ein ursprünglicher Zahlungsbeleg fehlt.');return value;});
 const refs=rows=>rows.map(payrollFactRef).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
 if(payments.some(row=>!settlementRefs.some(ref=>same(ref,row.settlement_ref)))||!same(refs(payments),refs(s.travel_payment_proofs.filter(row=>settlementRefs.some(ref=>same(ref,row.settlement_ref))))))throw fail('Der vollständige Zahlungspräfix muss genau zu den ausgewählten Originalreisen gehören.');
 const data={...claim,rule_version:PAYROLL_FACTOR_CLAIM_TRAVEL_RULE,source_contract_version:5,
  details:{...claim.details,travel_settlement_refs:settlementRefs,travel_payment_refs:refs(payments)}};
 if(previous){
  if(previous.employee_id!==id||previous.kind!=='calculation_case'||previous.status!=='active'||previous.details.month!==v.month)throw fail('Die ursprüngliche Mitarbeiter-/Monatsidentität bleibt erhalten.');
  if(previous.rule_version!==PAYROLL_FACTOR_CLAIM_TRAVEL_RULE){
   if(![PAYROLL_FACTOR_CLAIMS_RULE,PAYROLL_FACTOR_TRAVEL_RULE].includes(previous.rule_version)||v.confirm_unused_upgrade!==true)throw fail('Nur den fehlenden Bestandteil eines unbenutzten ursprünglichen Faktorfalls ausdrücklich ergänzen.');
   const base=s.factor_period_facts.find(row=>row.id===v.period_case_id);
   if(!same(previous.sources.period_case,base)||previous.source_file_ids.some(id=>!data.source_file_ids.includes(id)))throw fail('Die bereits geprüfte Faktorgrundlage und Originalunterlagen müssen erhalten bleiben.');
   if(previous.rule_version===PAYROLL_FACTOR_CLAIMS_RULE&&!same(previous.details.entitlement_case_refs,data.details.entitlement_case_refs))throw fail('Die bereits geprüften Anspruchsoriginale unverändert erhalten.');
   if(previous.rule_version===PAYROLL_FACTOR_TRAVEL_RULE&&(!same(previous.details.travel_settlement_refs,data.details.travel_settlement_refs)||!same(previous.details.travel_payment_refs,data.details.travel_payment_refs)))throw fail('Die bereits geprüften Reiseoriginale und Zahlungsfassungen unverändert erhalten.');
  }else if(previous.source_contract_version!==5)throw fail('Der ursprüngliche gemeinsame Quellenvertrag fehlt.');
  if(typeof v.correction_reason!=='string'||!v.correction_reason.trim()||v.correction_reason.trim().length>3000||/[\x00-\x1f\x7f]/.test(v.correction_reason))throw fail('Die ausdrückliche Ergänzung oder Korrektur begründen.');
  Object.assign(data,{id:previous.id,revision:previous.revision,correction_reason:v.correction_reason.trim()});
 }
 return data;
}
