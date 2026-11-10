import {payrollFactRef,payrollFactDates,payrollFactDate} from './payroll-facts.js';
import {factorClaimsPeriodSelectable} from './payroll-factor-claims.js';

export const PAYROLL_FACTOR_TRANSITION_RULE='de_2026_factor_transition_month_v14';
export const PAYROLL_FACTOR_TRANSITION_FEATURE='payroll_factor_transition';
export const PAYROLL_FACTOR_TRANSITION_SCOPE='regular_transition_factor_month';
const order=v=>Array.isArray(v)?v.map(order):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,order(v[k])])):v;
const same=(a,b)=>JSON.stringify(order(a))===JSON.stringify(order(b));
const copy=v=>structuredClone(v),bad=message=>Object.assign(new Error(message),{status:400});
const hash=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(order(v))))),b=>b.toString(16).padStart(2,'0')).join('');
const omit=(v,keys)=>Object.fromEntries(Object.entries(v).filter(([k])=>!keys.includes(k)));
const note=(v,max=3000)=>{if(typeof v!=='string'||!v.trim()||v.length>max||/[\x00-\x1f\x7f]/.test(v))throw bad('Die tatsächliche Prognose und Prüfung vollständig dokumentieren.');return v.trim();};
const amount=v=>{if(!Number.isSafeInteger(v)||v<60301||v>200000)throw bad('Belegten festen Monatslohn von603,01 bis2000Euro angeben.');return v;};

export function factorTransitionAssessment(v,id){
 const fields=['schema_version','employee_id','valid_from','valid_to','declaration_date','transition_assessment','forecast_evidence_ref','sole_employment_confirmed','full_fixed_monthly_pay_confirmed','verification_note'];
 if(!v||!same(Object.keys(v).sort(),fields.sort())||v.schema_version!==1||v.employee_id!==id||typeof v.sole_employment_confirmed!=='boolean'||typeof v.full_fixed_monthly_pay_confirmed!=='boolean')throw bad('Die personengebundene vollständige Prognoseentscheidung fehlt.');
 for(const key of ['valid_from','valid_to','declaration_date'])payrollFactDate(v[key]);
 if(v.valid_from>v.valid_to)throw bad('Der Prognosezeitraum ist umgekehrt.');
 const ref=payrollFactRef(v.forecast_evidence_ref);if(ref.revision!==1)throw bad('Das unveränderte Prognoseoriginal binden.');
 const f=v.transition_assessment,keys=['status','assessed_on','regular_monthly_gross_minor','forecast_months','foreseeable_one_off_payments','note'];
 if(!f||!same(Object.keys(f).sort(),keys.sort())||f.status!=='within_transition_area'||f.forecast_months!==12||typeof f.foreseeable_one_off_payments!=='boolean')throw bad('Die tatsächliche Zwölfmonatsprognose ausdrücklich angeben.');
 amount(f.regular_monthly_gross_minor);payrollFactDate(f.assessed_on);note(f.note,2000);note(v.verification_note);
 return v;
}

export function factorTransitionPlan(v){
 if(v.rule_version!==PAYROLL_FACTOR_TRANSITION_RULE||v.source_contract_version!==6||!/^0\.[0-9]{3}$/.test(v.factor_parameters?.tax_factor||''))throw bad('Bekannter Faktor-Midijob-Plan erforderlich.');
 payrollFactRef(v.factor_parameters.profile_ref);const review=factorTransitionAssessment(v.factor_transition_assessment,v.employee_id);
 if(!v.can_calculate)return v;
 const days=payrollFactDates(v.month),component=v.factor_transition_component;
 for(const key of ['employment_intervals','tax_periods','social_periods'])if(v[key]?.length!==1||v[key][0].start!==days[0]||v[key][0].end!==days.at(-1)||v[key][0].gross_minor!==undefined&&v[key][0].gross_minor!==v.gross_minor)throw bad('Genau einen vollständigen unveränderten Monatsfall verwenden.');
 if(v.tax_periods[0].lzz!==2||v.tax_periods[0].tax_days!==30||v.social_periods[0].days!==30||v.social_periods[0].full_month!==true||v.entitlement_sources.length||v.unpaid_dates.length||v.travel_source_hashes.length||v.flat_travel_tax!==null||Object.entries(v.travel).some(([k,n])=>n!==(k==='letter_m'?false:0))||!review.sole_employment_confirmed||!review.full_fixed_monthly_pay_confirmed||review.transition_assessment.foreseeable_one_off_payments||review.valid_from>days[0]||review.valid_to<days.at(-1)||review.transition_assessment.assessed_on>days[0]||component?.scope!==PAYROLL_FACTOR_TRANSITION_SCOPE||component.payroll_calculation_complete!==true||component.gross_minor!==v.gross_minor||component.tax_parameters.tax_factor!==v.factor_parameters.tax_factor||!same(component.factor_transition_components?.assessment,review.transition_assessment))throw bad('Die vollständige Faktor-/Prognoseentscheidung und der Monatslohn widersprechen sich.');
 amount(v.gross_minor);return v;
}

