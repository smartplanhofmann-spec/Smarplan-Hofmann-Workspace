"""Explicit historical entitlement dispatcher; no newest-rule fallback."""
import hashlib

from core import Problem, canonical
import payroll_entitlements_2026 as original
from payroll_sickness_2026 import SICKNESS_RULE_VERSION, derive_sickness_entitlement
from payroll_sickness_phases_2026 import SICKNESS_PHASE_RULE_VERSION, derive_sickness_phases
from payroll_sickness_start_2026 import SICKNESS_START_RULE_VERSION, derive_sickness_start
from payroll_de_2026 import day
from datetime import timedelta


def requires_current_sickness_rule(record):
    """Known v1 free-day boundary may be read, but not newly applied."""
    if record['kind'] != 'sickness_history' or record['plan']['rule_version'] != original.ENTITLEMENT_RULE_VERSION:
        return False
    source = record['details']['input']
    return source['pay_basis'] == 'hourly' and any(
        episode['onset'] == 'non_workday' and
        day(episode['first_scheduled_day']) > day(episode['from']) + timedelta(days=1)
        for episode in source['episodes'])


def _current_version(kind,source):
    if kind!='sickness_history':return original.ENTITLEMENT_RULE_VERSION
    if isinstance(source,dict) and 'employment_commencement' in source:return SICKNESS_START_RULE_VERSION
    if isinstance(source,dict) and 'prevention_cases' in source:return SICKNESS_PHASE_RULE_VERSION
    return SICKNESS_RULE_VERSION


def calculate_entitlement_input(kind, source, rule_version=None):
    if rule_version is None:
        rule_version = _current_version(kind,source)
    if rule_version == original.ENTITLEMENT_RULE_VERSION:
        return original.calculate_entitlement_input(kind, source)
    if rule_version == SICKNESS_RULE_VERSION and kind == 'sickness_history':
        return derive_sickness_entitlement(source)
    if rule_version == SICKNESS_PHASE_RULE_VERSION and kind == 'sickness_history':
        return derive_sickness_phases(source)
    if rule_version == SICKNESS_START_RULE_VERSION and kind == 'sickness_history':
        return derive_sickness_start(source)
    raise Problem(409, 'Die gespeicherte Anspruchsregelversion passt nicht zur Anspruchsart oder ist nicht verfügbar.')


def build_entitlement_plan(snapshot, rule_version=None):
    if (not isinstance(snapshot, dict) or type(snapshot.get('schema_version')) is not int
            or snapshot['schema_version'] != 1):
        raise Problem(400, 'Unbekannte Anspruchsquellenversion.')
    if rule_version is None:
        rule_version = _current_version(snapshot['kind'],snapshot['details']['input'])
    if rule_version == original.ENTITLEMENT_RULE_VERSION:
        return original.build_entitlement_plan(snapshot, rule_version)
    primitive = calculate_entitlement_input(snapshot['kind'], snapshot['details']['input'], rule_version)
    result = {key:value for key,value in primitive.items() if key not in ('plan_hash', 'source_hash', 'kind')}
    result.update(kind=snapshot['kind'], entitlement_kind=primitive['kind'],
        input_hash=primitive['source_hash'], source_hash=hashlib.sha256(canonical(snapshot).encode()).hexdigest())
    result['plan_hash'] = hashlib.sha256(canonical(result).encode()).hexdigest()
    return result
