import {payrollFactRef,payrollFactRecord,payrollFactDate,payrollFactDates} from './payroll-facts.js';

export const PAYROLL_FACTOR_TRAVEL_RULE='de_2026_factor_taxfree_travel_month_v10';
export const PAYROLL_FACTOR_TRAVEL_FEATURE='payroll_factor_taxfree_travel';
export const PAYROLL_FACTOR_TRAVEL_SCOPE='regular_standard_factor_taxfree_travel_month';
const HASH=/^[a-f0-9]{64}$/;
const fail=message=>Object.assign(new Error(message),{status:400});
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(key=>[key,ordered(v[key])])):v;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const sortedRefs=rows=>rows.map(payrollFactRef).sort((a,b)=>a.id.localeCompare(b.id));
const money=value=>{if(!Number.isSafeInteger(value)||value<0)throw fail('Der belegte Reisebetrag ist ungültig.');return value;};

export function factorTravelPayment(value,settlements=null){
 payrollFactRef(value);payrollFactRef(value.settlement_ref);payrollFactDate(value.paid_on);
 if(!['active','void'].includes(value.status)||!['reimbursement','repayment'].includes(value.kind))throw fail('Der tatsächliche Reisezahlungsnachweis ist nicht eindeutig.');
 money(value.amount_minor);
 if(settlements&&!settlements.some(item=>same(payrollFactRef(item),value.settlement_ref)))throw fail('Die Reisezahlung gehört nicht zu einer ausgewählten Reiseabrechnung.');
 return value;
}

export function factorTravelSources(s,id){
 if(!Array.isArray(s.factor_period_facts)||!Array.isArray(s.travel_payment_proofs))throw fail('Der Server liefert noch keine geprüften Faktor- und Reisezahlungsquellen.');
 const periods=new Set(),payments=new Set(),keys=['id','revision','content_hash','settlement_ref','status','kind','paid_on','amount_minor'].sort();
 for(const item of s.factor_period_facts){payrollFactRecord(item,id,'period_case');if(item.plan?.rule_version!=='de_2026_standard_factor_period_v9'||periods.has(item.id))throw fail('Der Basisfall gehört nicht zum geprüften Faktorregelstand.');periods.add(item.id);}
 for(const item of s.travel_payment_proofs){factorTravelPayment(item,s.travel_settlements);if(payments.has(item.id)||!same(Object.keys(item).sort(),keys))throw fail('Die begrenzten Reisezahlungsquellen sind nicht eindeutig.');payments.add(item.id);}
 return s;
}

export function factorTravelPeriodSelectable(item,month){
 const plan=item?.plan,days=payrollFactDates(month);
 return item?.status==='active'&&plan?.rule_version==='de_2026_standard_factor_period_v9'&&item.details?.month===month&&plan?.can_calculate===true&&plan.tax_periods?.length===1&&plan.tax_periods[0].lzz===2&&plan.tax_periods[0].start===days[0]&&plan.tax_periods[0].end===days.at(-1)&&plan.social_periods?.length===1&&plan.social_periods[0].full_month===true;
}

export function factorTravelPlan(plan){
 if(plan.rule_version!==PAYROLL_FACTOR_TRAVEL_RULE||plan.source_contract_version!==2)throw fail('Unbekannter Faktor-Reisefall.');
 if(!Array.isArray(plan.travel_payment_refs)||!plan.travel_payment_refs.length||new Set(plan.travel_payment_refs.map(ref=>payrollFactRef(ref).id)).size!==plan.travel_payment_refs.length)throw fail('Die vollständigen Reisezahlungsbelege fehlen.');
 money(plan.travel_paid_minor);
 if(plan.travel?.tax_free_external_minor!==plan.travel_paid_minor||['flat_taxable_payroll_minor','individual_taxable_payroll_minor','benefit_in_kind_non_cash_minor'].some(key=>plan.travel?.[key]!==0)||plan.travel?.letter_m!==false||plan.flat_travel_tax!==null||plan.entitlement_sources.length||plan.unpaid_dates.length)throw fail('Dieser Faktorfall erlaubt ausschließlich bereits bezahlte steuerfreie Reisen ohne Ansprüche oder Sachbezüge.');
 if(plan.can_calculate){
  const days=payrollFactDates(plan.month),tax=plan.tax_periods,social=plan.social_periods;
  if(plan.employment_intervals.length!==1||tax.length!==1||social.length!==1||tax[0].lzz!==2||tax[0].tax_days!==30||social[0].days!==30||social[0].full_month!==true||[plan.employment_intervals[0],tax[0],social[0]].some(period=>period.start!==days[0]||period.end!==days.at(-1)))throw fail('Der Faktor-Reisefall benötigt einen einzigen vollständigen Beschäftigungsmonat.');
  if(!/^0\.[0-9]{3}$/.test(plan.factor_parameters?.tax_factor||''))throw fail('Der belegte Faktor fehlt.');
  payrollFactRef(plan.factor_parameters.profile_ref);
 }
 return plan;
}

