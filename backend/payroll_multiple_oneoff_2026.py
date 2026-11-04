"""Additive Source5/v7 draft composition; no dispatcher or payment activation.

The first bounded contract keeps claims, planned receipt events, the statutory
social month group and tax calculation identities separate. Multiple receipts
have a verified monthly social assignment but deliberately no final tax/net
until their tax grouping and contribution allocation have been established.
Actual payment evidence and claim consumption belong to the private resolver.
"""
from copy import deepcopy
import hashlib
import re

from core import Problem, canonical
from payroll_calculations_2026 import CALCULATION_RULE_VERSION, build_calculation_plan, calculate_calculation_source
from payroll_de_2026 import month_range, normalize_profile
from payroll_annual_basis_2026 import employer_key, reference
from payroll_oneoff_2026 import _shape, _ref, _date, _int, select_one_off_assignment
from payroll_oneoff_composition_2026 import (
    ONEOFF_RULE_VERSION, SOURCE_CONTRACT_VERSION as SINGLE_CONTRACT, MONEY_FIELDS,
    _annual, _claim_section, _current_projection, _last_period, _room,
    calculate_oneoff_source)

MULTIPLE_RULE_VERSION='de_2026_multiple_oneoff_v7'
SOURCE_CONTRACT_VERSION=1
SOURCE_SCHEMA_VERSION=5
RULES=dict(version=MULTIPLE_RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION,
    inherited_single_rule=ONEOFF_RULE_VERSION,monthly_march_clause=True,
    multiple_tax_grouping='unresolved_blocked',component_contribution_allocation='unresolved_blocked',
    receipt_status='planned_only',actual_payment_created=False,
    monthly_source='https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Broschueren/DieBeitragspflichtvoneinmaliggezahltemArbeitsentgelt.pdf?__blob=publicationFile',
    monthly_source_section='January 2026; section 13.1, page 19')


