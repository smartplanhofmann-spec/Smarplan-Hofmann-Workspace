"""New factor/full-month source composition; all historical kernels unchanged."""
from copy import deepcopy
import hashlib
from pathlib import Path
import re

from core import Problem, canonical
from business_payroll_facts import reference, ref
from payroll_de_2026 import month_range
from payroll_factor_2026 import calculate_factor
from payroll_factor_periods_2026 import build_factor_period_plan, calculate_factor_period_source, FACTOR_PERIOD_RULE_VERSION
from payroll_calculations_2026 import _travel_totals

RULE_VERSION = 'de_2026_factor_taxfree_travel_month_v10'
SOURCE_CONTRACT_VERSION = 2
SCOPE = 'regular_standard_factor_taxfree_travel_month'
FEATURE = 'payroll_factor_taxfree_travel'
_ROOT = Path(__file__).resolve().parent
RULES = dict(version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
             supported_case='ONE_V9_FULL_MONTH_FACTOR_PROFILE_ONLY_FULLY_PAID_TAXFREE_EXTERNAL_TRAVEL',
             travel_payment='NO_ADDITION_TO_WAGE_GROSS_OR_NET',
             sources={name: hashlib.sha256((_ROOT/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                      for name in ('payroll_factor_2026.py', 'payroll_factor_periods_2026.py',
                                   'payroll_factor_taxfree_sources.py')},
             module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
             official_system_approval=False)
RULES_SHA256 = hashlib.sha256(canonical(RULES).encode()).hexdigest()
AMOUNTS = ('gross_minor', 'employee_contributions', 'employer_contributions', 'employee_social_total_minor',
           'employer_social_total_minor', 'employer_levies', 'employer_flat_tax_minor',
           'employer_total_excluding_accident_insurance_minor', 'individual_wage_tax_minor',
           'solidarity_minor', 'church_tax_minor', 'employee_tax_minor', 'net_minor', 'payout_minor',
           'employee_additional_payment_minor')


def build_plan(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    keys = {'schema_version', 'source_contract_version', 'rule_version', 'employee_id', 'month', 'period_case',
            'employment_terms', 'profiles', 'identities', 'segment_events', 'thirty_day_rule', 'entitlements',
            'travel_sources', 'flat_travel_tax', 'source_files'}
    if (not isinstance(snapshot, dict) or set(snapshot) != keys or type(snapshot['schema_version']) is not int
            or snapshot['schema_version'] != 1 or rule_version != RULE_VERSION or snapshot['rule_version'] != RULE_VERSION
            or type(source_contract_version) is not int or source_contract_version != SOURCE_CONTRACT_VERSION
            or type(snapshot['source_contract_version']) is not int
            or snapshot['source_contract_version'] != SOURCE_CONTRACT_VERSION):
        raise Problem(400, 'Expliziten neuen Faktor-/Reise-Quellenvertrag verwenden.')
    base = snapshot['period_case']; original = base['sources']
    if (base['kind'] != 'period_case' or base['status'] != 'active' or base['employee_id'] != snapshot['employee_id']
            or base['plan']['rule_version'] != FACTOR_PERIOD_RULE_VERSION or base['details']['month'] != snapshot['month']):
        raise Problem(400, 'Unveränderten eigenen v9-Faktorperiodenfall desselben Monats binden.')
    ordinary = build_factor_period_plan(original)
    if ordinary != base['plan']:
        raise Problem(409, 'Ursprünglicher Faktorperiodenplan stimmt nicht mit seinen Originalen überein.')
    if (snapshot['employment_terms'] != [original['employment_terms']] or snapshot['profiles'] != original['profiles']
            or snapshot['identities'] != original['identities']):
        raise Problem(409, 'Beschäftigung, Profil und Identität müssen aus demselben ursprünglichen Faktorfall stammen.')
    blockers = list(ordinary['blockers'])
    def block(code, message):
        if not any(row['code'] == code for row in blockers): blockers.append(dict(code=code, message=message))
    first, last = month_range(snapshot['month'])
    if (len(snapshot['profiles']) != 1 or len(snapshot['identities']) != 1 or len(ordinary['employment_intervals']) != 1
            or len(ordinary['tax_periods']) != 1 or len(ordinary['social_periods']) != 1
            or ordinary['tax_periods'][0]['lzz'] != 2 or not ordinary['social_periods'][0]['full_month']):
        block('factor_travel_full_month_required', 'Dieser Quellenvertrag benötigt genau einen unveränderten vollen Faktor-Monat.')
    if (snapshot['segment_events'] or snapshot['entitlements'] or snapshot['thirty_day_rule'] is not None
            or snapshot['flat_travel_tax'] is not None):
        block('factor_travel_other_case', 'Ansprüche, Profilwechsel und Pauschalsteuer benötigen ihren eigenen Faktorregelzweig.')
    if not snapshot['travel_sources']:
        block('factor_travel_original_missing', 'Mindestens eine vollständig erstattete steuerfreie Originalreise binden.')
    travel = _travel_totals(snapshot['travel_sources'], snapshot['employee_id'], snapshot['month'])
    payment_refs=[];all_payment_ids=set()
    for source in snapshot['travel_sources']:
        ref(source['settlement_ref'])
        proof = source.get('payment_proof', {})
        if (not isinstance(proof,dict) or set(proof) != {'schema_version', 'cutoff_sequence', 'paid_minor', 'payments'}
                or type(proof['schema_version']) is not int or proof['schema_version'] != 1
                or type(proof['paid_minor']) is not int or not isinstance(proof['payments'],list)
                or not proof['payments'] or proof['paid_minor'] != source['tax_free_external_minor']
                or source['tax_free_external_minor'] <= 0 or source['allocations'] or source['letter_m']
                or any(source[key] for key in ('flat_taxable_payroll_minor', 'individual_taxable_payroll_minor', 'benefit_in_kind_non_cash_minor'))):
            block('factor_travel_paid_taxfree_required', 'Nur vollständig ausgezahlte steuerfreie Reiseoriginale ohne weiteren Lohnbestandteil sind zugelassen.')
            continue
        paid=0;seen=set();sequences=set()
        if type(proof['cutoff_sequence']) is not int or proof['cutoff_sequence']<1:
            raise Problem(400,'Gültige ursprüngliche Zahlungsjournalgrenze erforderlich.')
        for payment in proof['payments']:
            fields={'id','revision','content_hash','sequence','status','kind','paid_on','amount_minor','cash_source_hash'}
            if (not isinstance(payment,dict) or set(payment)!=fields or payment['id'] in seen or payment['id'] in all_payment_ids
                    or payment['status'] not in ('active','void') or payment['kind'] not in ('reimbursement','repayment')
                    or type(payment['amount_minor']) is not int or payment['amount_minor']<=0
                    or type(payment['sequence']) is not int or not 1<=payment['sequence']<=proof['cutoff_sequence']
                    or payment['sequence'] in sequences or not isinstance(payment['paid_on'],str)
                    or not payment['paid_on'].startswith(snapshot['month']+'-')):
                raise Problem(400,'Eindeutige ursprüngliche Zahlungsbelege für den Lohnmonat erforderlich.')
            if not re.fullmatch('[a-f0-9]{64}',str(payment['cash_source_hash'])):
                raise Problem(400,'Unveränderten Reisegeldfluss nachweisen.')
            payment_refs.append(ref(reference(payment)))
            all_payment_ids.add(payment['id'])
            seen.add(payment['id']);sequences.add(payment['sequence'])
            if payment['status']=='active':paid+=payment['amount_minor']*(1 if payment['kind']=='reimbursement' else -1)
        if paid!=proof['paid_minor'] or max(sequences)!=proof['cutoff_sequence']:
            raise Problem(409,'Der Zahlungspräfix bestätigt die vollständig erstattete Reisesumme nicht.')
    profile_ref, identity_ref = ordinary['selected_profile_ref'], ordinary['selected_identity_ref']
    earnings = [dict(row, start=first.isoformat(), end=last.isoformat(), claim_dates=[]) for row in ordinary['earnings']]
    tax_periods=[dict(row,profile_ref=profile_ref,gross_minor=ordinary['gross_minor']) for row in ordinary['tax_periods']]
    social_periods=[dict(row,profile_ref=profile_ref,gross_minor=ordinary['gross_minor']) for row in ordinary['social_periods']]
    plan = dict(schema_version=1, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
                rules_sha256=RULES_SHA256, source_snapshot_hash=hashlib.sha256(canonical(snapshot).encode()).hexdigest(),
                claims_component_hash=hashlib.sha256(canonical([]).encode()).hexdigest(), employee_id=snapshot['employee_id'],
                month=snapshot['month'], employment_intervals=ordinary['employment_intervals'],
                identity_intervals=[dict(start=first.isoformat(), end=last.isoformat(), profile_ref=profile_ref, identity_ref=identity_ref)],
                earnings=earnings, tax_periods=tax_periods, social_periods=social_periods,
                entitlement_sources=[], unpaid_dates=[], social_continuation=[], travel=travel, flat_travel_tax=None,
                travel_source_hashes=[row['source_hash'] for row in snapshot['travel_sources']], gross_minor=ordinary['gross_minor'],
                travel_payment_refs=sorted(payment_refs, key=lambda value:value['id']),
                travel_paid_minor=travel['tax_free_external_minor'],
                factor_parameters=ordinary['factor_parameters'], selected_profile_ref=profile_ref,
                blockers=sorted(blockers, key=lambda row:row['code']))
    plan['plan_hash'] = hashlib.sha256(canonical(plan).encode()).hexdigest()
    return dict(plan, can_confirm=True, can_calculate=not blockers)


def calculate_source(snapshot, *, rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION):
    plan = build_plan(snapshot, rule_version=rule_version, source_contract_version=source_contract_version)
    result = deepcopy(calculate_factor_period_source(snapshot['period_case']['sources']))
    if not plan['blockers']:
        profile = snapshot['profiles'][0]['profile']
        monthly = calculate_factor(profile, snapshot['month'], plan['gross_minor'], full_month_confirmed=True)
        if not monthly['payroll_calculation_complete'] or any(result[key] != monthly[key] for key in AMOUNTS):
            raise Problem(409, 'Faktor-Vollmonat und ursprünglicher v9-Nachweis stimmen nicht centgenau überein.')
    result.update(rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION, rules_sha256=RULES_SHA256,
                  scope=SCOPE if not plan['blockers'] else 'unsupported', blockers=plan['blockers'],
                  payroll_calculation_complete=not plan['blockers'], travel_expenses_included_in_net=False, net_deductions_minor=0)
    if plan['blockers']:
        for key in AMOUNTS:
            if key != 'gross_minor': result[key] = None
        result['social_contributions_available'] = False
    original_details = result['period_details']
    original_tax = original_details.get('tax_calculation')
    result['period_details'] = {key:plan[key] for key in ('plan_hash', 'source_snapshot_hash', 'employment_intervals',
        'identity_intervals', 'earnings', 'tax_periods', 'social_periods', 'entitlement_sources', 'unpaid_dates',
        'social_continuation', 'travel', 'flat_travel_tax', 'travel_source_hashes', 'factor_parameters',
        'travel_payment_refs', 'travel_paid_minor')}
    result['period_details']['tax_calculation'] = original_tax
    result['period_details']['tax_calculations'] = [] if plan['blockers'] else [dict(period=plan['tax_periods'][0],
        calculation=original_tax, church_tax_percent=result['tax_parameters']['church_tax_percent'],
        church_tax_minor=result['church_tax_minor'])]
    result['period_details']['social_assessments'] = [] if plan['blockers'] else [dict(period=plan['social_periods'][0],
        branch_bases=original_details['branch_bases'], transition=None, care_adjustments=original_details['care_adjustments'],
        employee_contributions=result['employee_contributions'], employer_contributions=result['employer_contributions'],
        employer_levies=result['employer_levies'], levy_assessment_minor=min(plan['gross_minor'],plan['social_periods'][0]['caps']['pension_minor']))]
    if plan['blockers']: result['net_deductions_minor'] = None
    return result