export function factorTravelBindings(s,d,plan){
 if(d.segment_events.length||d.entitlement_case_refs.length||d.thirty_day_rule!==null||d.flat_tax_decision!==null||['employment_terms_refs','profile_refs','identity_refs'].some(key=>d[key].length!==1)||s.period_case.plan?.rule_version!=='de_2026_standard_factor_period_v9'||!Array.isArray(d.travel_payment_refs)||!d.travel_payment_refs.length||!s.travel_sources.length)throw fail('Die ursprünglichen Faktor-, Vollmonats- und Reisequellen sind nicht vollständig.');
 const payments=[],settlements=new Set();let total=0;
 for(const travel of s.travel_sources){
  const proof=travel.payment_proof;
  if(travel.kind!=='travel_allowances'||travel.schema_version!==1||!HASH.test(travel.source_hash||'')||!HASH.test(travel.rule_hash||'')||!Array.isArray(travel.allocations)||travel.allocations.length!==0||travel.letter_m!==false||['flat_taxable_payroll_minor','individual_taxable_payroll_minor','benefit_in_kind_non_cash_minor'].some(key=>travel[key]!==0)||!proof||proof.schema_version!==1||!Array.isArray(proof.payments)||!proof.payments.length||!Number.isSafeInteger(proof.cutoff_sequence)||proof.cutoff_sequence<1)throw fail('Die steuerfreie Reise besitzt keinen vollständigen ursprünglichen Zahlungsnachweis.');
  if(settlements.has(travel.settlement_ref.id))throw fail('Eine Reiseabrechnung wurde mehrfach gebunden.');settlements.add(travel.settlement_ref.id);
  const sequences=new Set();let paid=0;
  for(const value of proof.payments){
   factorTravelPayment({...value,settlement_ref:travel.settlement_ref});
   if(!Number.isSafeInteger(value.sequence)||value.sequence<1||value.sequence>proof.cutoff_sequence||sequences.has(value.sequence)||!HASH.test(value.cash_source_hash||''))throw fail('Die ursprüngliche Folge der Reisezahlungen ist widersprüchlich.');
   sequences.add(value.sequence);payments.push(value);
   if(value.status==='active')paid+=(value.kind==='reimbursement'?1:-1)*value.amount_minor;
  }
  if(Math.max(...sequences)!==proof.cutoff_sequence||paid!==money(proof.paid_minor)||paid!==money(travel.tax_free_external_minor))throw fail('Die belegte Reiseerstattung ist nicht vollständig ausgezahlt.');
  total+=paid;
 }
 const expected=sortedRefs(payments),actual=sortedRefs(d.travel_payment_refs);
 if(new Set(expected.map(ref=>ref.id)).size!==expected.length||!same(expected,actual)||!same(plan.travel_payment_refs,d.travel_payment_refs)||!same(plan.travel_source_hashes,s.travel_sources.map(source=>source.source_hash))||total!==plan.travel_paid_minor)throw fail('Die ursprünglichen Reisezahlungen wurden ersetzt oder nicht vollständig ausgewählt.');
 if(plan.can_calculate&&(!same(plan.factor_parameters.profile_ref,d.profile_refs[0])||plan.factor_parameters.tax_factor!==s.profiles[0]?.profile?.tax_factor))throw fail('Der Faktor gehört nicht zur ausgewählten Profilfassung.');
}