def sha(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


RULES_SHA256=sha(RULES)


def _key(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):
        raise Problem(400,'Stabile ursprüngliche Anspruchs-/Zuflussidentität erforderlich.')
    return value


def select_monthly_assignment(*,receipt_events,current_room,previous_room,current_period_ref,
        previous_period_ref,mandatory_statutory_health,previous_year_employment):
    """KBS 2026 13.1: decide the entire actual/planned month, never each bonus.

    Source authority, completeness and exclusion of the group's own previous
    consumption are resolver obligations. No allocation to individual net
    payments, or assumption about their tax grouping, is made by this helper.
    """
    if not isinstance(receipt_events,list) or not 1<=len(receipt_events)<=100:
        raise Problem(400,'Ein bis hundert vollständige belegte Zuflussbestandteile erforderlich.')
    events=[];seen=set();month=None
    for event in receipt_events:
        _shape(event,'component_key event_key receipt_date gross_minor')
        _key(event['component_key']);_key(event['event_key']);_int(event['gross_minor'],1)
        day=_date(event['receipt_date']);current=day.strftime('%Y-%m')
        if day.year!=2026 or month is not None and current!=month:
            raise Problem(400,'Eine SV-Monatsgruppe enthält genau einen Zuflussmonat 2026.')
        if event['event_key'] in seen:raise Problem(409,'Dasselbe Zuflussereignis darf nur einmal in der Monatsgruppe vorkommen.')
        seen.add(event['event_key']);month=current;events.append(dict(event))
    events.sort(key=lambda value:(value['receipt_date'],value['event_key']))
    total=sum(value['gross_minor'] for value in events);_int(total,1)
    decisive='health' if mandatory_statutory_health else 'pension'
    room=current_room['branches'][decisive]['room_minor'] if current_room else 0
    if int(month[-2:])<=3 and total>room and previous_room is None and previous_year_employment:
        raise Problem(409,'Die vollständige gemeinsame Monatsgruppe benötigt ihre belegte Vorjahresbasis.')
    assignment=select_one_off_assignment(receipt_date=events[-1]['receipt_date'],amount_minor=total,
        current_room=current_room,previous_room=previous_room,current_period_ref=current_period_ref,
        previous_period_ref=previous_period_ref,mandatory_statutory_health=mandatory_statutory_health,
        previous_year_employment=previous_year_employment)
    return dict(month=month,gross_minor=total,receipt_events=events,assignment=assignment,
        source_hash=sha(dict(events=events,current_room=current_room,previous_room=previous_room,
            current_period_ref=current_period_ref,previous_period_ref=previous_period_ref,
            mandatory_statutory_health=mandatory_statutory_health,previous_year_employment=previous_year_employment)),
        component_allocations=None,actual_payment_created=False)


def _canonical_snapshot(snapshot):
    _shape(snapshot,'schema_version source_contract_version rule_version employee_id month '
        'running_calculation_case components current_annual_basis previous_annual_basis annual_tax_forecasts completeness')
    if (type(snapshot['schema_version']) is not int or snapshot['schema_version']!=1
            or type(snapshot['source_contract_version']) is not int or snapshot['source_contract_version']!=1
            or snapshot['rule_version']!=MULTIPLE_RULE_VERSION):
        raise Problem(400,'Expliziter Mehrfachbezugsvertrag v7/1 erforderlich.')
    _key(snapshot['employee_id']);first,last=month_range(snapshot['month'])
    if first.year!=2026:raise Problem(400,'Unterstützter Zuflussmonat 2026 erforderlich.')
    _shape(snapshot['completeness'],'month_events_complete evidence_ref')
    if snapshot['completeness']['month_events_complete'] is not True:
        raise Problem(409,'Vollständige Monatsgruppe ausdrücklich aus ihren Quellen bestätigen.')
    _ref(snapshot['completeness']['evidence_ref'])
    components=snapshot['components']
    if not isinstance(components,list) or not 1<=len(components)<=20:
        raise Problem(400,'Ein bis zwanzig eindeutige Anspruchskomponenten erforderlich.')
    normalized=deepcopy(snapshot);normalized['components']=[];claims=set();events=set()
    allowed=set()
    for source in [snapshot['current_annual_basis']]+[part.get('earning',{}) for part in components if isinstance(part,dict)]:
        if not isinstance(source,dict):raise Problem(400,'Vollständige ursprüngliche Jahres-/Anspruchsobjekte erforderlich.')
        for original in source.get('sources',{}).get('source_files',[]):
            allowed.add(canonical(dict(id=original['id'],revision=1,content_hash=original['content_hash'])))
    if canonical(snapshot['completeness']['evidence_ref']) not in allowed:
        raise Problem(409,'Monatsvollständigkeit benötigt eines der gebundenen geschützten Originale.')
    for component in components:
        _shape(component,'component_key earning planned_receipts')
        earning=_annual(component['earning'],'one_off_earning',snapshot['employee_id'])
        key=_key(component['component_key'])
        if key!=earning['id'] or key in claims:
            raise Problem(409,'Jeder ursprüngliche Anspruch besitzt genau seine eigene stabile Komponente.')
        claims.add(key);receipts=component['planned_receipts']
        if not isinstance(receipts,list) or not 1<=len(receipts)<=20:
            raise Problem(400,'Begrenzte konkrete geplante Zuflüsse je Anspruch erforderlich.')
        planned=[];total=0
        for receipt in receipts:
            _shape(receipt,'event_key receipt_date gross_minor document_refs')
            event_key=_key(receipt['event_key']);day=_date(receipt['receipt_date']);_int(receipt['gross_minor'],1)
            if event_key in events or day.strftime('%Y-%m')!=snapshot['month']:
                raise Problem(409,'Zuflussidentitäten sind eindeutig und gehören zum bestätigten Monat.')
            documents=receipt['document_refs']
            if not isinstance(documents,list) or not 1<=len(documents)<=20:
                raise Problem(400,'Jeder geplante Bruttozufluss benötigt konkrete Originalreferenzen.')
            for document in documents:_ref(document)
            if len({canonical(value) for value in documents})!=len(documents) or any(canonical(value) not in allowed for value in documents):
                raise Problem(409,'Zuflussnachweise müssen eindeutige gebundene Originalfassungen sein.')
            events.add(event_key);total+=receipt['gross_minor']
            planned.append(dict(receipt,document_refs=sorted(documents,key=canonical)))
        if total>earning['details']['amount_minor']:
            raise Problem(409,'Geplante Teilzuflüsse dürfen den wirksamen Originalanspruch nicht überschreiten.')
        normalized['components'].append(dict(component_key=key,earning=deepcopy(earning),
            planned_receipts=sorted(planned,key=lambda value:(value['receipt_date'],value['event_key']))))
    if len(events)>100:raise Problem(400,'Die vollständige Monatsgruppe umfasst höchstens hundert Zuflüsse.')
    normalized['components'].sort(key=lambda value:value['component_key'])
    forecasts=normalized['annual_tax_forecasts']
    if not isinstance(forecasts,list) or len(forecasts)>100:
        raise Problem(400,'Explizite Steuerquellenliste erforderlich.')
    seen=set()
    for item in forecasts:
        _shape(item,'event_key annual_tax_forecast');_key(item['event_key'])
        if item['event_key'] not in events or item['event_key'] in seen:raise Problem(409,'Steuerquelle benötigt genau ihr eigenes Zuflussereignis.')
        seen.add(item['event_key']);_annual(item['annual_tax_forecast'],'annual_tax_forecast',snapshot['employee_id'])
    forecasts.sort(key=lambda value:value['event_key'])
    return normalized


def calculate_multiple_source(snapshot,*,rule_version,source_contract_version):
    if (rule_version!=MULTIPLE_RULE_VERSION or type(source_contract_version) is not int
            or source_contract_version!=SOURCE_CONTRACT_VERSION):
        raise Problem(400,'Unbekannte explizite Mehrfachbezugsregel oder Quellenvertragsversion.')
    source=_canonical_snapshot(snapshot);employee=source['employee_id'];month=source['month'];first,last=month_range(month)
    case=source['running_calculation_case']
    if (case.get('kind')!='calculation_case' or case.get('status')!='active' or case.get('employee_id')!=employee
            or case.get('rule_version')!=CALCULATION_RULE_VERSION or case['details']['month']!=month):
        raise Problem(409,'Dieselbe aktive laufende v5-Originalrechnung erforderlich.')
    running=calculate_calculation_source(case['sources'],rule_version=case['rule_version'],source_contract_version=case['source_contract_version'])
    if build_calculation_plan(case['sources'],rule_version=case['rule_version'],source_contract_version=case['source_contract_version'])!=case['plan']:
        raise Problem(409,'Der laufende Gesamtplan muss aus denselben Originalen unverändert ableitbar sein.')
    current=_annual(source['current_annual_basis'],'annual_basis',employee)
    previous=_annual(source['previous_annual_basis'],'annual_basis',employee) if source['previous_annual_basis'] else None
    events=[dict(component_key=part['component_key'],**{key:event[key] for key in ('event_key','receipt_date','gross_minor')})
        for part in source['components'] for event in part['planned_receipts']]
    events.sort(key=lambda value:(value['receipt_date'],value['event_key']));cutoff=events[-1]['receipt_date']
    if (current['details']['year']!=2026 or current['details']['coverage_to']!=last.isoformat()
            or current['details']['as_of_date']!=cutoff or current['sources']['current_calculation_case']!=case
            or current['details']['current_calculation_case_ref']!=reference(case)):
        raise Problem(409,'Die SV-Monatsbasis muss die vollständige Gruppe und dieselbe laufende Originalrechnung binden.')
    if previous and (previous['details']['year']!=2025 or previous['details']['coverage_to']!='2025-12-31'
            or previous['details']['as_of_date']!=cutoff):
        raise Problem(409,'Die Vorjahresbasis benötigt denselben vollständigen Gruppenstichtag.')
    company=employer_key(current['sources']['identity'])
    records=[part['earning'] for part in source['components']]+([previous] if previous else [])
    if any(employer_key(record['sources']['identity'])!=company for record in records):
        raise Problem(409,'Anspruchsbestandteile und Jahresquellen müssen zum selben Arbeitgeber gehören.')
    for item in source['annual_tax_forecasts']:
        event=next(event for event in events if event['event_key']==item['event_key'])
        earning=next(part['earning'] for part in source['components'] if part['component_key']==event['component_key'])
        forecast=item['annual_tax_forecast'];history=forecast['sources']['annual_basis']
        if (forecast['sources']['current_one_off']!=earning or forecast['details']['current_one_off_ref']!=reference(earning)
                or forecast['details']['receipt_date']!=event['receipt_date'] or employer_key(forecast['sources']['identity'])!=company
                or history['sources']['current_calculation_case']!=case):
            raise Problem(409,'Jede Steuerquelle muss ihren konkreten Anspruch, Zuflusstag und laufenden Originalfall binden.')
    projections=[value for value in current['sources']['internal_periods'] if value['source_ref']==reference(case)]
    if running['payroll_calculation_complete'] and projections!=[_current_projection(case,running)]:
        raise Problem(409,'Die laufende Jahresprojektion darf keine zusätzliche SV-Luft erfinden.')
    for part in source['components']:_claim_section(part['earning'])
    for basis in [current]+([previous] if previous else []):
        if any(run['source']['month']==month for run in basis['sources']['payroll_runs']):
            raise Problem(409,'Der bereits verbrauchte eigene Zuflussmonat benötigt eine explizite vollständige Gruppenkorrektur ohne Selbstverbrauch.')
    blockers=list(running['blockers'])
    def block(code,message):
        if not any(value['code']==code for value in blockers):blockers.append(dict(code=code,message=message))
    if running['scope']!='regular_standard_segments' or any(part['earning']['details']['section_key']!='regular' for part in source['components']):
        block('multiple_oneoff_status_source_required','Der Mehrfachbezug benötigt den belegten regulären Versicherungszweig.')
    if any(period['section_key']!='regular' for basis in [current]+([previous] if previous else []) for period in basis['plan']['projection']['periods']):
        block('multiple_oneoff_mixed_sections_required','Gemischte Anspruchs-/Versicherungsabschnitte benötigen ihre eigene Zuordnung.')
    total=sum(event['gross_minor'] for event in events);_int(total,1)
    result=deepcopy(running);result.update(rule_version=rule_version,rules_sha256=RULES_SHA256,source_contract_version=source_contract_version,
        scope='multiple_oneoff_review_required',payroll_calculation_complete=False,social_contributions_available=False,
        gross_minor=running['gross_minor']+total if running['gross_minor'] is not None else None,
        running_calculation=running,blockers=blockers,tax_method=None,
        multiple_one_off_details=dict(source_snapshot_hash=sha(source),month=month,amount_minor=total,
            components=[dict(component_key=part['component_key'],earning_ref=reference(part['earning']),
                claim_minor=part['earning']['details']['amount_minor'],planned_minor=sum(event['gross_minor'] for event in part['planned_receipts']),
                remaining_claim_minor=part['earning']['details']['amount_minor']-sum(event['gross_minor'] for event in part['planned_receipts'])) for part in source['components']],
            receipt_events=events,sv_month_group_key=sha(dict(employee_id=employee,employer=company,month=month)),
            social_month_group=None,tax_groups=None,actual_payment_created=False,claim_consumption_created=False))
    for name in MONEY_FIELDS:result[name]=None
    current_period=_last_period(current,'regular',cutoff);previous_period=_last_period(previous,'regular',cutoff) if previous else None
    current_room=_room(current,current_period,'regular');previous_room=_room(previous,previous_period,'regular') if previous else None
    profile=next(value['profile'] for value in case['sources']['profiles'] if reference(value)==case['plan']['selected_profile_ref'])
    if normalize_profile(profile)!=profile or profile['health_insurance']!='statutory_mandatory':
        block('multiple_oneoff_insurance_required','Die gemeinsame Gruppe benötigt ihren geprüften KV-Pflichtzweig.')
    if int(month[-2:])<=3 and total>(current_room['branches']['health']['room_minor'] if current_room else 0) and previous is None:
        block('previous_year_evidence_required','Die gesamte Monatsgruppe überschreitet die aktuelle KV-Luft; vollständiges Vorjahr belegen.')
    if not blockers:
        result['multiple_one_off_details']['social_month_group']=select_monthly_assignment(receipt_events=events,current_room=current_room,
            previous_room=previous_room,current_period_ref=current_period['source_ref'] if current_period else None,
            previous_period_ref=previous_period['source_ref'] if previous_period else None,
            mandatory_statutory_health=True,previous_year_employment=previous_period is not None)
    full_single=len(events)==1 and events[0]['gross_minor']==source['components'][0]['earning']['details']['amount_minor']
    if len(events)>1:
        block('multiple_oneoff_tax_grouping_unresolved','Mehrere Zuflüsse oder Ansprüche im Monat benötigen die fachlich belegte Steuergruppenregel; auch ein gemeinsamer Tag genügt dafür nicht.')
        block('multiple_oneoff_contribution_allocation_unresolved','Die gemeinsame SV-Zuordnung ersetzt keine geprüfte Verteilung der Beiträge auf einzelne Zahlungsereignisse.')
    elif not full_single:
        block('partial_oneoff_fulfillment_required','Ein Teilzufluss benötigt seine eigene bestätigte Brutto-Erfüllungs- und Steuerquelle.')
    elif len(source['annual_tax_forecasts'])!=1:
        block('oneoff_tax_forecast_required','Der einzelne vollständige Anspruch benötigt seine unveränderte tatsächliche Steuerprognose.')
    elif not blockers:
        single=calculate_oneoff_source(dict(schema_version=1,source_contract_version=SINGLE_CONTRACT,rule_version=ONEOFF_RULE_VERSION,
            employee_id=employee,month=month,running_calculation_case=case,one_off_earning=source['components'][0]['earning'],
            current_annual_basis=current,previous_annual_basis=previous,annual_tax_forecast=source['annual_tax_forecasts'][0]['annual_tax_forecast']),
            rule_version=ONEOFF_RULE_VERSION,source_contract_version=SINGLE_CONTRACT)
        details=result['multiple_one_off_details'];result=deepcopy(single)
        result.update(rule_version=rule_version,rules_sha256=RULES_SHA256,source_contract_version=SOURCE_CONTRACT_VERSION,
            scope='regular_standard_multiple_oneoff' if single['payroll_calculation_complete'] else 'multiple_oneoff_review_required',
            multiple_one_off_details=details)
        result.pop('one_off_details')
        details['single_original_calculation']=single
    return result
