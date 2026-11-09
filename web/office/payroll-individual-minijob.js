import {payrollFactRef,payrollFactRecord,payrollFactDate,payrollFactDates,payrollFactMonth} from './payroll-facts.js';

export const INDIVIDUAL_MINIJOB_RULE='de_2026_individual_minijob_month_v11';
export const INDIVIDUAL_MINIJOB_FEATURE='payroll_individual_minijob';
export const INDIVIDUAL_MINIJOB_SCOPE='commercial_minijob_individual_month';
export const MINIJOB_CONFIRMATIONS={sole_employment_confirmed:'Die alleinige Beschäftigung ist anhand der Originale bestätigt.',income_review_complete:'Die Einkommensprüfung ist vollständig dokumentiert.',no_other_relevant_income_confirmed:'Weitere relevante Einkünfte sind anhand der Erklärung ausgeschlossen.',domestic_commercial_employment_confirmed:'Die Beschäftigung ist inländisch und gewerblich.',no_foreign_insurance_confirmed:'Eine Auslandsversicherung ist anhand der Originale ausgeschlossen.',no_other_special_cases_confirmed:'Weitere Sonderfälle sind anhand der Originale ausgeschlossen.'};
export const MINIJOB_EVIDENCE={health_evidence_ref:'Nachweis der beitragsfreien gesetzlichen Familienversicherung',pension_evidence_ref:'Nachweis der wirksamen Rentenversicherungspflicht oder Befreiung',employment_evidence_ref:'Nachweis der alleinigen inländischen Beschäftigung',income_evidence_ref:'Nachweis der vollständigen Einkommensprüfung',elstam_evidence_ref:'Original des ausgewählten ELStAM-Nachweises'};
const HASH=/^[a-f0-9]{64}$/;
const fail=message=>Object.assign(new Error(message),{status:400});
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(key=>[key,ordered(v[key])])):v;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const integer=(v,min=0,max=1e12)=>{if(!Number.isSafeInteger(v)||v<min||v>max)throw fail('Der belegte Minijobbetrag oder Zeitraum ist ungültig.');return v;};
export function minijobNote(value){
 if(typeof value!=='string'||!value.trim()||[...value].length>3000)throw fail('Die Prüfung der Minijoboriginale vollständig dokumentieren.');
 for(const ch of value){const n=ch.codePointAt(0);if(n>=0xd800&&n<=0xdfff||n<32&&ch!=='\n'&&ch!=='\t')throw fail('Der Prüftext enthält unzulässige Zeichen.');}
 return value.trim();
}
function exactKeys(value,keys){if(!value||typeof value!=='object'||Array.isArray(value)||!same(Object.keys(value).sort(),[...keys].sort()))throw fail('Der neue Minijobnachweis ist nicht vollständig oder besitzt unbekannte Angaben.');}
export function minijobProfile(profile){
 return profile?.employment_kind==='minijob'&&profile.minijob_tax==='individual'&&profile.health_insurance==='statutory_other'&&[1,5].includes(profile.tax_class)&&profile.tax_children_half_units===0&&profile.church_tax==='none'&&profile.pension_other_compulsory===false&&Array.isArray(profile.special_cases)&&profile.special_cases.length===0&&typeof profile.minijob_rv_exempt==='boolean';
}
export function minijobAssessment(value,id,month,{complete=true}={}){
 exactKeys(value,['schema_version','employee_id','valid_from','valid_to','declaration_date','actual_health_insurance','pension_status','verification_note',...Object.keys(MINIJOB_CONFIRMATIONS),...Object.keys(MINIJOB_EVIDENCE)]);
 if(value.schema_version!==1||value.employee_id!==id)throw fail('Die Minijobprüfung gehört nicht zur ausgewählten Person.');
 for(const key of ['valid_from','valid_to','declaration_date'])if(payrollFactDate(value[key])!==value[key])throw fail('Die tatsächlichen Prüfdaten unverändert angeben.');
 if(value.valid_from>value.valid_to||!['statutory_family','statutory_mandatory','statutory_voluntary','private','unknown'].includes(value.actual_health_insurance)||!['compulsory','exempt','unknown'].includes(value.pension_status))throw fail('Versicherungsstatus und Wirkungszeitraum ausdrücklich belegen.');
 for(const key of Object.keys(MINIJOB_CONFIRMATIONS))if(typeof value[key]!=='boolean'||complete&&value[key]!==true)throw fail('Jede erforderliche Minijobprüfung ausdrücklich bestätigen.');
 for(const key of Object.keys(MINIJOB_EVIDENCE)){exactKeys(value[key],['id','revision','content_hash']);payrollFactRef(value[key]);if(value[key].revision!==1)throw fail('Das unveränderte Personalaktenoriginal auswählen.');}
 minijobNote(value.verification_note);
 const dates=payrollFactDates(month);
 if(complete&&(value.actual_health_insurance!=='statutory_family'||value.valid_from>dates[0]||value.valid_to<dates.at(-1)))throw fail('Die beitragsfreie Familienversicherung und die Prüfung müssen den vollständigen Lohnmonat abdecken.');
 return value;
}
export function minijobIdentity(value){
 const d=value?.details,p=value?.sources?.profile?.profile;
 if(d?.identity_source_schema_version!==2||!minijobProfile(p)||d.tax_source!=='elstam_imported'||d.tax_allowance_yearly_minor!==0||d.tax_addition_yearly_minor!==0||d.religion_code!=='none'||d.profile_id!==value.sources.profile.id||d.profile_revision!==value.sources.profile.revision)throw fail('Der neue Identitätsnachweis benötigt das tatsächliche individuelle Minijobprofil und sein ELStAM-Original.');
 return value;
}
function technical(profile,gross){return {ALTER1:0,ALV:1,KRV:profile.minijob_rv_exempt?1:0,KVZ:'0',LZZ:2,LZZFREIB:0,LZZHINZU:0,PKPV:0,PKPVAGZ:0,PKV:1,PVA:0,PVS:0,PVZ:0,RE4:gross,STKL:profile.tax_class,ZKF:0,af:0,f:'1'};}
export function minijobBaseEligible(value,month){
 const p=value?.plan,days=payrollFactDates(month);
 return value?.kind==='period_case'&&value.status==='active'&&value.details?.month===month&&p?.rule_version==='de_2026_periods_pap_v4'&&Array.isArray(p.blockers)&&p.blockers.length===1&&p.blockers[0].code==='minijob_individual_tax'&&p.employment_intervals?.length===1&&p.employment_intervals[0].start===days[0]&&p.employment_intervals[0].end===days.at(-1)&&p.tax_periods?.length===1&&p.tax_periods[0].lzz===2&&p.social_periods?.length===1&&p.social_periods[0].full_month===true;
}
export function minijobUpgradeEligible(value){
 return value?.kind==='calculation_case'&&value.rule_version==='de_2026_segments_entitlements_v5'&&value.source_contract_version===1&&value.status==='active'&&value.plan?.can_calculate===false&&value.plan.blockers?.some(row=>row.code==='minijob_individual_tax')&&value.sources?.profiles?.length===1&&value.sources.profiles[0].profile?.employment_kind==='minijob'&&value.sources.profiles[0].profile?.minijob_tax==='individual';
}
export function minijobPlan(value,id,month){
 payrollFactMonth(month);
 if(value?.schema_version!==1||value.rule_version!==INDIVIDUAL_MINIJOB_RULE||value.source_contract_version!==3||value.employee_id!==id||value.month!==month||['rules_sha256','source_snapshot_hash','plan_hash'].some(key=>!HASH.test(value[key]||''))||['employment_intervals','identity_intervals','earnings','tax_periods','social_periods','blockers'].some(key=>!Array.isArray(value[key]))||typeof value.can_confirm!=='boolean'||typeof value.can_calculate!=='boolean'||value.can_calculate!==(value.blockers.length===0))throw fail('Der individuelle Minijobplan gehört nicht zum bestätigten Quellenvertrag.');
 payrollFactRef(value.selected_profile_ref);payrollFactRef(value.selected_identity_ref);
 minijobAssessment(value.individual_minijob_assessment,id,month,{complete:value.can_calculate});
 if(value.can_calculate){
  integer(value.gross_minor,17500,60300);const dates=payrollFactDates(month);
  for(const key of ['employment_intervals','tax_periods','social_periods'])if(value[key].length!==1||value[key][0].start!==dates[0]||value[key][0].end!==dates.at(-1))throw fail('Der individuelle Minijob benötigt einen vollständigen Kalendermonat.');
  if(value.tax_periods[0].lzz!==2||value.tax_periods[0].tax_days!==30||value.social_periods[0].days!==30||value.social_periods[0].full_month!==true||value.earnings.some(row=>row.kind!=='ordinary_work')||value.earnings.reduce((sum,row)=>sum+integer(row.gross_minor),0)!==value.gross_minor||value.actual_health_insurance!=='statutory_family')throw fail('Der Minijobplan enthält einen anderen Entgelt- oder Versicherungsfall.');
 }
 return value;
}
export function minijobBindings(s,d,files,id,plan){
 exactKeys(s,['schema_version','source_contract_version','rule_version','employee_id','month','period_case','employment_terms','profiles','identities','segment_events','thirty_day_rule','entitlements','travel_sources','flat_travel_tax','source_files','individual_minijob_assessment']);
 if(s.schema_version!==1||s.source_contract_version!==3||s.rule_version!==INDIVIDUAL_MINIJOB_RULE||s.employee_id!==id||s.month!==d.month||!same(s.individual_minijob_assessment,d.individual_minijob_assessment)||!same(plan.individual_minijob_assessment,d.individual_minijob_assessment))throw fail('Der neue Minijobplan und die ursprüngliche Prüfung widersprechen sich.');
 if(['employment_terms_refs','profile_refs','identity_refs'].some(key=>d[key]?.length!==1)||['segment_events','entitlement_case_refs','travel_settlement_refs'].some(key=>!Array.isArray(d[key])||d[key].length)||d.thirty_day_rule!==null||d.flat_tax_decision!==null||s.entitlements.length||s.travel_sources.length||s.segment_events.length||s.thirty_day_rule!==null||s.flat_travel_tax!==null)throw fail('Der individuelle Minijobfall enthält nicht erlaubte Zusatzquellen.');
 const base=s.period_case;payrollFactRecord(base,id,'period_case');
 if(!same(payrollFactRef(base),d.period_case_ref)||base.plan.rule_version!=='de_2026_periods_pap_v4'||!same(base.sources.profiles,s.profiles)||!same(base.sources.identities,s.identities)||!same([base.sources.employment_terms],s.employment_terms))throw fail('Der ursprüngliche Monatsfall wurde ersetzt.');
 for(const [key,refs]of [['profiles','profile_refs'],['identities','identity_refs'],['employment_terms','employment_terms_refs']])if(!Array.isArray(s[key])||s[key].length!==1||s[key][0].employee_id!==id||!same(s[key].map(payrollFactRef),d[refs]))throw fail('Die gebundenen Minijobquellen gehören nicht zur Person oder Fassung.');
 const profile=s.profiles[0].profile,assessment=d.individual_minijob_assessment;
 minijobAssessment(assessment,id,d.month,{complete:plan.can_calculate});if(plan.can_calculate)minijobIdentity(s.identities[0]);
 if(!same(s.source_files.map(file=>file.id).sort(),[...files].sort())||s.source_files.some(file=>file.employee_id!==id||file.purpose!=='personnel'))throw fail('Die privaten Personaloriginale wurden ersetzt.');
 for(const key of Object.keys(MINIJOB_EVIDENCE)){const ref=assessment[key],file=s.source_files.find(file=>file.id===ref.id);if(!file||file.content_hash!==ref.content_hash)throw fail('Ein konkretes Minijobprüfungsoriginal fehlt.');}
 const identity=s.identities[0];if(assessment.elstam_evidence_ref.id!==identity.source_file.id||assessment.elstam_evidence_ref.content_hash!==identity.source_file.content_hash)throw fail('Die ELStAM-Prüfung bezieht sich nicht auf das gebundene Identitätsoriginal.');
 if(plan.can_calculate&&(!minijobProfile(profile)||assessment.pension_status!==(profile.minijob_rv_exempt?'exempt':'compulsory')||!same(plan.technical_pap_parameters,technical(profile,plan.gross_minor))||!same(plan.selected_profile_ref,d.profile_refs[0])||!same(plan.selected_identity_ref,d.identity_refs[0])))throw fail('Versicherungs-, Steuer- und Originalmerkmale passen nicht zum Minijobplan.');
}
export function minijobInput(id,s,v,previous=null){
 const month=payrollFactMonth(v.month);
 if(v.segment_events?.length||v.entitlement_case_ids?.length||v.travel_settlement_ids?.length||v.thirty_day_rule||v.policy_id)throw fail('Zusätzliche Ansprüche, Reisen oder Profilereignisse gehören nicht zu diesem Minijobvertrag.');
 if(previous&&(previous.details.month!==month||previous.rule_version!==INDIVIDUAL_MINIJOB_RULE&&!minijobUpgradeEligible(previous)))throw fail('Dieser historische Gesamtfall darf nicht in den individuellen Minijobvertrag geändert werden.');
 const refs=(items,ids,kind=null)=>{if(!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length)throw fail('Die eigenen Minijoboriginale ausdrücklich auswählen.');return [...ids].sort().map(id=>{const item=items.find(row=>row.id===id&&row.status!=='void'&&(!kind||row.kind===kind));if(!item)throw fail('Die ausgewählte Minijobquelle ist nicht aktuell.');return payrollFactRef(item);});};
 if(['employment_terms_ids','profile_ids','identity_ids'].some(key=>v[key]?.length!==1))throw fail('Genau eine Beschäftigung, ein Profil und eine Identitätsfassung auswählen.');
 const base=s.facts.find(row=>row.id===v.period_case_id);if(!minijobBaseEligible(base,month))throw fail('Den bestätigten vollständigen Monatsfall mit bisher gesperrter Individualsteuer auswählen.');
 const files=v.source_file_ids;if(!Array.isArray(files)||!files.length||files.length>20||new Set(files).size!==files.length||files.some(id=>!s.files.some(file=>file.id===id&&file.purpose==='personnel')))throw fail('Die geschützten Personalaktenoriginale auswählen.');
 const a={schema_version:1,employee_id:id,valid_from:v.valid_from,valid_to:v.valid_to,declaration_date:v.declaration_date,actual_health_insurance:v.actual_health_insurance,pension_status:v.pension_status,verification_note:minijobNote(v.assessment_note)};
 for(const key of Object.keys(MINIJOB_CONFIRMATIONS))a[key]=v[key];
 for(const key of Object.keys(MINIJOB_EVIDENCE)){const file=s.files.find(file=>file.id===v[key+'_id']);if(!file||!files.includes(file.id)||file.purpose!=='personnel')throw fail('Jeden konkreten Prüfungsbeleg zusätzlich als Personaloriginal binden.');a[key]={id:file.id,revision:1,content_hash:file.content_hash};}
 minijobAssessment(a,id,month);
 return {employee_id:id,employee_revision:s.employee.revision,kind:'calculation_case',rule_version:INDIVIDUAL_MINIJOB_RULE,source_contract_version:3,details:{month,period_case_ref:payrollFactRef(base),employment_terms_refs:refs(s.facts,v.employment_terms_ids,'employment_terms'),profile_refs:refs(s.profiles,v.profile_ids),identity_refs:refs(s.identities,v.identity_ids),segment_events:[],thirty_day_rule:null,entitlement_case_refs:[],travel_settlement_refs:[],flat_tax_decision:null,verification_note:minijobNote(v.verification_note),individual_minijob_assessment:a},source_file_ids:[...files].sort(),revision:previous?.revision||0,status:'active',confirmed:true,...previous?{id:previous.id,correction_reason:minijobNote(v.correction_reason)}:{}};
}
export function minijobCalculation(v){
 const d=v?.period_details,arrays=['earnings','employment_intervals','identity_intervals','tax_periods','social_periods','entitlement_sources','unpaid_dates','social_continuation'];
 if(v?.rule_version!==INDIVIDUAL_MINIJOB_RULE||v.source_contract_version!==3||v.currency!=='EUR'||!HASH.test(v.rules_sha256||'')||v.official_system_approval!==false||v.statutory_report_status!=='not_transmitted'||v.accident_insurance_included!==false||v.travel_expenses_included_in_net!==false||v.net_deductions_minor!==0||!Array.isArray(v.blockers)||!d||arrays.some(key=>!Array.isArray(d[key]))||!HASH.test(d.plan_hash||'')||!HASH.test(d.source_snapshot_hash||''))throw fail('Die individuelle Minijobabrechnung besitzt keinen bekannten Quellenvertrag.');
 payrollFactMonth(v.month);
 if(['entitlement_sources','unpaid_dates','social_continuation'].some(key=>d[key].length)||d.flat_travel_tax!==null||!same(d.travel,{tax_free_external_minor:0,flat_taxable_payroll_minor:0,individual_taxable_payroll_minor:0,benefit_in_kind_non_cash_minor:0,letter_m:false}))throw fail('Zusatzentgelte und Reisen sind in diesem Minijobvertrag nicht berechnet.');
 if(v.scope==='unsupported'){if(v.payroll_calculation_complete!==false||v.social_contributions_available!==false||['net_minor','payout_minor','employee_tax_minor','employee_social_total_minor','employer_social_total_minor'].some(key=>v[key]!==null))throw fail('Ein gesperrter Minijob darf keine vermeintlichen Nettowerte ausgeben.');return v;}
 if(!Array.isArray(d.tax_assessments)||!Array.isArray(d.social_assessments))throw fail('Die ursprünglichen Steuer- und Beitragsrechnungen fehlen.');
 if(v.scope!==INDIVIDUAL_MINIJOB_SCOPE||v.payroll_calculation_complete!==true||v.social_contributions_available!==true||v.blockers.length||v.employer_flat_tax_minor!==0)throw fail('Unbekannter berechenbarer Minijobumfang.');
 integer(v.gross_minor,17500,60300);const dates=payrollFactDates(v.month);
 for(const key of ['employment_intervals','tax_periods','social_periods'])if(d[key].length!==1||d[key][0].start!==dates[0]||d[key][0].end!==dates.at(-1))throw fail('Der Minijob benötigt einen vollständigen Lohnmonat.');
 if(d.tax_periods[0].lzz!==2||d.tax_periods[0].tax_days!==30||d.social_periods[0].days!==30||d.social_periods[0].full_month!==true||d.earnings.some(row=>row.kind!=='ordinary_work')||d.earnings.reduce((sum,row)=>sum+integer(row.gross_minor),0)!==v.gross_minor)throw fail('Die ausgewiesenen Zeiträume oder Entgelte widersprechen dem Minijobumfang.');
 const sum=map=>{if(!map||typeof map!=='object'||Array.isArray(map))throw fail('Die Beitragsaufstellung fehlt.');return Object.values(map).reduce((sum,v)=>sum+integer(v),0);};
 if(sum(v.employee_contributions)!==v.employee_social_total_minor||sum(v.employer_contributions)!==v.employer_social_total_minor||v.employer_total_excluding_accident_insurance_minor!==v.gross_minor+v.employer_social_total_minor+sum(v.employer_levies)||v.employee_tax_minor!==integer(v.individual_wage_tax_minor)+integer(v.solidarity_minor)+integer(v.church_tax_minor)||v.net_minor!==v.gross_minor-v.employee_social_total_minor-v.employee_tax_minor||v.payout_minor!==Math.max(0,v.net_minor)||v.employee_additional_payment_minor!==Math.max(0,-v.net_minor))throw fail('Die Minijobbeiträge, Steuer- und Nettosummen widersprechen sich.');
 if(['health_general','health_additional','unemployment','care'].some(key=>v.employee_contributions[key]!==0)||['health_additional','unemployment','care'].some(key=>v.employer_contributions[key]!==0)||v.tax_parameters?.actual_health_insurance!=='statutory_family'||v.tax_parameters.children_half_units!==0||v.tax_parameters.church_tax_percent!=='0'||![1,5].includes(v.tax_parameters.tax_class)||v.church_tax_minor!==0)throw fail('Die ausgewiesene Versicherung oder Steuerklasse gehört nicht zum begrenzten Minijobfall.');
 const tech=v.tax_parameters.technical_pap_parameters;
 if(tech?.KRV===1&&v.employee_contributions.pension!==0||tech?.KRV===0&&v.employee_contributions.pension<=0)throw fail('Der RV-Beitrag widerspricht dem belegten Befreiungsstatus.');
 if(!tech||![0,1].includes(tech.KRV)||!same(tech,technical({tax_class:v.tax_parameters.tax_class,minijob_rv_exempt:tech.KRV===1},v.gross_minor))||!HASH.test(v.pap_provenance_sha256||'')||v.pap_version!=='bmf_2026_individual_minijob_month_v1')throw fail('Die technischen PAP-Merkmale sind nicht an den ausgewiesenen Minijob gebunden.');
 if(d.tax_assessments.length!==1||!same(d.tax_assessments[0].period,d.tax_periods[0])||d.social_assessments.length!==1||!same(d.social_assessments[0].period,d.social_periods[0]))throw fail('Die Einzelberechnungen gehören nicht zu den ursprünglichen Zeiträumen.');
 const tax=d.tax_assessments[0];if(tax.calculation?.LSTLZZ!==v.individual_wage_tax_minor||tax.calculation?.SOLZLZZ!==v.solidarity_minor||tax.calculation?.BK!==0||tax.church_tax_minor!==0||tax.calculation?.version!==v.pap_version||tax.calculation?.provenance_sha256!==v.pap_provenance_sha256)throw fail('Die direkte PAP-Berechnung stimmt nicht mit den Minijobsteuern überein.');
 for(const key of ['employee_contributions','employer_contributions','employer_levies'])if(!same(d.social_assessments[0][key],v[key]))throw fail('Die ausgewiesenen Beiträge wurden gegenüber der Monatsgrundlage verändert.');
 return v;
}
