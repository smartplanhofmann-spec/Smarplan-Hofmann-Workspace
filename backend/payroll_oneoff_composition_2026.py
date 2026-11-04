"""Explicit v6 composition from v5 wages and canonical annual source records.

This development component is not a payroll dispatcher registration. Database
source authority and freshness belong to the private source resolver. No client
may supply annual sums, selected rates or ready-made contribution room here.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib

from core import Problem, canonical
from payroll_calculations_2026 import (
    CALCULATION_RULE_VERSION as RUNNING_RULE_VERSION,
    RULES_SHA256 as RUNNING_RULE_HASH,
    build_calculation_plan, calculate_calculation_source)
from payroll_de_2026 import day, month_range, _age_completed, normalize_profile
from payroll_periods_2026 import _profile_blockers
from payroll_annual_basis_2026 import (
    ANNUAL_BASIS_VERSION, build_annual_plan, normalize_details,
    employer_key, reference, dates)
from payroll_oneoff_2026 import (
    BRANCHES, SOCIAL_ONEOFF_VERSION, SOCIAL_ONEOFF_HASH, annual_social_room,
    select_one_off_assignment, calculate_regular_one_off_contributions, _shape)
from payroll_pap_oneoff_2026 import (
    ONEOFF_PAP_VERSION, ONEOFF_PAP_HASH, calculate_standard_one_off_tax)

ONEOFF_RULE_VERSION = 'de_2026_oneoff_composition_v6'
SOURCE_CONTRACT_VERSION = 1
SOURCE_SCHEMA_VERSION = 4
RULES = dict(version=ONEOFF_RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
    running_rule_version=RUNNING_RULE_VERSION, running_rule_hash=RUNNING_RULE_HASH,
    annual_basis_version=ANNUAL_BASIS_VERSION, social_version=SOCIAL_ONEOFF_VERSION,
    social_hash=SOCIAL_ONEOFF_HASH, pap_version=ONEOFF_PAP_VERSION, pap_hash=ONEOFF_PAP_HASH,
    tax_receipt_year=2026, historical_assignment_rates=True,
    additional_gross_not_in_running_pap=True, actual_payment_created=False)
RULES_SHA256 = hashlib.sha256(canonical(RULES).encode()).hexdigest()
MONEY_FIELDS = ('employee_contributions', 'employer_contributions',
    'employee_social_total_minor', 'employer_social_total_minor', 'employer_levies',
    'employer_flat_tax_minor', 'employer_total_excluding_accident_insurance_minor',
    'individual_wage_tax_minor', 'solidarity_minor', 'church_tax_minor',
    'employee_tax_minor', 'net_minor', 'net_deductions_minor', 'payout_minor',
    'employee_additional_payment_minor')


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _annual(record, kind, employee_id):
    if (not isinstance(record, dict) or record.get('employee_id') != employee_id
            or record.get('kind') != kind or record.get('status') != 'active'
            or record.get('plan', {}).get('rule_version') != ANNUAL_BASIS_VERSION):
        raise Problem(409, 'Aktive kanonische Jahresquelle derselben Person erforderlich.')
    normalized = normalize_details(kind, record['details'])
    if (normalized != record['details'] or record['sources']['details'] != normalized
            or record['sources']['kind'] != kind
            or record['sources']['employee']['id'] != employee_id
            or build_annual_plan(record['sources'], rule_version=record['plan']['rule_version']) != record['plan']):
        raise Problem(409, 'Jahresquelle und erneut hergeleiteter Originalplan widersprechen sich.')
    return record


def _social_profile(profile, ref, month):
    if profile.get('scheme') is not None:
        return dict(source_ref=ref, **{key: profile[key] for key in
            ('health_additional_percent', 'saxony', 'childless_surcharge', 'care_child_discounts')})
    born = day(profile['date_of_birth'])
    return dict(source_ref=ref, health_additional_percent=profile['health_additional_percent'],
        saxony=profile['federal_state'] == 'SN',
        childless_surcharge=not profile['has_children'] and _age_completed(born, 23).strftime('%Y-%m') < month,
        care_child_discounts=max(0, min(5, profile['pv_children_under_25']) - 1))


def _last_period(basis, section, receipt_date):
    periods = [value for value in basis['plan']['projection']['periods']
        if value['section_key'] == section and value['end'][:7] <= receipt_date[:7]]
    return max(periods, key=lambda value: (value['end'], value['start'])) if periods else None


def _room(basis, period, section):
    if period is None:
        return None
    return annual_social_room(dict(basis['plan']['projection'], source_ref=reference(basis)),
        through=period['end'], section_key=section)


def _assignment_profile(basis, period):
    """Select exact historical profile from the bound actual period, no defaults."""
    source = basis['sources']; ref = period['source_ref']
    for imported in source['imported_periods']:
        if reference(imported) == ref:
            _annual(imported, 'imported_period', basis['employee_id'])
            if period['part_key'] != 'imported':
                raise Problem(409, 'Importperiode besitzt keinen solchen Versicherungsabschnitt.')
            p = imported['details']['profile']
            return p, _social_profile(p, reference(imported), period['end'][:7])
    candidate = source['current_calculation_case']
    records = source['payroll_runs']
    if candidate is not None and reference(candidate) == ref:
        case = candidate
    else:
        runs = [item for item in records if reference(item) == ref]
        if len(runs) != 1:
            raise Problem(409, 'Zuordnungsperiode fehlt in den tatsächlichen Jahresoriginalen.')
        run = runs[0]
        if run['source'].get('source_schema_version') == 4:
            if run.get('projection_format')!='source4_annual_reference_v1':
                raise Problem(409,'Unbekannte interne Jahresprojektion des Einmalbezugs.')
            projections=[item for item in source['internal_periods'] if item['source_ref']==ref]
            choices=[item for projection in projections for item in projection['assignment_profiles']
                if item['part_key']==period['part_key'] and item['start']==period['start'] and item['end']==period['end']]
            if len(choices)!=1:raise Problem(409,'Das ursprüngliche historische SV-Profil der internen Periode fehlt.')
            selected=choices[0];p=selected['profile']
            if normalize_profile(p)!=p:raise Problem(409,'Das ursprüngliche SV-Profil ist nicht normiert.')
            return p,_social_profile(p,selected['profile_ref'],period['end'][:7])
        if run['source'].get('source_schema_version') != 3:
            p = run['source']['profile']['profile']
            return p, _social_profile(p, reference(run['source']['profile']), period['end'][:7])
        case = run['source']['calculation_case']
    running = calculate_calculation_source(case['sources'], rule_version=case['rule_version'],
        source_contract_version=case['source_contract_version'])
    assessments = running['period_details'].get('social_assessments', [])
    choices = [value for index, value in enumerate(assessments)
        if period['part_key'] == 'social:' + str(index)
        and value['period']['start'] == period['start'] and value['period']['end'] == period['end']]
    if len(choices) != 1:
        raise Problem(409, 'Zuordnungsabschnitt ist nicht aus der Originalrechnung herleitbar.')
    selected = next(value for value in case['sources']['profiles']
        if reference(value) == choices[0]['period']['profile_ref'])
    return selected['profile'], _social_profile(selected['profile'], reference(selected), period['end'][:7])


def _claim_section(earning):
    """Check the actual agreements for each claim day, not a free section label."""
    section = earning['details']['section_key']
    terms = earning['sources']['employment_terms']
    for period in earning['details']['claim_periods']:
        for current in dates(period['start'], period['end']):
            active = [term for term in terms if term['details']['employment_from'] <= current
                <= (term['details']['employment_to'] or '9999-12-31')]
            if len(active) != 1:
                raise Problem(409, 'Anspruchstag benötigt genau seinen belegten Beschäftigungsvertrag.')
            agreements = [value for value in active[0]['sources']['agreements'] if value['effective_from'] <= current]
            if not agreements:
                raise Problem(409, 'Anspruchstag hat keine tatsächliche Entgeltvereinbarung.')
            agreement = max(agreements, key=lambda value: value['effective_from'])
            expected = 'minijob' if agreement['employment_kind'] == 'minijob' else 'regular'
            if expected != section:
                raise Problem(409, 'Anspruchsabschnitt widerspricht seiner ursprünglichen Beschäftigungsart.')


def _current_projection(case, running):
    """Reconstruct the planned annual period from the same v5 calculation."""
    first, last = month_range(case['details']['month']); ref = reference(case)
    profiles = {canonical(reference(value)): value['profile'] for value in case['sources']['profiles']}
    details = running['period_details']; periods = []; minis = []
    for index, assessment in enumerate(details.get('social_assessments', [])):
        period = assessment['period']; p = profiles[canonical(period['profile_ref'])]
        mini = p['employment_kind'] == 'minijob'; minis.append(mini); branches = {}
        for branch in BRANCHES:
            active = not mini or branch not in ('care', 'unemployment')
            if branch in ('health', 'care') and p['health_insurance'] == 'private': active = False
            bases = assessment['branch_bases']; groups = []
            if not active: contributed = 0
            elif bases: contributed = bases['health_general' if branch == 'health' else branch]['total_minor']
            else:
                cap = period['caps']['health_minor' if branch in ('health', 'care') else 'pension_minor']
                contributed = min(period['gross_minor'], cap)
            if active:
                continuation = {value['date'] for value in details['social_continuation']}
                for current in dates(period['start'], period['end']):
                    reason = 'continued_section_7_3' if current in continuation else 'paid_employment'
                    if groups and groups[-1]['legal_reason'] == reason: groups[-1]['end'] = current
                    else: groups.append(dict(start=current, end=current, legal_reason=reason, source_ref=ref))
            branches[branch] = dict(eligible_intervals=groups, contributed_minor=contributed)
        periods.append(dict(source_ref=ref, part_key='social:' + str(index), section_key='minijob' if mini else 'regular',
            start=period['start'], end=period['end'], branches=branches))
    taxable = 0 if all(minis) else sum(value['gross_minor'] for value in details['tax_periods'])
    return dict(source_ref=ref, coverage_start=first.isoformat(), coverage_end=last.isoformat(),
        periods=periods, running_taxable_minor=taxable, tax_receipt_status='planned_current_period', payment_evidence=None)


def calculate_oneoff_source(snapshot, *, rule_version, source_contract_version):
    if (rule_version != ONEOFF_RULE_VERSION or type(source_contract_version) is not int
            or source_contract_version != SOURCE_CONTRACT_VERSION):
        raise Problem(400, 'Unbekannte explizite Einmalbezugsregel oder Quellenvertragsversion.')
    _shape(snapshot, 'schema_version source_contract_version rule_version employee_id month '
        'running_calculation_case one_off_earning current_annual_basis previous_annual_basis annual_tax_forecast')
    if (type(snapshot['schema_version']) is not int or snapshot['schema_version'] != 1
            or type(snapshot['source_contract_version']) is not int
            or snapshot['source_contract_version'] != source_contract_version
            or snapshot['rule_version'] != rule_version):
        raise Problem(400, 'Vollständigen explizit versionierten Einmalbezugsquellenstand angeben.')
    employee_id = snapshot['employee_id']; month = snapshot['month']; first, last = month_range(month)
    if first.year != 2026:
        raise Problem(400, 'Diese Zusammensetzung verarbeitet Zuflüsse 2026.')
    case = snapshot['running_calculation_case']
    if (case['employee_id'] != employee_id or case['kind'] != 'calculation_case'
            or case['status'] != 'active' or case['details']['month'] != month
            or case['rule_version'] != RUNNING_RULE_VERSION
            or case['plan'] != build_calculation_plan(case['sources'], rule_version=case['rule_version'],
                source_contract_version=case['source_contract_version'])):
        raise Problem(409, 'Laufender Originalfall gehört nicht unverändert zu Person und Monat.')
    running = calculate_calculation_source(case['sources'], rule_version=case['rule_version'],
        source_contract_version=case['source_contract_version'])
    earning = _annual(snapshot['one_off_earning'], 'one_off_earning', employee_id)
    current = _annual(snapshot['current_annual_basis'], 'annual_basis', employee_id)
    forecast = _annual(snapshot['annual_tax_forecast'], 'annual_tax_forecast', employee_id)
    previous = snapshot['previous_annual_basis']
    if previous is not None:
        previous = _annual(previous, 'annual_basis', employee_id)
    receipt = earning['details']['planned_receipt_date']; amount = earning['details']['amount_minor']
    section = earning['details']['section_key']; company = employer_key(current['sources']['identity'])
    if (receipt[:7] != month or current['details']['year'] != 2026
            or current['details']['coverage_to'] != last.isoformat()
            or current['details']['as_of_date'] != receipt
            or current['sources']['current_calculation_case'] != case
            or current['details']['current_calculation_case_ref'] != reference(case)
            or forecast['sources']['annual_basis'] != current
            or forecast['sources']['current_one_off'] != earning
            or forecast['details']['annual_basis_ref'] != reference(current)
            or forecast['details']['current_one_off_ref'] != reference(earning)
            or forecast['details']['receipt_date'] != receipt):
        raise Problem(409, 'Anspruch, laufende Rechnung, Jahresbasis und Steuerprognose benötigen denselben tatsächlichen Zuflussfall.')
    records = [earning, current, forecast] + ([previous] if previous else [])
    if any(employer_key(value['sources']['identity']) != company for value in records):
        raise Problem(409, 'Einmalbezug verbindet verschiedene rechtliche Arbeitgeber.')
    if previous and (previous['details']['year'] != 2025
            or previous['details']['coverage_to'] != '2025-12-31'
            or previous['details']['as_of_date'] != receipt):
        raise Problem(409, 'Märzklausel braucht das vollständig belegte Vorjahr mit demselben Zuflussstichtag.')
    current_projections = [value for value in current['sources']['internal_periods'] if value['source_ref'] == reference(case)]
    if running['payroll_calculation_complete'] and current_projections != [_current_projection(case, running)]:
        raise Problem(409, 'Aktuelle Jahresperiode muss exakt aus derselben laufenden Originalrechnung stammen.')
    _claim_section(earning)
    blockers = list(running['blockers'])

    def block(code, message):
        if not any(value['code'] == code for value in blockers):
            blockers.append(dict(code=code, message=message))

    if running['scope'] != 'regular_standard_segments' or section != 'regular':
        block('oneoff_status_source_required', 'Mini-/Midijob benötigt seine vollständige zusätzliche Prognose- und Periodenquelle.')
    if any(period['section_key'] != section for basis in [current] + ([previous] if previous else [])
            for period in basis['plan']['projection']['periods']):
        block('mixed_oneoff_sections_required', 'Wechsel zwischen geringfügigen und regulären Anspruchsabschnitten benötigt seine eigene belegte Zuordnung.')
    tax_identity = forecast['sources']['tax_identity']; tax_record = tax_identity['sources']['profile']
    tax_profile = tax_record['profile']
    if (normalize_profile(tax_profile) != tax_profile or tax_record['employee_id'] != employee_id
            or employer_key(tax_identity) != company
            or not tax_identity['details']['valid_from'] <= last.isoformat() <= tax_identity['details']['valid_to']):
        raise Problem(409, 'Steuermerkmale müssen tatsächlich am Ende des Zuflussmonats gelten.')
    for issue in _profile_blockers(tax_profile, None, first, last):
        block(issue['code'], issue['message'])
    current_period = _last_period(current, section, receipt)
    previous_period = _last_period(previous, section, receipt) if previous else None
    current_room = _room(current, current_period, section)
    previous_room = _room(previous, previous_period, section) if previous else None
    mandatory = tax_profile['health_insurance'] == 'statutory_mandatory'
    room = current_room['branches']['health' if mandatory else 'pension']['room_minor'] if current_room else 0
    if int(month[-2:]) <= 3 and amount > room and previous is None:
        block('previous_year_evidence_required', 'Mögliche Märzklausel braucht das vollständige belegte Vorjahr einschließlich ausdrücklicher Nichtbeschäftigung.')
    result = deepcopy(running)
    result.update(rule_version=rule_version, rules_sha256=RULES_SHA256,
        source_contract_version=source_contract_version, scope='unsupported',
        payroll_calculation_complete=False, social_contributions_available=False,
        gross_minor=None if running['gross_minor'] is None else running['gross_minor'] + amount,
        blockers=blockers, running_calculation=running,
        one_off_details=dict(source_snapshot_hash=sha(snapshot), receipt_date=receipt,
            earning_ref=reference(earning), amount_minor=amount, current_annual_basis_ref=reference(current),
            previous_annual_basis_ref=reference(previous) if previous else None,
            annual_tax_forecast_ref=reference(forecast), actual_payment_created=False))
    for key in MONEY_FIELDS:
        result[key] = None
    if blockers:
        return result
    assignment = select_one_off_assignment(receipt_date=receipt, amount_minor=amount,
        current_room=current_room, previous_room=previous_room,
        current_period_ref=current_period['source_ref'] if current_period else None,
        previous_period_ref=previous_period['source_ref'] if previous_period else None,
        mandatory_statutory_health=mandatory, previous_year_employment=previous_period is not None)
    selected_period = previous_period if assignment['march_clause'] else current_period
    selected_basis = previous if assignment['march_clause'] else current
    if selected_period is None:
        block('oneoff_assignment_period_required', 'Einmalbezug ohne aktuelle Zuordnungsperiode benötigt seinen eigenen vollständigen Versicherungszweig.')
        return result
    selected_profile, social_profile = _assignment_profile(selected_basis, selected_period)
    scheme = selected_profile.get('scheme', 'regular_transition' if 'transition_assessment' in selected_profile
        else 'commercial_minijob' if selected_profile.get('employment_kind') == 'minijob' else 'regular_standard')
    if scheme != 'regular_standard' or selected_profile['health_insurance'] != 'statutory_mandatory':
        block('historical_oneoff_status_source_required', 'Die tatsächliche Zuordnungsperiode benötigt ihren eigenen Versicherungs-/Übergangsbereichszweig.')
        return result
    social = calculate_regular_one_off_contributions(assignment=assignment, profile=social_profile)
    tax_social = _social_profile(tax_profile, reference(tax_record), month)
    tax = calculate_standard_one_off_tax(
        annual_pay_before_minor=forecast['plan']['annual_pay_before_minor'], one_off_minor=amount,
        tax_class=tax_profile['tax_class'], children_half_units=tax_profile['tax_children_half_units'],
        additional_health_percent=format(Decimal(tax_profile['health_additional_percent']), '.2f'),
        saxony=tax_social['saxony'], childless_surcharge=tax_social['childless_surcharge'],
        care_child_discounts=tax_social['care_child_discounts'], church_member=tax_profile['church_tax'] != 'none',
        annual_allowance_minor=forecast['plan']['annual_allowance_minor'],
        annual_addition_minor=forecast['plan']['annual_addition_minor'])
    rate = 0 if tax_profile['church_tax'] == 'none' else 8 if tax_profile['federal_state'] in ('BW', 'BY') else 9
    church = tax['BKS'] * rate // 100
    for key in ('employee_contributions', 'employer_contributions', 'employer_levies'):
        result[key] = {name: value + social[key][name] for name, value in running[key].items()}
    for target, extra in (('individual_wage_tax_minor', tax['STS']), ('solidarity_minor', tax['SOLZS']), ('church_tax_minor', church)):
        result[target] = running[target] + extra
    result['employee_social_total_minor'] = sum(result['employee_contributions'].values())
    result['employer_social_total_minor'] = sum(result['employer_contributions'].values())
    result['employee_tax_minor'] = result['individual_wage_tax_minor'] + result['solidarity_minor'] + result['church_tax_minor']
    result['net_minor'] = result['gross_minor'] - result['employee_social_total_minor'] - result['employee_tax_minor']
    result['net_deductions_minor'] = running['net_deductions_minor']
    cash = result['net_minor'] - result['net_deductions_minor']
    result.update(scope='regular_standard_oneoff', payroll_calculation_complete=True,
        social_contributions_available=True, employer_flat_tax_minor=running['employer_flat_tax_minor'],
        employer_total_excluding_accident_insurance_minor=running['employer_total_excluding_accident_insurance_minor']
            + amount + social['employer_total_minor'] + sum(social['employer_levies'].values()),
        payout_minor=max(0, cash), employee_additional_payment_minor=max(0, -cash),
        tax_method='individual_2026_verified_running_and_other_payment_pap')
    result['one_off_details'].update(assignment=assignment,
        assigned_part_key=selected_period['part_key'], social=social, tax=tax,
        church_tax_percent=rate, church_tax_minor=church,
        tax_profile_ref=reference(tax_record), annual_pay_before_minor=forecast['plan']['annual_pay_before_minor'])
    return result
