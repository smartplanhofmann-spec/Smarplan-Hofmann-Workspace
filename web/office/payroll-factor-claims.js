import {payrollFactRef,payrollFactDates,payrollFactRecord} from './payroll-facts.js';

export const PAYROLL_FACTOR_CLAIMS_RULE='de_2026_factor_claims_month_v12';
export const PAYROLL_FACTOR_CLAIMS_FEATURE='payroll_factor_claims';
export const PAYROLL_FACTOR_CLAIMS_SCOPE='regular_standard_factor_claims_month';
export const FACTOR_CLAIMS_CARE_METHOD='ROUND_BASE_AND_ADJUSTMENTS_SEPARATELY_GKV_2025_03_31_SECTION_3_3';
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const fail=message=>Object.assign(new Error(message),{status:400});
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(value))))),b=>b.toString(16).padStart(2,'0')).join('');
const omit=(value,keys)=>Object.fromEntries(Object.entries(value).filter(([key])=>!keys.includes(key)));
const note=v=>{if(typeof v!=='string'||!v.trim()||v.trim().length>3000||/[\x00-\x1f\x7f]/.test(v))throw fail('Die belegte Prüfung vollständig dokumentieren.');return v.trim();};

export function factorClaimsPeriodSelectable(value,month){
 const p=value?.plan,days=payrollFactDates(month);
 return value?.status==='active'&&value.kind==='period_case'&&p?.rule_version==='de_2026_standard_factor_period_v9'&&value.details?.month===month&&p.tax_periods?.length===1&&p.social_periods?.length===1&&p.employment_intervals?.length===1&&p.tax_periods[0].lzz===2&&p.tax_periods[0].tax_days===30&&p.social_periods[0].days===30&&p.social_periods[0].full_month===true&&[p.employment_intervals[0],p.tax_periods[0],p.social_periods[0]].every(period=>period.start===days[0]&&period.end===days.at(-1));
}
export function factorClaimsPlan(value){
 if(value.rule_version!==PAYROLL_FACTOR_CLAIMS_RULE||value.source_contract_version!==4||value.care_contribution_method!==FACTOR_CLAIMS_CARE_METHOD||!/^0\.[0-9]{3}$/.test(value.factor_parameters?.tax_factor||''))throw fail('Faktor und verbindliche Beitragsmethode fehlen im Anspruchsplan.');
 payrollFactRef(value.factor_parameters.profile_ref);
 if(value.can_calculate){
  const days=payrollFactDates(value.month),tax=value.tax_periods,social=value.social_periods;
  if(value.employment_intervals.length!==1||tax.length!==1||social.length!==1||tax[0].lzz!==2||tax[0].tax_days!==30||social[0].days!==30||social[0].full_month!==true||[value.employment_intervals[0],tax[0],social[0]].some(p=>p.start!==days[0]||p.end!==days.at(-1)||p.gross_minor!==undefined&&p.gross_minor!==value.gross_minor)||!value.entitlement_sources.length||value.travel_source_hashes.length||value.flat_travel_tax!==null||Object.entries(value.travel).some(([k,v])=>v!==(k==='letter_m'?false:0)))throw fail('Dieser Anspruchsfall benötigt einen vollständigen Faktor-Monat ohne zusätzliche Reiserechnung.');
 }
 return value;
}
export function factorClaimsBindings(s,d,p){
 const original=s.period_case?.sources;
 if(s.rule_version!==PAYROLL_FACTOR_CLAIMS_RULE||s.source_contract_version!==4||s.period_case?.plan?.rule_version!=='de_2026_standard_factor_period_v9'||!original||d.segment_events.length||d.thirty_day_rule!==null||d.flat_tax_decision!==null||d.travel_settlement_refs.length||Object.hasOwn(d,'travel_payment_refs')||s.travel_sources.length||s.flat_travel_tax!==null||!d.entitlement_case_refs.length||['employment_terms_refs','profile_refs','identity_refs'].some(k=>d[k].length!==1)||!same(s.profiles,original.profiles)||!same(s.identities,original.identities)||!same(s.employment_terms,[original.employment_terms])||!same(p.factor_parameters?.profile_ref,d.profile_refs[0])||p.factor_parameters?.tax_factor!==s.profiles[0]?.profile?.tax_factor)throw fail('Die ursprünglichen Faktor-, Beschäftigungs- und Anspruchsnachweise wurden ersetzt oder erweitert.');
 factorClaimsPlan(p);
}
export async function verifyFactorClaimsCase(value){
 const s=value.sources||value.source_snapshot,p=value.plan;
 factorClaimsPlan(p);
 if(await hash(s)!==value.source_hash||p.source_snapshot_hash!==value.source_hash||await hash(omit(p,['plan_hash','can_confirm','can_calculate']))!==p.plan_hash||await hash({source_snapshot:s,plan:p})!==value.preview_hash)throw fail('Die Anspruchsvorschau bindet andere Originale oder einen veränderten Gesamtplan.');
 return value;
}
export async function verifyFactorClaimsRun(value){
 const fact=value.source?.calculation_case;
 await verifyFactorClaimsCase(fact);
 if(await hash({source:value.source,calculation:value.calculation})!==value.preview_hash)throw fail('Die Lohnvorschau wurde gegenüber den ursprünglichen Anspruchsquellen verändert.');
 return value;
}
export function factorClaimsInput(id,s,v,previous=null){
 if(previous&&(previous.rule_version!==PAYROLL_FACTOR_CLAIMS_RULE||previous.source_contract_version!==4))throw fail('Die ursprüngliche Abrechnungsregel bleibt bei einer Korrektur erhalten.');
 if(!Array.isArray(s.factor_period_facts)||!s.factor_period_facts.some(p=>p.id===v.period_case_id&&factorClaimsPeriodSelectable(p,v.month))||['employment_terms_ids','profile_ids','identity_ids'].some(k=>v[k]?.length!==1)||v.segment_events?.length||v.thirty_day_rule||v.policy_id||v.travel_settlement_ids?.length||v.travel_payment_ids?.length)throw fail('Einen vollständigen ursprünglichen Faktor-Monat mit seinen Anspruchsquellen auswählen.');
 const refs=(items,ids,kind=null)=>{if(!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length)throw fail('Alle einschlägigen Originalquellen ausdrücklich auswählen.');return [...ids].sort().map(id=>{const item=items.find(v=>v.id===id&&v.status!=='void'&&(!kind||v.kind===kind));if(!item)throw fail('Eine Originalquelle ist nicht mehr aktuell.');return payrollFactRef(item);});};
 const days=payrollFactDates(v.month),required=s.entitlements.filter(e=>e.status==='active'&&e.effective_from<=days.at(-1)&&e.effective_to>=days[0]).map(e=>e.id).sort();
 if(!required.length||!same(required,[...(v.entitlement_case_ids||[])].sort()))throw fail('Sämtliche aktiven Anspruchsnachweise des Monats vollständig auswählen.');
 const files=v.source_file_ids;
 if(!Array.isArray(files)||!files.length||files.length>20||new Set(files).size!==files.length||files.some(id=>!s.files.some(f=>f.id===id)))throw fail('Ein bis zwanzig geschützte Personaloriginale auswählen.');
 const base=s.factor_period_facts.find(p=>p.id===v.period_case_id);payrollFactRecord(base,id,'period_case');
 return {employee_id:id,employee_revision:s.employee.revision,kind:'calculation_case',rule_version:PAYROLL_FACTOR_CLAIMS_RULE,source_contract_version:4,details:{month:v.month,period_case_ref:payrollFactRef(base),employment_terms_refs:refs(s.facts,v.employment_terms_ids,'employment_terms'),profile_refs:refs(s.profiles,v.profile_ids),identity_refs:refs(s.identities,v.identity_ids),segment_events:[],thirty_day_rule:null,entitlement_case_refs:refs(s.entitlements,required),travel_settlement_refs:[],flat_tax_decision:null,verification_note:note(v.verification_note)},source_file_ids:[...files].sort(),revision:previous?.revision||0,status:'active',confirmed:true,...previous?{id:previous.id,correction_reason:note(v.correction_reason)}:{}};
}