export function factorTransitionBindings(s,d,p){
 const original=s.period_case?.sources;
 if(!original||s.period_case.plan.rule_version!=='de_2026_standard_factor_period_v9'||!same(s.profiles,original.profiles)||!same(s.identities,original.identities)||!same(s.employment_terms,[original.employment_terms])||s.profiles.length!==1||s.identities.length!==1||d.segment_events.length||d.entitlement_case_refs.length||d.travel_settlement_refs.length||d.thirty_day_rule!==null||d.flat_tax_decision!==null||s.travel_sources.length||s.entitlements.length||!same(d.factor_transition_assessment,s.factor_transition_assessment)||!same(d.factor_transition_assessment,p.factor_transition_assessment)||!same(p.factor_parameters.profile_ref,d.profile_refs[0])||p.factor_parameters.tax_factor!==s.profiles[0].profile.tax_factor)throw bad('Die tatsächlichen Faktor-, Personen- und Prognoseoriginale wurden ersetzt.');
 const r=factorTransitionAssessment(d.factor_transition_assessment,s.employee_id),file=s.source_files.find(f=>f.id===r.forecast_evidence_ref.id);
 if(!file||file.purpose!=='personnel'||file.employee_id!==s.employee_id||file.content_hash!==r.forecast_evidence_ref.content_hash)throw bad('Das tatsächliche eigene Prognoseoriginal fehlt.');
 factorTransitionPlan(p);
}

export async function verifyFactorTransitionCase(v){
 const s=v.sources||v.source_snapshot,p=v.plan;
 factorTransitionPlan(p);
 if(await hash(s)!==v.source_hash||p.source_snapshot_hash!==v.source_hash||await hash(omit(p,['plan_hash','can_confirm','can_calculate']))!==p.plan_hash||await hash({source_snapshot:s,plan:p})!==v.preview_hash)throw bad('Faktor-Midijob-Plan und ursprüngliche Quellen sind nicht unverändert gebunden.');
 if(p.can_calculate){
  const actual=s.profiles[0].profile,c=p.factor_transition_component.factor_transition_components;
  const projection={...omit(actual,['tax_factor']),special_cases:actual.special_cases.filter(x=>x!=='tax_factor'),transition_assessment:s.factor_transition_assessment.transition_assessment};
  if(c.actual_profile_sha256!==await hash(actual)||!same(c.contribution_profile,projection)||c.contribution_profile_sha256!==await hash(projection)||!same(c.assessment,s.factor_transition_assessment.transition_assessment)||actual.regular_annual_gross_minor!==c.assessment.regular_monthly_gross_minor*12||p.gross_minor!==c.assessment.regular_monthly_gross_minor)throw bad('Die ausdrücklich bezeichnete Beitragsprojektion hat die ursprünglichen Merkmale ersetzt.');
 }
 return v;
}

export function factorTransitionCalculation(v){
 if(v.rule_version!==PAYROLL_FACTOR_TRANSITION_RULE||v.source_contract_version!==6)throw bad('Bekannter Faktor-Midijob-Regelstand erforderlich.');
 if(v.scope==='unsupported')return v;
 const c=v.factor_transition_components,t=c?.factor_tax;
 if(v.scope!==PAYROLL_FACTOR_TRANSITION_SCOPE||v.travel_expenses_included_in_net!==false||v.net_deductions_minor!==0||!c||!t||t.factor!==v.tax_parameters?.tax_factor||!same(c.assessment,v.period_details.factor_transition_assessment.transition_assessment)||v.transition?.factor!=='0.6619'||!same(c.contribution_financials.transition,v.transition))throw bad('Faktorsteuer und belegte Übergangsbereichsbeiträge passen nicht zusammen.');
 for(const key of ['employee_contributions','employer_contributions','employee_social_total_minor','employer_social_total_minor','employer_levies','employer_flat_tax_minor','employer_total_excluding_accident_insurance_minor'])if(!same(c.contribution_financials[key],v[key]))throw bad('Die unveränderte Beitragskomponente wurde ersetzt.');
 if(t.totals.LSTLZZ!==v.individual_wage_tax_minor||t.totals.SOLZLZZ!==v.solidarity_minor||t.totals.BK!==v.tax_parameters.church_assessment_minor)throw bad('Die ursprüngliche Faktorsteuer wurde ersetzt.');
 return v;
}

