import {payrollFactRef, payrollFactDates, payrollFactDate} from './payroll-facts.js';

export const PAYROLL_FACTOR_TRANSITION_PERIOD_RULE = 'de_2026_factor_transition_period_v16';
export const PAYROLL_FACTOR_TRANSITION_PERIOD_FEATURE = 'payroll_factor_transition_periods';
export const PAYROLL_FACTOR_TRANSITION_PERIOD_SCOPE = 'regular_transition_factor_period';
const bad = message => Object.assign(new Error(message), {status:400});
const compare = (a,b) => {const x=Array.from(a,c=>c.codePointAt(0)),y=Array.from(b,c=>c.codePointAt(0));for(let i=0;i<Math.min(x.length,y.length);i++)if(x[i]!==y[i])return x[i]-y[i];return x.length-y.length;};
const ordered = v => Array.isArray(v) ? v.map(ordered) : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v).sort(compare).map(k=>[k,ordered(v[k])])) : v;
const same = (a,b) => JSON.stringify(ordered(a)) === JSON.stringify(ordered(b));
const copy = v => structuredClone(v);
const omit = (v,names) => Object.fromEntries(Object.entries(v).filter(([k])=>!names.includes(k)));
const hash = async v => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(v))))),b=>b.toString(16).padStart(2,'0')).join('');
const integer = (v,min=0,max=1e12) => {if(!Number.isSafeInteger(v)||v<min||v>max)throw bad('Eindeutige vollständige Cent- und Tageswerte erforderlich.');return v;};
const shape = (v,names) => {if(!v||typeof v!=='object'||Array.isArray(v)||!same(Object.keys(v).sort(),names.split(' ').sort()))throw bad('Die ursprüngliche Teilmonatsstruktur ist unbekannt oder unvollständig.');};
const note = (v,max=3000) => {
 if(typeof v!=='string'||!v.trim()||Array.from(v).length>max||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v))throw bad('Die tatsächliche Teilmonatsprüfung vollständig dokumentieren.');
 for(let i=0;i<v.length;i++){const c=v.charCodeAt(i);if(c>=0xd800&&c<=0xdbff){const next=v.charCodeAt(++i);if(!(next>=0xdc00&&next<=0xdfff))throw bad('Prüftext enthält ungültige Unicode-Zeichen.');}else if(c>=0xdc00&&c<=0xdfff)throw bad('Prüftext enthält ungültige Unicode-Zeichen.');}
 return v.trim();
};
const hashValue = v => {if(typeof v!=='string'||!(/^[a-f0-9]{64}$/).test(v))throw bad('Der unveränderte ursprüngliche Teilmonatsnachweis fehlt.');return v;};

export function factorTransitionPeriodAssessment(v,id){
 shape(v,'schema_version employee_id valid_from valid_to declaration_date transition_assessment forecast_evidence_ref sole_employment_confirmed fixed_monthly_contract_confirmed contractual_30_days_confirmed verification_note');
 if(v.schema_version!==1||v.employee_id!==id)throw bad('Die Teilmonatsprüfung gehört nicht zur ursprünglichen Person.');
 for(const key of ['sole_employment_confirmed','fixed_monthly_contract_confirmed','contractual_30_days_confirmed'])if(typeof v[key]!=='boolean')throw bad('Beschäftigung, Monatsvertrag und Teilentgeltmethode ausdrücklich prüfen.');
 for(const key of ['valid_from','valid_to','declaration_date'])payrollFactDate(v[key]);
 if(v.valid_from>v.valid_to||payrollFactRef(v.forecast_evidence_ref).revision!==1)throw bad('Gültige ursprüngliche Prognose und ihren Zeitraum binden.');
 const f=v.transition_assessment;
 shape(f,'status assessed_on regular_monthly_gross_minor forecast_months foreseeable_one_off_payments note');
 if(f.status!=='within_transition_area'||f.forecast_months!==12||typeof f.foreseeable_one_off_payments!=='boolean')throw bad('Vollständige tatsächliche Zwölfmonatsprognose erforderlich.');
 integer(f.regular_monthly_gross_minor,60301,200000);payrollFactDate(f.assessed_on);note(f.note,2000);note(v.verification_note);
 return v;
}

