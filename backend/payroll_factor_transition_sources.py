"""Resolve actual immutable originals for the explicit v14 factor/Midijob case."""
from core import Problem
from business_payroll_facts import reference
from payroll_de_2026 import month_range
from payroll_factor_transition_2026 import RULE_VERSION,SOURCE_CONTRACT_VERSION,normalize_case_assessment


def snapshot(api,employee,details,ids,*,fresh,actor=None):
    employee_id=employee['id'];review=normalize_case_assessment(details['factor_transition_assessment'])
    if review['employee_id']!=employee_id:
        raise Problem(400,'Die Prognoseentscheidung gehört nicht zur gewählten Person.')
    if fresh and review['declaration_date']>api.hr.now()[:10]:
        raise Problem(400,'Die tatsächliche Prognoseprüfung darf nicht aus der Zukunft stammen.')
    ref=review['forecast_evidence_ref']
    if ref['id'] not in ids:
        raise Problem(400,'Das tatsächliche Prognoseoriginal am Gesamtfall binden.')
    base=api.facts._fact_ref(employee_id,details['period_case_ref'],'period_case',fresh=fresh)
    if base['plan']['rule_version']!='de_2026_standard_factor_period_v9' or base['details']['month']!=details['month']:
        raise Problem(400,'Den ursprünglichen eigenen Faktorperiodenfall desselben Monats verwenden.')
    original=base['sources']
    if fresh and api.facts._snapshot(employee,'period_case',base['details'],base['source_file_ids'])!=original:
        raise Problem(409,'Die tatsächliche ursprüngliche Monatsvorbereitung ist nicht mehr aktuell.')
    if (details['employment_terms_refs']!=[reference(original['employment_terms'])]
            or details['profile_refs']!=sorted([reference(row)for row in original['profiles']],key=lambda row:row['id'])
            or details['identity_refs']!=sorted([reference(row)for row in original['identities']],key=lambda row:row['id'])):
        raise Problem(400,'Die vollständigen tatsächlichen Monatsquellen unverändert binden.')
    terms=[api.facts._fact_ref(employee_id,value,'employment_terms',fresh=fresh)for value in details['employment_terms_refs']]
    profiles=[api.facts._payroll_ref(employee_id,value,fresh=fresh)for value in details['profile_refs']]
    identities=[api.facts._identity_ref(employee_id,value,fresh=fresh)for value in details['identity_refs']]
    if len(terms)!=1 or len(profiles)!=1 or len(identities)!=1:
        raise Problem(400,'Genau eine tatsächliche Beschäftigung, Faktorprofilfassung und Identität binden.')
    if fresh:
        first,last=month_range(details['month'])
        expected=[reference(row)for row in api.facts._all(employee_id,'employment_terms')
            if row['status']=='active' and row['effective_from']<=last.isoformat()
            and (row['effective_to'] is None or row['effective_to']>=first.isoformat())]
        if sorted(expected,key=lambda row:row['id'])!=details['employment_terms_refs']:
            raise Problem(409,'Alle tatsächlich aktiven Beschäftigungsnachweise dieses Monats vollständig binden.')
        from business_payroll_entitlements import PayrollEntitlements
        from business_travel_allowances import TravelAllowances
        if any(row['status']=='active' and row['effective_from']<=last.isoformat() and row['effective_to']>=first.isoformat()
                for row in PayrollEntitlements(api.office)._all(employee_id)):
            raise Problem(409,'Ein zusätzlicher tatsächlicher Anspruch benötigt seinen eigenen Faktor-Midijob-Regelzweig.')
        if any(row['status']=='approved' and row['details']['period_from']<=last.isoformat()
                and row['details']['period_to']>=first.isoformat()
                for row in TravelAllowances(api.office)._all('settlement',employee_id)):
            raise Problem(409,'Ein tatsächlicher Reisebezug ist nicht im ersten Faktor-Midijob-Vertrag enthalten.')
    files=api._files(employee_id,ids,fresh=fresh);indexed={row['id']:row for row in files}
    if indexed[ref['id']]['content_hash']!=ref['content_hash']:
        raise Problem(409,'Das ursprüngliche tatsächliche Prognoseoriginal wurde verändert.')
    if (details['segment_events'] or details['entitlement_case_refs'] or details['travel_settlement_refs']
            or details['flat_tax_decision'] is not None or details['thirty_day_rule'] is not None):
        raise Problem(400,'Dieser erste Faktor-Midijob-Vertrag umfasst keine Zusatz- oder Untermonatsfälle.')
    return dict(schema_version=1,source_contract_version=SOURCE_CONTRACT_VERSION,rule_version=RULE_VERSION,
        employee_id=employee_id,month=details['month'],period_case=base,employment_terms=terms,
        profiles=profiles,identities=identities,segment_events=[],thirty_day_rule=None,entitlements=[],
        travel_sources=[],flat_travel_tax=None,source_files=files,factor_transition_assessment=review)
