"""Explicit pre-employment onset, IKK2026 p7 example 3.

Original medical dates are never rewritten. A separately hashed legal
projection bounds this employment's claim to its agreed commencement.
"""
from copy import deepcopy
import hashlib

from core import Problem,canonical
from payroll_de_2026 import day
from payroll_entitlements_2026 import _shape,_refs,_interval,ONE_DAY
from payroll_sickness_phases_2026 import derive_sickness_phases,SICKNESS_PHASE_RULES_SHA256

SICKNESS_START_RULE_VERSION='de_2026_sickness_start_v4'
SICKNESS_START_RULES=dict(version=SICKNESS_START_RULE_VERSION,
    phase_rules_hash=SICKNESS_PHASE_RULES_SHA256,
    employment='ACTUAL_CONTRACT_CONCLUDED_BEFORE_AU_AGREED_START_UNCHANGED',
    waiting='28_DAYS_FROM_AGREED_EMPLOYMENT_START_NO_PRIOR_SERVICE_ASSUMED',
    history='ORIGINAL_PREEMPLOYMENT_AU_PRESERVED_SEPARATE_LEGAL_PROJECTION',
    multiple_preexisting_causes='REQUIRES_SEPARATE_DECISION',
    evidence='IKK_2026_PAGE_7_EXAMPLE_3')
SICKNESS_START_RULES_SHA256=hashlib.sha256(canonical(SICKNESS_START_RULES).encode()).hexdigest()


def derive_sickness_start(source):
    _shape(source,'employment_from employment_to pay_basis complete_from complete_through history_evidence_refs episodes prevention_cases employment_commencement')
    commencement=source['employment_commencement']
    _shape(commencement,'contract_concluded_on evidence_refs');_refs(commencement['evidence_refs'])
    contract=day(commencement['contract_concluded_on']);employment=day(source['employment_from'])
    if contract>=employment:raise Problem(400,'Dieser Nachweis benötigt einen vor Beschäftigungsaufnahme abgeschlossenen Vertrag.')
    if source['complete_from']!=source['employment_from']:
        raise Problem(400,'Dieser Beginnfall benötigt vollständige Vorzeiten ab dem tatsächlichen Beschäftigungsbeginn.')
    projection=deepcopy({key:value for key,value in source.items() if key!='employment_commencement'})
    if not isinstance(projection['episodes'],list):raise Problem(400,'Ungültige AU-Ursachen.')
    original_dates={};periods=[]
    for episode in projection['episodes']:
        _shape(episode,'id from to onset first_scheduled_day continuation_group recovery_before unculpable evidence_refs')
        first,last=_interval(episode['from'],episode['to'])
        if first<employment:
            if first<=contract or last<employment or episode['onset']!='before_employment' or episode['first_scheduled_day'] is not None or episode['recovery_before'] is not True:
                raise Problem(409,'Belegter AU-Beginn muss nach Vertragsabschluss liegen und bis zur vereinbarten Aufnahme fortbestehen.')
            if periods:raise Problem(409,'Mehrere vor Beschäftigungsbeginn bestehende Ursachen benötigen eine eigene Anfangsentscheidung.')
            original_dates[episode['id']]=episode['from']
            periods.append(dict(episode_id=episode['id'],from_date=episode['from'],to_date=(employment-ONE_DAY).isoformat(),employment_wage_entitlement=False))
            # This is the legal claim projection, not an alteration of the
            # original medical episode or an invented actual scheduled shift.
            episode.update(**{'from':employment.isoformat()},onset='before_work')
        elif episode['onset']=='before_employment':
            raise Problem(400,'AU-Beginn liegt nicht vor Beschäftigungsaufnahme.')
    if not periods:raise Problem(400,'Dieser Regelzweig benötigt eine tatsächlich vor Beschäftigungsbeginn begonnene AU.')
    result=derive_sickness_phases(projection)
    for episode in result['episodes']:
        if episode['episode_id'] in original_dates:episode['from_date']=original_dates[episode['episode_id']]
    for case in result['prevention_cases']:
        member_ids=next(item['episode_ids'] for item in source['prevention_cases'] if item['id']==case['id'])
        case['original_au_from']=min(next(item['from'] for item in source['episodes'] if item['id']==identity) for identity in member_ids)
    result.update(rule_version=SICKNESS_START_RULE_VERSION,rules_hash=SICKNESS_START_RULES_SHA256,
        source_hash=hashlib.sha256(canonical(source).encode()).hexdigest(),
        legal_projection_hash=hashlib.sha256(canonical(projection).encode()).hexdigest(),
        preemployment_periods=periods)
    result.pop('plan_hash')
    result['plan_hash']=hashlib.sha256(canonical(result).encode()).hexdigest()
    return result