export function factorTransitionPeriodSelectable(v,month){
 const p=v?.plan,original=v?.sources,t=p?.tax_periods,s=p?.social_periods,e=p?.employment_intervals;
 return v?.kind==='period_case'&&v.status==='active'&&v.details?.month===month&&p?.rule_version==='de_2026_standard_factor_period_v9'
  &&original?.employment_terms?.details?.proration_method==='contractual_30_days'
  &&Array.isArray(t)&&t.length===1&&t[0].lzz===4&&Number.isInteger(t[0].tax_days)&&t[0].tax_days>=1&&t[0].tax_days<=30
  &&Array.isArray(s)&&s.length===1&&s[0].full_month===false&&Number.isInteger(s[0].days)&&s[0].days>=1&&s[0].days<=30
  &&Array.isArray(e)&&e.length===1&&t[0].start===e[0].start&&t[0].end===e[0].end&&s[0].start===e[0].start&&s[0].end===e[0].end
  &&Array.isArray(p.blockers)&&p.blockers.every(r=>r.code==='transition_assessment_missing');
}

export function factorTransitionPeriodPlan(v){
 if(v?.schema_version!==1||v.rule_version!==PAYROLL_FACTOR_TRANSITION_PERIOD_RULE||v.source_contract_version!==7||!/^0\.[0-9]{3}$/.test(v.factor_parameters?.tax_factor||''))throw bad('Bekannter eigener Faktor-/Midijob-Teilmonatsplan erforderlich.');
 payrollFactRef(v.factor_parameters.profile_ref);const r=factorTransitionPeriodAssessment(v.factor_transition_period_assessment,v.employee_id);
 for(const key of ['plan_hash','rules_sha256','source_snapshot_hash'])hashValue(v[key]);
 if(!Array.isArray(v.blockers)||typeof v.can_calculate!=='boolean'||v.can_confirm!==true||v.can_calculate!==(v.blockers.length===0))throw bad('Der tatsächliche Berechnungsstatus des Teilmonats ist widersprüchlich.');
 if(!v.can_calculate){if(v.factor_transition_period_component!==null)throw bad('Ein gesperrter Teilmonat darf keine vollständige Geldkomponente enthalten.');return v;}
 const days=payrollFactDates(v.month);
 for(const key of ['employment_intervals','tax_periods','social_periods','earnings','identity_intervals'])if(!Array.isArray(v[key])||v[key].length!==1)throw bad('Genau einen ursprünglichen Beschäftigungs- und Entgeltabschnitt verwenden.');
 const e=v.employment_intervals[0],t=v.tax_periods[0],s=v.social_periods[0],w=v.earnings[0];
 if(e.start<days[0]||e.end>days.at(-1)||e.start>e.end||t.start!==e.start||t.end!==e.end||s.start!==e.start||s.end!==e.end||t.lzz!==4||s.full_month!==false)throw bad('Die tatsächliche Teilmonatszeitachse ist widersprüchlich.');
 integer(t.tax_days,1,30);integer(s.days,1,30);
 if(w.kind!=='ordinary_work'||w.pay_basis!=='monthly'||w.proration_method!=='contractual_30_days'||w.thirty_day_rule!=='actual_days_capped_per_claim'||w.numerator!==s.days||w.denominator!==30||w.gross_minor!==v.gross_minor||s.gross_minor!==v.gross_minor||t.gross_minor!==v.gross_minor||!same(s.transition_ratio,{numerator:s.days,denominator:30})||v.gross_minor!==Math.floor((r.transition_assessment.regular_monthly_gross_minor*s.days+15)/30))throw bad('Die tatsächliche 30-Tage-Vertragsquote wurde verändert.');
 if(!r.sole_employment_confirmed||!r.fixed_monthly_contract_confirmed||!r.contractual_30_days_confirmed||r.transition_assessment.foreseeable_one_off_payments||r.valid_from>e.start||r.valid_to<e.end||r.transition_assessment.assessed_on>e.start||r.declaration_date<r.transition_assessment.assessed_on||v.entitlement_sources.length||v.unpaid_dates.length||v.travel_source_hashes.length||v.flat_travel_tax!==null||Object.entries(v.travel).some(([k,n])=>n!==(k==='letter_m'?false:0)))throw bad('Die vollständig geprüfte einfache Teilmonatsentscheidung fehlt.');
 const component=v.factor_transition_period_component;
 if(!component||component.rules_sha256!==v.rules_sha256||component.gross_minor!==v.gross_minor)throw bad('Die ursprüngliche vollständige Teilmonatskomponente fehlt.');
 factorTransitionPeriodCalculation({...component,period_details:v});
 return v;
}

