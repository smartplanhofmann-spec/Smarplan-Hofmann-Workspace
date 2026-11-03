"""Evidence-bound 25% meal reimbursement tax, separate from ordinary wage tax.

This pure component does not establish that tax was booked or transmitted.
The private case resolver must verify dates, membership, allowance capacity and
the employer's common filing-period policy against the original sources.
"""
import calendar
from datetime import date
import hashlib
import re

from core import Problem, canonical
from payroll_de_2026 import day, integer, month_range

RULE_VERSION = 'de_2026_travel_flat_tax_v1'
# Basis points of the already calculated flat wage tax; not of reimbursement.
# Regional exceptions require an explicit jurisdiction decision, never inference
# from a person's postal address. See the dated source document.
SIMPLIFIED_RATES = dict(BW=450, BY=700, BE=500, BB=500, HB=700, HH=400,
    HE=700, MV=500, NI=600, NW=700, RP=700, SL=700, SN=500, ST=500, SH=600, TH=500)
RULES = dict(version=RULE_VERSION, year=2026, wage_tax_basis_points=2500,
    solidarity_basis_points=550, simplified_church_rates=SIMPLIFIED_RATES,
    evidence_church_rates=dict(BW=800, BY=800, other=900),
    exceptions=dict(ni_ev_westfalen=700, bw_bad_wimpfen_mainz=900),
    membership_evidence=('elstam', 'substitute_tax_certificate',
        'official_employee_declaration', 'unknown_membership_general_rate'),
    unresolved_membership='DOCUMENTED_GENERAL_RATE_NOT_ZERO',
    tax_rule='ESTG_40_2_S1_N4', social_rule='SVEV_1_1_S1_N3_AND_S2',
    rounding='FLOOR_EACH_TAX_TO_CENTS',
    social_timing='ACTUAL_PAYROLL_TAX_TREATMENT_BY_CERTIFICATE_AND_NEXT_FEBRUARY_END')
RULES_SHA256 = hashlib.sha256(canonical(RULES).encode()).hexdigest()
FIELDS = frozenset(('policy_ref', 'filing_period_from', 'filing_period_to',
    'payroll_month', 'taxation_recorded_on', 'tax_certificate_issued_on',
    'eligible_limit_minor', 'eligible_source_refs', 'church_rate_region',
    'church_method_applies_to_all', 'church_membership_evidence',
    'employee_deduction_authorization'))


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _ref(value):
    if (not isinstance(value, dict) or set(value) != {'id', 'revision', 'content_hash'}
            or not isinstance(value['id'], str) or not re.fullmatch('[a-f0-9]{32}', value['id'])
            or type(value['revision']) is not int or value['revision'] < 1
            or not isinstance(value['content_hash'], str)
            or not re.fullmatch('[a-f0-9]{64}', value['content_hash'])):
        raise Problem(400, 'Eine konkrete unveränderliche Steuerentscheidungsquelle ist erforderlich.')
    return dict(value)


def _filing_period(evidence):
    first, last = day(evidence['filing_period_from']), day(evidence['filing_period_to'])
    start, end = month_range(evidence['payroll_month'])
    whole_month = first.day == 1 and last == date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    quarter = (first.day == 1 and first.month in (1, 4, 7, 10)
               and last == date(first.year, first.month+2, calendar.monthrange(first.year, first.month+2)[1]))
    year = first == date(2026, 1, 1) and last == date(2026, 12, 31)
    if first.year != 2026 or last.year != 2026 or not (whole_month or quarter or year) or not first <= start <= end <= last:
        raise Problem(400, 'Der tatsächliche Anmeldezeitraum 2026 muss den Abrechnungsmonat vollständig umfassen.')
    return first, last, start


