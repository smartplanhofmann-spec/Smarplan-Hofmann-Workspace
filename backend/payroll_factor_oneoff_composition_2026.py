"""Explicit V15 factor/P4 running wages plus one source-bound other payment.

The private API must establish immutable authority and freshness. This pure
component keeps every original, reuses unchanged SV primitives and adds the
new independently verified factor-other-payment tax. No payment is created.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path

from core import Problem,canonical
from payroll_de_2026 import month_range
from payroll_factor_2026 import normalize_factor_profile
from payroll_annual_basis_2026 import ANNUAL_BASIS_VERSION,normalize_details,build_annual_plan,employer_key,reference
from payroll_factor_annual_basis_2026 import RULE_VERSION as ANNUAL_V2,build_plan as factor_annual_plan
from payroll_factor_oneoff_2026 import FACTOR_ONEOFF_PAP_HASH,calculate_factor_one_off_tax
from payroll_oneoff_2026 import select_one_off_assignment,calculate_regular_one_off_contributions
import payroll_factor_claims_2026 as factor
import payroll_oneoff_composition_2026 as ordinary

RULE_VERSION='de_2026_factor_claims_oneoff_v15'
SOURCE_CONTRACT_VERSION=2
RULES=dict(version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION,
    running_rule=factor.RULE_VERSION,running_hash=factor.RULES_SHA256,
    annual_rule=ANNUAL_V2,oneoff_tax_hash=FACTOR_ONEOFF_PAP_HASH,
    social_version=ordinary.SOCIAL_ONEOFF_VERSION,social_hash=ordinary.SOCIAL_ONEOFF_HASH,
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    actual_payment_created=False)
RULES_SHA256=hashlib.sha256(canonical(RULES).encode()).hexdigest()


def sha(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def _annual(record,kind,employee_id,*,version=None):
    if (not isinstance(record,dict) or record.get('kind')!=kind or record.get('employee_id')!=employee_id
            or record.get('status')!='active'):
        raise Problem(409,'Aktive eigene ursprüngliche Jahresquelle erforderlich.')
    details=normalize_details(kind,record['details']);sources=record['sources']
    selected=record['plan']['rule_version']
    if version is not None and selected!=version:
        raise Problem(409,'Die Faktor-Einmalzahlung benötigt ihre ausdrücklich versionierte Jahresquelle.')
    if selected==ANNUAL_V2:expected=factor_annual_plan(sources,rule_version=selected)
    elif selected==ANNUAL_BASIS_VERSION and 'annual_source_contract' not in sources:expected=build_annual_plan(sources,rule_version=selected)
    else:raise Problem(409,'Unbekannte Original-Jahresquellenregel.')
    if (details!=record['details'] or sources['details']!=details or sources['kind']!=kind
            or sources['employee']['id']!=employee_id or expected!=record['plan']):
        raise Problem(409,'Jahresquelle und erneut hergeleiteter Originalplan widersprechen sich.')
    return record


def _assignment_profile(basis,period,case,running):
    if period['source_ref']!=reference(case):
        return ordinary._assignment_profile(basis,period)
    if basis['sources']['current_calculation_case']!=case:
        raise Problem(409,'Die Zuordnungsperiode gehört nicht zum tatsächlichen Faktor-Originalfall.')
    choices=[item for index,item in enumerate(running['period_details']['social_assessments'])
        if period['part_key']=='social:'+str(index) and item['period']['start']==period['start'] and item['period']['end']==period['end']]
    if len(choices)!=1:raise Problem(409,'Eindeutigen ursprünglichen Faktor-SV-Abschnitt verwenden.')
    profile=next(item for item in case['sources']['profiles'] if reference(item)==choices[0]['period']['profile_ref'])
    if normalize_factor_profile(profile['profile'])!=profile['profile']:
        raise Problem(409,'Unverändertes ursprüngliches Faktorprofil für die SV-Zuordnung verwenden.')
    return profile['profile'],ordinary._social_profile(profile['profile'],reference(profile),period['end'][:7])


def calculate_source(snapshot,*,rule_version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION):
    if rule_version!=RULE_VERSION or type(source_contract_version) is not int or source_contract_version!=SOURCE_CONTRACT_VERSION:
        raise Problem(400,'Ausdrückliche Faktor-Einmalbezugsregel und Quellenvertragsversion verwenden.')
    ordinary._shape(snapshot,'schema_version source_contract_version rule_version employee_id month running_calculation_case one_off_earning current_annual_basis previous_annual_basis annual_tax_forecast')
    if (type(snapshot['schema_version']) is not int or snapshot['schema_version']!=1 or snapshot['rule_version']!=RULE_VERSION
            or type(snapshot['source_contract_version']) is not int or snapshot['source_contract_version']!=source_contract_version):
        raise Problem(400,'Eindeutigen neuen Faktor-Einmalbezugsquellenstand verwenden.')
    employee_id=snapshot['employee_id'];month=snapshot['month'];first,last=month_range(month)
    case=snapshot['running_calculation_case']
    if (first.year!=2026 or case['employee_id']!=employee_id or case['kind']!='calculation_case'
            or case['status']!='active' or case['details']['month']!=month or case['rule_version']!=factor.RULE_VERSION
            or case['source_contract_version']!=factor.SOURCE_CONTRACT_VERSION or factor.build_plan(case['sources'])!=case['plan']):
        raise Problem(409,'Unveränderten tatsächlichen eigenen Faktor-/P4-Monatsfall binden.')
    running=factor.calculate_source(case['sources'])
    earning=_annual(snapshot['one_off_earning'],'one_off_earning',employee_id,version=ANNUAL_BASIS_VERSION)
    current=_annual(snapshot['current_annual_basis'],'annual_basis',employee_id,version=ANNUAL_V2)
    forecast=_annual(snapshot['annual_tax_forecast'],'annual_tax_forecast',employee_id,version=ANNUAL_V2)
    previous=snapshot['previous_annual_basis']
    if previous is not None:previous=_annual(previous,'annual_basis',employee_id,version=ANNUAL_BASIS_VERSION)
    receipt=earning['details']['planned_receipt_date'];amount=earning['details']['amount_minor'];section=earning['details']['section_key']
    company=employer_key(current['sources']['identity'])
    if (receipt[:7]!=month or current['details']['year']!=2026 or current['details']['coverage_to']!=last.isoformat()
            or current['details']['as_of_date']!=receipt or current['sources']['current_calculation_case']!=case
            or current['details']['current_calculation_case_ref']!=reference(case) or forecast['sources']['annual_basis']!=current
            or forecast['sources']['current_one_off']!=earning or forecast['details']['annual_basis_ref']!=reference(current)
            or forecast['details']['current_one_off_ref']!=reference(earning) or forecast['details']['receipt_date']!=receipt):
        raise Problem(409,'Faktorfall, Anspruch, Jahresbasis und Steuerprognose benötigen denselben tatsächlichen Zufluss.')
    if any(employer_key(record['sources']['identity'])!=company for record in [earning,current,forecast]+([previous] if previous else [])):
        raise Problem(409,'Einmalbezug verbindet verschiedene tatsächliche Arbeitgeberidentitäten.')
    if previous and (previous['details']['year']!=2025 or previous['details']['coverage_to']!='2025-12-31' or previous['details']['as_of_date']!=receipt):
        raise Problem(409,'Die Märzklausel benötigt ihr vollständiges tatsächliches Vorjahr zum selben Zuflussstichtag.')
    projections=[item for item in current['sources']['internal_periods'] if item['source_ref']==reference(case)]
    if running['payroll_calculation_complete'] and projections!=[ordinary._current_projection(case,running)]:
        raise Problem(409,'Die aktuelle Jahresperiode ist nicht exakt aus der ursprünglichen Faktor-Rechnung hergeleitet.')
    ordinary._claim_section(earning)
    blockers=list(running['blockers'])
    def block(code,message):
        if not any(item['code']==code for item in blockers):blockers.append(dict(code=code,message=message))
    if running['scope']!='regular_standard_factor_claims_month' or section!='regular':
        block('factor_oneoff_status_required','Dieser Faktor-Einmalbezug benötigt den vollständigen regulären P4-Monat.')
    if any(item['section_key']!=section for basis in [current]+([previous] if previous else []) for item in basis['plan']['projection']['periods']):
        block('mixed_oneoff_sections_required','Gemischte Beschäftigungsabschnitte benötigen ihre eigene nachgewiesene Zuordnung.')
    identity=forecast['sources']['tax_identity'];tax_record=identity['sources']['profile'];profile=tax_record['profile']
    if (normalize_factor_profile(profile)!=profile or tax_record['employee_id']!=employee_id or employer_key(identity)!=company
            or not identity['details']['valid_from']<=last.isoformat()<=identity['details']['valid_to']
            or reference(tax_record)!=reference(case['sources']['profiles'][0])):
        raise Problem(409,'Das tatsächliche unveränderte Faktorprofil muss am Ende des Zuflussmonats gelten.')
    for issue in ordinary._profile_blockers(profile,None,first,last):
        if issue['code']!='special_case:tax_factor':block(issue['code'],issue['message'])
    if forecast['plan']['annual_allowance_minor'] or forecast['plan']['annual_addition_minor']:
        block('factor_oneoff_allowances_required','Zusätzliche jährliche ELStAM-Frei-/Hinzurechnungsbeträge benötigen ihren eigenen Faktorregelzweig.')
    period=ordinary._last_period(current,section,receipt);prior_period=ordinary._last_period(previous,section,receipt) if previous else None
    room=ordinary._room(current,period,section);prior_room=ordinary._room(previous,prior_period,section) if previous else None
    mandatory=profile['health_insurance']=='statutory_mandatory'
    available=room['branches']['health' if mandatory else 'pension']['room_minor'] if room else 0
    if int(month[-2:])<=3 and amount>available and previous is None:
        block('previous_year_evidence_required','Eine mögliche Märzklausel benötigt das vollständig belegte Vorjahr.')
    result=deepcopy(running)
    result.update(rule_version=RULE_VERSION,rules_sha256=RULES_SHA256,source_contract_version=SOURCE_CONTRACT_VERSION,
        scope='unsupported',payroll_calculation_complete=False,social_contributions_available=False,
        gross_minor=None if running['gross_minor'] is None else running['gross_minor']+amount,blockers=blockers,running_calculation=running,
        one_off_details=dict(source_snapshot_hash=sha(snapshot),receipt_date=receipt,earning_ref=reference(earning),amount_minor=amount,
            current_annual_basis_ref=reference(current),previous_annual_basis_ref=reference(previous) if previous else None,
            annual_tax_forecast_ref=reference(forecast),actual_payment_created=False))
    for key in ordinary.MONEY_FIELDS:result[key]=None
    if blockers:return result
    assignment=select_one_off_assignment(receipt_date=receipt,amount_minor=amount,current_room=room,previous_room=prior_room,
        current_period_ref=period['source_ref'] if period else None,previous_period_ref=prior_period['source_ref'] if prior_period else None,
        mandatory_statutory_health=mandatory,previous_year_employment=prior_period is not None)
    selected_period=prior_period if assignment['march_clause'] else period;selected_basis=previous if assignment['march_clause'] else current
    if selected_period is None:
        block('oneoff_assignment_period_required','Der Faktor-Einmalbezug benötigt eine tatsächliche SV-Zuordnungsperiode.');return result
    selected_profile,social_profile=_assignment_profile(selected_basis,selected_period,case,running)
    scheme=selected_profile.get('scheme','regular_transition' if 'transition_assessment' in selected_profile else 'commercial_minijob' if selected_profile.get('employment_kind')=='minijob' else 'regular_standard')
    if scheme!='regular_standard' or selected_profile['health_insurance']!='statutory_mandatory':
        block('historical_oneoff_status_source_required','Die ursprüngliche SV-Zuordnung benötigt ihren eigenen Versicherungs-/Übergangsbereichsvertrag.');return result
    social=calculate_regular_one_off_contributions(assignment=assignment,profile=social_profile)
    tax_social=ordinary._social_profile(profile,reference(tax_record),month)
    tax=calculate_factor_one_off_tax(annual_pay_before_minor=forecast['plan']['annual_pay_before_minor'],one_off_minor=amount,
        tax_class=profile['tax_class'],factor=profile['tax_factor'],children_half_units=profile['tax_children_half_units'],
        additional_health_percent=format(Decimal(profile['health_additional_percent']),'.2f'),saxony=tax_social['saxony'],
        childless_surcharge=tax_social['childless_surcharge'],care_child_discounts=tax_social['care_child_discounts'],
        church_member=profile['church_tax']!='none',annual_allowance_minor=forecast['plan']['annual_allowance_minor'],annual_addition_minor=forecast['plan']['annual_addition_minor'])
    rate=0 if profile['church_tax']=='none' else 8 if profile['federal_state'] in ('BW','BY') else 9;church=tax['BKS']*rate//100
    for key in ('employee_contributions','employer_contributions','employer_levies'):
        result[key]={name:value+social[key][name] for name,value in running[key].items()}
    for key,extra in (('individual_wage_tax_minor',tax['STS']),('solidarity_minor',tax['SOLZS']),('church_tax_minor',church)):
        result[key]=running[key]+extra
    result['employee_social_total_minor']=sum(result['employee_contributions'].values());result['employer_social_total_minor']=sum(result['employer_contributions'].values())
    result['employee_tax_minor']=result['individual_wage_tax_minor']+result['solidarity_minor']+result['church_tax_minor']
    result['net_minor']=result['gross_minor']-result['employee_social_total_minor']-result['employee_tax_minor'];result['net_deductions_minor']=running['net_deductions_minor']
    cash=result['net_minor']-result['net_deductions_minor']
    result.update(scope='regular_standard_factor_claims_oneoff',payroll_calculation_complete=True,social_contributions_available=True,
        employer_flat_tax_minor=running['employer_flat_tax_minor'],employer_total_excluding_accident_insurance_minor=running['employer_total_excluding_accident_insurance_minor']+amount+social['employer_total_minor']+sum(social['employer_levies'].values()),
        payout_minor=max(0,cash),employee_additional_payment_minor=max(0,-cash),tax_method='individual_2026_verified_factor_running_and_other_payment_pap')
    result['one_off_details'].update(assignment=assignment,assigned_part_key=selected_period['part_key'],social=social,tax=tax,
        church_tax_percent=rate,church_tax_minor=church,tax_profile_ref=reference(tax_record),annual_pay_before_minor=forecast['plan']['annual_pay_before_minor'],tax_factor=profile['tax_factor'])
    return result


def calculation_matches(snapshot,calculated,original):
    """Reproduce only trusted LF/CRLF SV metadata; compare every money field."""
    if calculated==original:return True
    if (not isinstance(original,dict) or original.get('rule_version')!=RULE_VERSION
            or calculated.get('rule_version')!=RULE_VERSION):return False
    from oneoff_provenance_compat import _trusted_variants,_rooms
    from payroll_oneoff_2026 import select_one_off_assignment
    for contribution_hash in {value[0] for value in _trusted_variants()}:
        rules_hash=sha(dict(RULES,social_hash=contribution_hash))
        if original.get('rules_sha256')!=rules_hash:continue
        candidate=deepcopy(calculated);candidate['rules_sha256']=rules_hash;details=candidate['one_off_details']
        if 'assignment' in details:
            current_period,previous_period,current_room,previous_room=_rooms(snapshot,details['receipt_date'],contribution_hash)
            tax_profile=snapshot['annual_tax_forecast']['sources']['tax_identity']['sources']['profile']['profile']
            assignment=select_one_off_assignment(receipt_date=details['receipt_date'],amount_minor=details['amount_minor'],
                current_room=current_room,previous_room=previous_room,
                current_period_ref=current_period['source_ref'] if current_period else None,
                previous_period_ref=previous_period['source_ref'] if previous_period else None,
                mandatory_statutory_health=tax_profile['health_insurance']=='statutory_mandatory',
                previous_year_employment=previous_period is not None)
            if {k:v for k,v in assignment.items() if k!='source_hash'}!={k:v for k,v in details['assignment'].items() if k!='source_hash'}:continue
            details['assignment']=assignment
            if 'social' in details:
                period=previous_period if assignment['march_clause'] else current_period
                basis=snapshot['previous_annual_basis'] if assignment['march_clause'] else snapshot['current_annual_basis']
                _,profile=_assignment_profile(basis,period,snapshot['running_calculation_case'],calculated['running_calculation'])
                details['social'].update(rules_hash=contribution_hash,assignment=assignment,source_hash=sha(dict(assignment=assignment,profile=profile)))
        if candidate==original:return True
    return False