function sourceBindings(s,p){
 shape(s,'schema_version source_contract_version rule_version employee_id month period_case employment_terms profiles identities segment_events thirty_day_rule entitlements travel_sources flat_travel_tax source_files factor_transition_period_assessment');
 if(s.schema_version!==1||s.source_contract_version!==7||s.rule_version!==PAYROLL_FACTOR_TRANSITION_PERIOD_RULE||s.employee_id!==p.employee_id||s.month!==p.month||s.thirty_day_rule!=='actual_days_capped_per_claim')throw bad('Die ursprünglichen Teilmonatsquellen wurden umgedeutet.');
 const base=s.period_case,original=base?.sources;
 if(!original||base.plan.rule_version!=='de_2026_standard_factor_period_v9'||!same(s.profiles,original.profiles)||!same(s.identities,original.identities)||!same(s.employment_terms,[original.employment_terms])||s.profiles.length!==1||s.identities.length!==1||s.segment_events.length||s.entitlements.length||s.travel_sources.length||s.flat_travel_tax!==null||!same(s.factor_transition_period_assessment,p.factor_transition_period_assessment)||!same(p.factor_parameters.profile_ref,payrollFactRef(s.profiles[0]))||p.factor_parameters.tax_factor!==s.profiles[0].profile.tax_factor)throw bad('Eine ursprüngliche Person, Profilfassung oder Teilmonatsquelle wurde ersetzt.');
 const review=factorTransitionPeriodAssessment(s.factor_transition_period_assessment,s.employee_id),file=s.source_files.find(f=>f.id===review.forecast_evidence_ref.id);
 if(!file||file.purpose!=='personnel'||file.employee_id!==s.employee_id||file.content_hash!==review.forecast_evidence_ref.content_hash||s.profiles[0].profile.regular_annual_gross_minor!==review.transition_assessment.regular_monthly_gross_minor*12)throw bad('Das tatsächliche private Prognoseoriginal wurde nicht unverändert gebunden.');
 if(p.can_calculate&&(!factorTransitionPeriodSelectable(base,p.month)||p.gross_minor!==base.plan.gross_minor))throw bad('Der angenommene Teilmonat widerspricht seinem ursprünglichen Periodenfall.');
}

export function factorTransitionPeriodBindings(s,d,p){
 factorTransitionPeriodPlan(p);sourceBindings(s,p);
 if(d.month!==s.month||!same(d.period_case_ref,payrollFactRef(s.period_case))||!same(d.employment_terms_refs,s.employment_terms.map(payrollFactRef))||!same(d.profile_refs,s.profiles.map(payrollFactRef))||!same(d.identity_refs,s.identities.map(payrollFactRef))||d.segment_events.length||d.entitlement_case_refs.length||d.travel_settlement_refs.length||d.flat_tax_decision!==null||d.thirty_day_rule!=='actual_days_capped_per_claim'||!same(d.factor_transition_period_assessment,s.factor_transition_period_assessment))throw bad('Die ursprüngliche ausdrückliche Teilmonatsauswahl wurde verändert.');
}

export async function verifyFactorTransitionPeriodCase(v){
 const s=v.sources||v.source_snapshot,p=v.plan;
 factorTransitionPeriodPlan(p);sourceBindings(s,p);
 if(await hash(s)!==v.source_hash||p.source_snapshot_hash!==v.source_hash||await hash(omit(p,['plan_hash','can_confirm','can_calculate']))!==p.plan_hash||await hash({source_snapshot:s,plan:p})!==v.preview_hash)throw bad('Der Teilmonatsplan ist nicht unverändert an seine ursprünglichen Quellen gebunden.');
 if(p.can_calculate&&(p.factor_transition_period_component.factor_transition_period_components.original_profile_sha256!==await hash(s.profiles[0].profile)||p.factor_transition_period_component.factor_transition_period_components.original_period_plan_hash!==s.period_case.plan.plan_hash))throw bad('Die vollständige Teilmonatskomponente enthält nicht die ursprünglichen Profil- und Periodenbindungen.');
 if(v.details)factorTransitionPeriodBindings(s,v.details,p);
 return v;
}