def calculate_flat_travel_tax(amount_minor, *, federal_state, church_tax,
                              church_method, employer_bears_tax=True, evidence):
    """Return separate tax liabilities and explicitly evidenced SV treatment.

    church_method is ``simplified`` (tax for every employee) or ``evidence``
    (documented membership/non-membership). Missing legal facts return blockers;
    malformed data raises Problem400. No taxable excess is silently discarded.
    employer_total_minor is the employer's economic tax cost. The statutory
    employer liability remains statutory_employer_due_minor even if an evidenced
    wage agreement passes that economic cost to the employee.
    """
    integer(amount_minor, 0, 10**12)
    if not isinstance(federal_state, str) or federal_state not in SIMPLIFIED_RATES:
        raise Problem(400, 'Das Bundesland der lohnsteuerlichen Betriebsstätte ist erforderlich.')
    if church_method not in ('simplified', 'evidence') or church_tax is not None and type(church_tax) is not bool:
        raise Problem(400, 'Kirchensteuerverfahren und belegte Zugehörigkeit eindeutig angeben.')
    if type(employer_bears_tax) is not bool or not isinstance(evidence, dict) or set(evidence) != FIELDS:
        raise Problem(400, 'Die dokumentierte Pauschalsteuerentscheidung ist unvollständig oder unbekannt.')
    _ref(evidence['policy_ref'])
    first, last, payroll_start = _filing_period(evidence)
    limit = integer(evidence['eligible_limit_minor'], 0, 10**12)
    sources = evidence['eligible_source_refs']
    if not isinstance(sources, list) or not 1 <= len(sources) <= 100:
        raise Problem(400, 'Die pauschalierungsfähigen Reisequellen müssen konkret gebunden sein.')
    refs = [_ref(value) for value in sources]
    if len({(r['id'], r['revision']) for r in refs}) != len(refs):
        raise Problem(400, 'Eine Reisequellfassung darf nicht doppelt in der Steuerbasis stehen.')
    region = evidence['church_rate_region']
    if (region not in ('standard', 'ni_ev_westfalen', 'bw_bad_wimpfen_mainz')
            or region == 'ni_ev_westfalen' and federal_state != 'NI'
            or region == 'bw_bad_wimpfen_mainz' and federal_state != 'BW'):
        raise Problem(400, 'Die belegte Kirchensteuerzuständigkeit passt nicht zur Betriebsstätte.')
    if type(evidence['church_method_applies_to_all']) is not bool:
        raise Problem(400, 'Die einheitliche Verfahrenswahl muss ausdrücklich geprüft sein.')
    membership = evidence['church_membership_evidence']
    if membership is not None:
        if (not isinstance(membership, dict) or set(membership) != {'kind', 'reference'}
                or membership['kind'] not in RULES['membership_evidence']):
            raise Problem(400, 'Konkreten zulässigen Zugehörigkeitsnachweis oder dokumentierten allgemeinen Kirchensteuersatz angeben.')
        _ref(membership['reference'])
        if membership['kind'] == 'unknown_membership_general_rate' and church_tax is not None:
            raise Problem(400, 'Ungeklärte Kirchenzugehörigkeit darf nicht als bekannte Mitgliedschaft erklärt werden.')
    authorization = evidence['employee_deduction_authorization']
    if authorization is not None:
        _ref(authorization)
    booked = day(evidence['taxation_recorded_on']) if evidence['taxation_recorded_on'] is not None else None
    certificate = day(evidence['tax_certificate_issued_on']) if evidence['tax_certificate_issued_on'] is not None else None
    if booked is not None and booked < payroll_start or certificate is not None and certificate < payroll_start:
        raise Problem(400, 'Steuerbehandlung oder Bescheinigung liegt vor dem zugeordneten Zuflussmonat.')
    blockers = []
    def block(code, message):
        blockers.append(dict(code=code, message=message))
    if amount_minor > limit:
        block('travel_flat_capacity_exceeded', 'Der Betrag überschreitet die tatsächlich belegte 25%-Reisekostengrenze.')
    if not evidence['church_method_applies_to_all']:
        block('travel_church_policy_incomplete', 'Das Verfahren muss für den Anmeldezeitraum und Tatbestand einheitlich angewendet werden.')
    unknown_general = (membership is not None and
                       membership['kind'] == 'unknown_membership_general_rate' and
                       church_tax is None)
    if church_method == 'evidence' and (membership is None or church_tax is None and not unknown_general):
        block('travel_church_membership_missing', 'Das Nachweisverfahren benötigt belegte Kirchenzugehörigkeit oder Nichtzugehörigkeit.')
    if not employer_bears_tax and authorization is None:
        block('travel_employee_tax_authorization_missing', 'Die Abwälzung auf den Beschäftigten benötigt eine konkrete Vereinbarung.')
    if employer_bears_tax and authorization is not None:
        raise Problem(400, 'Ein Arbeitnehmerabzug gehört nicht zur vollständigen Arbeitgeberübernahme.')
    if booked is None:
        block('travel_tax_timing_missing', 'Die tatsächliche zeitliche Pauschalbesteuerung muss für die SV-Beurteilung feststehen.')

    if church_method == 'simplified':
        church_rate = 700 if region == 'ni_ev_westfalen' else SIMPLIFIED_RATES[federal_state]
    else:
        ordinary_rate = 900 if region == 'bw_bad_wimpfen_mainz' else 800 if federal_state in ('BW', 'BY') else 900
        church_rate = ordinary_rate if church_tax or unknown_general else 0
    # No half-up rounding, no ordinary wage-tax/SolZ allowance, no child factor.
    wage = amount_minor * 2500 // 10000
    solidarity = wage * 550 // 10000
    church = wage * church_rate // 10000
    total = wage + solidarity + church
    deadline = date(2027, 2, 28)
    if certificate is not None:
        deadline = min(deadline, certificate)
    timely = booked is not None and booked <= deadline
    policy = dict(filing_period_from=first.isoformat(), filing_period_to=last.isoformat(),
                  federal_state=federal_state, jurisdiction=region, tax_rule=RULES['tax_rule'])
    output = dict(schema_version=1, rule_version=RULE_VERSION, rules_hash=RULES_SHA256,
        source_hash=_sha(dict(amount_minor=amount_minor, federal_state=federal_state,
            church_tax=church_tax, church_method=church_method,
            employer_bears_tax=employer_bears_tax, evidence=evidence)),
        policy_key=_sha(policy), policy_choice_hash=_sha(dict(policy, church_method=church_method)),
        policy_ref=dict(evidence['policy_ref']), policy=policy,
        amount_minor=amount_minor, eligible_limit_minor=limit,
        church_method=church_method, church_rate_basis_points=church_rate,
        employer_bears_tax=employer_bears_tax, can_calculate=not blockers,
        wage_tax_minor=None if blockers else wage,
        solidarity_minor=None if blockers else solidarity,
        church_tax_minor=None if blockers else church,
        statutory_employer_due_minor=None if blockers else total,
        employer_total_minor=None if blockers else total if employer_bears_tax else 0,
        employee_tax_minor=None if blockers else 0 if employer_bears_tax else total,
        employee_cash_after_flat_tax_minor=None if blockers else amount_minor if employer_bears_tax else amount_minor-total,
        social_exemption_basis=RULES['social_rule'], social_exempt=not blockers and timely,
        social_gross_minor=None if blockers else 0 if timely else amount_minor,
        social_exemption_conditions=dict(taxation_recorded_on=evidence['taxation_recorded_on'],
            certificate_issued_on=evidence['tax_certificate_issued_on'], deadline=deadline.isoformat(),
            timely=timely, source_resolution_required=True),
        actual_payment_created=False, statutory_transmitted=False, blockers=blockers)
    return dict(output, calculation_hash=_sha(output))