export async function verifyFactorTransitionRun(v){
 const fact=v.source?.calculation_case;await verifyFactorTransitionCase(fact);
 if(await hash({source:v.source,calculation:v.calculation})!==v.preview_hash||v.calculation.scope!=='unsupported'&&!same(omit(v.calculation,['period_details']),fact.plan.factor_transition_component))throw bad('Der Lohnlauf entspricht nicht der unveränderten vollständigen Faktor-Midijob-Vorschau.');
 return v;
}

export function factorTransitionInput(id,s,v,previous=null){
 const month=v.month,days=payrollFactDates(month),base=s.factor_period_facts?.find(row=>row.id===v.period_case_id);
 if(!base||!factorClaimsPeriodSelectable(base,month)||previous&&(previous.rule_version!==PAYROLL_FACTOR_TRANSITION_RULE||previous.source_contract_version!==6||previous.details.month!==month))throw bad('Einen ursprünglichen vollständigen Faktor-Monat auswählen; die alte Regel bleibt erhalten.');
 if(v.segment_events?.length||v.entitlement_case_ids?.length||v.travel_settlement_ids?.length||v.travel_payment_ids?.length||v.policy_id||v.thirty_day_rule)throw bad('Zusätzliche Vorgänge dürfen nicht aus dem neuen Monatsfall entfernt werden.');
 const refs=(items,ids,kind)=>{if(!Array.isArray(ids)||ids.length!==1)throw bad('Genau eine ursprüngliche Fassung auswählen.');const row=items.find(r=>r.id===ids[0]&&r.status!=='void'&&(!kind||r.kind===kind));if(!row)throw bad('Eine ausgewählte ursprüngliche Quelle fehlt.');return[payrollFactRef(row)];};
 const terms=refs(s.facts,v.employment_terms_ids,'employment_terms'),profiles=refs(s.profiles,v.profile_ids),identities=refs(s.identities,v.identity_ids);
 if(!same(terms,base.details.employment_terms_ref?[base.details.employment_terms_ref]:[payrollFactRef(base.sources.employment_terms)])||!same(profiles,base.details.profile_refs)||!same(identities,base.details.identity_refs))throw bad('Die tatsächlichen ursprünglichen Monatsfassungen unverändert auswählen.');
 if(s.entitlements.some(r=>r.status==='active'&&r.effective_from<=days.at(-1)&&r.effective_to>=days[0])||s.travel_settlements.some(r=>r.status==='approved'&&r.details.period_from<=days.at(-1)&&r.details.period_to>=days[0]))throw bad('Weitere Ansprüche und Reisen benötigen ihren eigenen Faktor-Midijob-Vertrag.');
 const review=copy(factorTransitionAssessment(v.factor_transition_assessment,id)),files=v.source_file_ids;review.verification_note=note(review.verification_note);review.transition_assessment.note=note(review.transition_assessment.note,2000);
 if(!Array.isArray(files)||!files.length||files.length>20||new Set(files).size!==files.length||files.some(id=>!s.files.some(r=>r.id===id))||!files.includes(review.forecast_evidence_ref.id)||!s.files.some(r=>r.id===review.forecast_evidence_ref.id&&r.content_hash===review.forecast_evidence_ref.content_hash))throw bad('Das eigene tatsächliche Prognoseoriginal ausdrücklich binden.');
 return{employee_id:id,employee_revision:s.employee.revision,kind:'calculation_case',rule_version:PAYROLL_FACTOR_TRANSITION_RULE,source_contract_version:6,details:{month,period_case_ref:payrollFactRef(base),employment_terms_refs:terms,profile_refs:profiles,identity_refs:identities,segment_events:[],thirty_day_rule:null,entitlement_case_refs:[],travel_settlement_refs:[],flat_tax_decision:null,factor_transition_assessment:review,verification_note:note(v.verification_note)},source_file_ids:[...files].sort(),revision:previous?.revision||0,status:'active',confirmed:true,...previous?{id:previous.id,correction_reason:note(v.correction_reason)}:{}};
}