export function factorTransitionPeriodCalculation(v){
 if(v?.rule_version!==PAYROLL_FACTOR_TRANSITION_PERIOD_RULE||v.source_contract_version!==7)throw bad('Unbekannte Faktor-/Midijob-Teilmonatsrechnung.');
 const scalars=['employee_social_total_minor','employer_social_total_minor','employer_flat_tax_minor','employer_total_excluding_accident_insurance_minor','individual_wage_tax_minor','solidarity_minor','church_tax_minor','employee_tax_minor','net_minor','payout_minor','employee_additional_payment_minor','net_deductions_minor'];
 if(v.scope==='unsupported'){
  if(v.payroll_calculation_complete!==false||v.social_contributions_available!==false||!v.blockers?.length||[...scalars,'employee_contributions','employer_contributions','employer_levies'].some(k=>v[k]!==null))throw bad('Ein gesperrter Teilmonat darf keinen vollständigen Geldbetrag ausgeben.');
  return v;
 }
 if(v.scope!==PAYROLL_FACTOR_TRANSITION_PERIOD_SCOPE||v.payroll_calculation_complete!==true||v.social_contributions_available!==true||v.blockers.length||v.travel_expenses_included_in_net!==false||v.net_deductions_minor!==0||v.official_system_approval!==false||v.statutory_report_status!=='not_transmitted')throw bad('Unbekannter oder nicht vollständig geprüfter Teilmonatsumfang.');
 for(const k of scalars)integer(v[k],k==='net_minor'?-1e12:0);
 shape(v.employee_contributions,'health_general health_additional pension unemployment care');shape(v.employer_contributions,'health_general health_additional pension unemployment care');shape(v.employer_levies,'u1 u2 insolvency');
 const sum=map=>Object.values(map).reduce((a,n)=>a+integer(n),0),component=v.factor_transition_period_components,tax=component?.factor_tax;
 if(!component||!tax||tax.factor!==v.tax_parameters?.tax_factor||!same(component.assessment,v.period_details.factor_transition_period_assessment)||!same(component.branch_bases,v.transition?.branch_bases)||!same(component.care_adjustments,v.transition?.care_adjustments)||v.transition?.factor!=='0.6619'||sum(v.employee_contributions)!==v.employee_social_total_minor||sum(v.employer_contributions)!==v.employer_social_total_minor||v.employee_tax_minor!==v.individual_wage_tax_minor+v.solidarity_minor+v.church_tax_minor||v.net_minor!==v.gross_minor-v.employee_social_total_minor-v.employee_tax_minor||v.payout_minor!==Math.max(0,v.net_minor)||v.employee_additional_payment_minor!==Math.max(0,-v.net_minor)||v.employer_total_excluding_accident_insurance_minor!==v.gross_minor+v.employer_social_total_minor+sum(v.employer_levies))throw bad('Der Teilmonatsbetrag oder seine ursprünglichen Steuer-/Beitragskomponenten wurden ersetzt.');
 if(tax.totals.LSTLZZ!==v.individual_wage_tax_minor||tax.totals.SOLZLZZ!==v.solidarity_minor||tax.totals.BK!==v.tax_parameters.church_assessment_minor||Math.floor(tax.totals.BK*Number(v.tax_parameters.church_tax_percent)/100)!==v.church_tax_minor)throw bad('Die tatsächliche Faktorsteuer und Kirchensteuer stimmen nicht überein.');
 const days=v.period_details.tax_periods[0].tax_days,input=tax.inputs;
 if(input.lzz!==4||input.tax_days!==days||input.gross_minor!==v.gross_minor||input.pap_gross_minor!==Math.floor(v.gross_minor/days)||input.gross_divisor!==days||input.gross_remainder_minor!==v.gross_minor%days||['LSTLZZ','SOLZLZZ','BK'].some(k=>integer(tax.component[k])*days!==tax.totals[k]))throw bad('Tägliche Steuer, tatsächliche Steuertage und ungekürztes Originalbrutto widersprechen sich.');
 return v;
}

export async function verifyFactorTransitionPeriodRun(v){
 const fact=v.source?.calculation_case;
 await verifyFactorTransitionPeriodCase(fact);factorTransitionPeriodCalculation(v.calculation);
 if(await hash({source:v.source,calculation:v.calculation})!==v.preview_hash||v.calculation.gross_minor!==fact.plan.gross_minor||v.calculation.period_details.plan_hash!==fact.plan.plan_hash||v.calculation.period_details.source_snapshot_hash!==fact.source_hash)throw bad('Der Lohnlauf entspricht nicht dem unveränderten Teilmonatsplan.');
 if(v.calculation.scope!=='unsupported'&&!same(omit(v.calculation,['period_details']),fact.plan.factor_transition_period_component))throw bad('Die vollständige angenommene Teilmonatskomponente wurde gegenüber der ausdrücklichen Vorschau verändert.');
 for(const key of ['employment_intervals','identity_intervals','earnings','tax_periods','social_periods','entitlement_sources','unpaid_dates','social_continuation','travel','flat_travel_tax','travel_source_hashes','factor_parameters','factor_transition_period_assessment'])if(!same(v.calculation.period_details[key],fact.plan[key]))throw bad('Ein angenommener ursprünglicher Teilmonatsplan wurde ersetzt.');
 if(v.calculation.scope!=='unsupported'){
  const c=v.calculation.factor_transition_period_components;
  if(c.original_profile_sha256!==await hash(fact.sources.profiles[0].profile)||c.original_period_plan_hash!==fact.sources.period_case.plan.plan_hash||v.calculation.rules_sha256!==fact.plan.rules_sha256)throw bad('Das ursprüngliche Faktorprofil oder seine historische Periodenfassung wurde ersetzt.');
 }
 return v;
}