export function factorTravelInput(id,s,v,previous=null){
 factorTravelSources(s,id);
 if(previous&&(previous.rule_version!==PAYROLL_FACTOR_TRAVEL_RULE||previous.source_contract_version!==2))throw fail('Die ursprüngliche Abrechnungsregel bleibt bei einer Korrektur erhalten.');
 const refs=(items,ids,kind=null)=>{
  if(!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length)throw fail('Die einschlägigen Originalquellen ausdrücklich auswählen.');
  return [...ids].sort().map(id=>{const item=items.find(item=>item.id===id&&item.status!=='void'&&(!kind||item.kind===kind));if(!item)throw fail('Eine Originalquelle ist nicht mehr aktuell.');return payrollFactRef(item);});
 };
 if(['employment_terms_ids','profile_ids','identity_ids'].some(key=>v[key]?.length!==1)||v.segment_events?.length||(v.entitlement_case_ids||[]).length||v.thirty_day_rule||v.policy_id)throw fail('Dieser Faktorfall erlaubt genau einen Vollmonatsgrundfall ohne zusätzliche Ansprüche oder Pauschalsteuer.');
 const files=v.source_file_ids;
 if(!Array.isArray(files)||!files.length||files.length>20||new Set(files).size!==files.length||files.some(id=>!s.files.some(file=>file.id===id)))throw fail('Ein bis zwanzig geschützte Personaloriginale auswählen.');
 if(typeof v.verification_note!=='string'||!v.verification_note.trim()||v.verification_note.trim().length>3000||/[\x00-\x1f\x7f]/.test(v.verification_note))throw fail('Die Prüfung der Faktor- und Reisequellen vollständig dokumentieren.');
 if(previous&&(typeof v.correction_reason!=='string'||!v.correction_reason.trim()||v.correction_reason.trim().length>3000||/[\x00-\x1f\x7f]/.test(v.correction_reason)))throw fail('Den Korrekturgrund vollständig dokumentieren.');
 if(!s.factor_period_facts.some(item=>item.id===v.period_case_id&&factorTravelPeriodSelectable(item,v.month)))throw fail('Einen bestätigten vollständigen Faktor-Monatsfall auswählen.');
 const settlementRefs=refs(s.travel_settlements,v.travel_settlement_ids),paymentIds=v.travel_payment_ids;
 if(!Array.isArray(paymentIds)||!paymentIds.length||new Set(paymentIds).size!==paymentIds.length)throw fail('Die tatsächlichen Reisezahlungen ausdrücklich auswählen.');
 const payments=paymentIds.map(id=>{const value=s.travel_payment_proofs.find(item=>item.id===id);if(!value||!settlementRefs.some(ref=>same(ref,value.settlement_ref)))throw fail('Die gewählte Reisezahlung gehört nicht zur ausgewählten Abrechnung.');return value;});
 const required=s.travel_payment_proofs.filter(value=>settlementRefs.some(ref=>same(ref,value.settlement_ref)));
 if(!same(sortedRefs(payments),sortedRefs(required)))throw fail('Sämtliche ursprünglichen Zahlungsfassungen der ausgewählten Reisen müssen enthalten sein.');
 return {employee_id:id,employee_revision:s.employee.revision,kind:'calculation_case',rule_version:PAYROLL_FACTOR_TRAVEL_RULE,source_contract_version:2,details:{month:v.month,period_case_ref:refs(s.factor_period_facts,[v.period_case_id],'period_case')[0],employment_terms_refs:refs(s.facts,v.employment_terms_ids,'employment_terms'),profile_refs:refs(s.profiles,v.profile_ids),identity_refs:refs(s.identities,v.identity_ids),segment_events:[],thirty_day_rule:null,entitlement_case_refs:[],travel_settlement_refs:settlementRefs,travel_payment_refs:sortedRefs(payments),flat_tax_decision:null,verification_note:v.verification_note.trim()},source_file_ids:[...files].sort(),revision:previous?.revision||0,status:'active',confirmed:true,...previous?{id:previous.id,correction_reason:v.correction_reason?.trim()}: {}};
}