export function factorTransitionPeriodInput(id,s,v,previous=null){
 const month=v.month,dates=payrollFactDates(month),base=s.factor_period_facts?.find(r=>r.id===v.period_case_id);
 if(!base||!factorTransitionPeriodSelectable(base,month)||previous&&(previous.rule_version!==PAYROLL_FACTOR_TRANSITION_PERIOD_RULE||previous.source_contract_version!==7||previous.details.month!==month))throw bad('Einen ursprünglichen belegten Eintritts-/Austrittsteilmonat auswählen.');
 if(v.segment_events?.length||v.entitlement_case_ids?.length||v.travel_settlement_ids?.length||v.travel_payment_ids?.length||v.policy_id||v.thirty_day_rule&&v.thirty_day_rule!=='actual_days_capped_per_claim')throw bad('Zusätzliche Vorgänge gehören nicht zum einfachen Teilmonatsvertrag.');
 const refs=(items,ids,kind)=>{if(!Array.isArray(ids)||ids.length!==1)throw bad('Genau eine ursprüngliche Fassung ausdrücklich auswählen.');const r=items.find(r=>r.id===ids[0]&&r.status!=='void'&&(!kind||r.kind===kind));if(!r)throw bad('Eine ursprüngliche Teilmonatsquelle fehlt.');return [payrollFactRef(r)];};
 const terms=refs(s.facts,v.employment_terms_ids,'employment_terms'),profiles=refs(s.profiles,v.profile_ids),identities=refs(s.identities,v.identity_ids);
 if(!same(terms,[payrollFactRef(base.sources.employment_terms)])||!same(profiles,base.details.profile_refs)||!same(identities,base.details.identity_refs))throw bad('Die ursprünglichen Teilmonatsfassungen vollständig und unverändert wählen.');
 if(s.entitlements.some(r=>r.status==='active'&&r.effective_from<=dates.at(-1)&&r.effective_to>=dates[0])||s.travel_settlements.some(r=>r.status==='approved'&&r.details.period_from<=dates.at(-1)&&r.details.period_to>=dates[0]))throw bad('Zusätzliche Ansprüche und Reisen benötigen einen eigenen Teilmonatsvertrag.');
 const review=copy(factorTransitionPeriodAssessment(v.factor_transition_period_assessment,id)),files=v.source_file_ids;
 review.verification_note=note(review.verification_note);review.transition_assessment.note=note(review.transition_assessment.note,2000);
 if(!Array.isArray(files)||!files.length||files.length>20||new Set(files).size!==files.length||files.some(id=>!s.files.some(r=>r.id===id))||!files.includes(review.forecast_evidence_ref.id)||!s.files.some(r=>r.id===review.forecast_evidence_ref.id&&r.content_hash===review.forecast_evidence_ref.content_hash))throw bad('Das private tatsächliche Prognoseoriginal ausdrücklich binden.');
 return {employee_id:id,employee_revision:s.employee.revision,kind:'calculation_case',rule_version:PAYROLL_FACTOR_TRANSITION_PERIOD_RULE,source_contract_version:7,
  details:{month,period_case_ref:payrollFactRef(base),employment_terms_refs:terms,profile_refs:profiles,identity_refs:identities,segment_events:[],thirty_day_rule:'actual_days_capped_per_claim',entitlement_case_refs:[],travel_settlement_refs:[],flat_tax_decision:null,factor_transition_period_assessment:review,verification_note:note(v.verification_note)},
  source_file_ids:[...files].sort(),revision:previous?.revision||0,status:'active',confirmed:true,...previous?{id:previous.id,correction_reason:note(v.correction_reason)}:{}};
}
