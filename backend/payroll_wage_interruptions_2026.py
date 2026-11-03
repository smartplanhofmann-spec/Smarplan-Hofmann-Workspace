"""Pure evidenced U assessment; independent of wage/SV calculation versions.

See docs/CRM_ERP_LOHN_U_MERKMAL_VERTRAG_2026.md for read official sources.
The initial branch deliberately leaves partial wage claims and year carry-ins
unresolved instead of inventing a legal percentage or an interruption count.
"""
from datetime import timedelta
import hashlib

from core import Problem,canonical
from payroll_de_2026 import day
from payroll_entitlements_2026 import _shape,_refs

RULE_VERSION='de_2026_wage_interruptions_v1'
EXCLUDED_PAYMENTS=frozenset(('short_time_work_benefit','qualification_benefit','employer_maternity_supplement',
    'civil_service_parental_birth_supplement','infection_protection_compensation','section3_number21',
    'section3_number28','section3_number28a'))
RULES=dict(version=RULE_VERSION,threshold_workdays=5,scope='fully_lost_wage_claim',
    workdays='canonical_contractual_schedule',unit='one_uninterrupted_period_not_months',
    exceptions='estg_section41_paragraph1_sentence4',partial_claim='explicit_blocker',
    year_carry_in='explicit_blocker',statutory_transmitted=False)
RULES_SHA256=hashlib.sha256(canonical(RULES).encode()).hexdigest()


def _dates(first,last):
    return [(first+timedelta(days=index)).isoformat() for index in range(max(0,(last-first).days+1))]


def calculate_wage_interruptions(source,rule_version=RULE_VERSION):
    if rule_version!=RULE_VERSION:raise Problem(400,'Unbekannte U-Merkmalsregel; kein stiller Versionswechsel.')
    _shape(source,'year assessment_through employment_intervals days carry_in_loss tax_scope')
    if type(source['year']) is not int or source['year']!=2026:raise Problem(400,'U-Prüfjahr 2026 ausdrücklich angeben.')
    end=day(source['assessment_through']);first=day('2026-01-01')
    if end.year!=2026 or type(source['carry_in_loss']) is not bool:raise Problem(400,'Tatsächlichen Prüfungstag und Vorjahresverlust ausdrücklich belegen.')
    if source['tax_scope'] not in ('individual','flat_minijob'):raise Problem(400,'Belegten lohnsteuerlichen Aufzeichnungsumfang angeben.')
    periods=source['employment_intervals'];rows=source['days'];expected=[];previous=None
    if not isinstance(periods,list) or not periods or not isinstance(rows,list):raise Problem(400,'Tatsächliche Beschäftigung und Tagesquellen vollständig angeben.')
    for interval in periods:
        _shape(interval,'from to evidence_refs');_refs(interval['evidence_refs'])
        left=day(interval['from']);right=day(interval['to']) if interval['to'] else end
        if right<left or previous is not None and left<=previous:raise Problem(400,'Beschäftigungsepisoden müssen aufsteigend und überschneidungsfrei sein.')
        previous=right
        expected.extend(_dates(max(first,left),min(end,right)))
    by_date={};blockers=[]
    def block(code,message):
        if not any(value['code']==code for value in blockers):blockers.append(dict(code=code,message=message))
    if source['carry_in_loss']:block('year_carry_in_requires_rule','Ein vor dem Jahresbeginn bestehender Anspruchsverlust benötigt den belegten jahresübergreifenden Zweig.')
    if source['tax_scope']=='flat_minijob':block('flat_minijob_recording_scope_requires_rule','Pauschal besteuerter Minijob benötigt die gesonderte Aufzeichnungsabgrenzung nach §4Abs2LStDV.')
    for row in rows:
        _shape(row,'date contractual_workday wage_claim section41_1_4_payment_kind claim_evidence_refs schedule_evidence_refs exception_evidence_refs')
        day(row['date']);_refs(row['claim_evidence_refs']);_refs(row['schedule_evidence_refs']);_refs(row['exception_evidence_refs'])
        if row['date'] in by_date or row['date'] not in expected:raise Problem(400,'Tagesnachweis ist doppelt oder außerhalb der tatsächlichen geprüften Beschäftigung.')
        if type(row['contractual_workday']) is not bool or row['wage_claim'] not in ('none','preserved','partial_unknown'):
            raise Problem(400,'Vertraglichen Arbeitstag und belegten Anspruch ausdrücklich angeben.')
        kind=row['section41_1_4_payment_kind']
        if kind is not None and kind!='none' and kind not in EXCLUDED_PAYMENTS:raise Problem(400,'Unbekannte gesetzliche Satz4-Leistungsart.')
        if kind is None:block('excluded_payment_unknown','Die einschlägigen §41Abs1Satz4-Leistungen sind noch nicht vollständig geprüft.')
        if row['wage_claim']=='partial_unknown':block('partial_wage_claim_requires_assessment','Teilweise verbliebene Arbeitslohnansprüche benötigen eine eigene belegte wesentliche Ausfallbeurteilung.')
        by_date[row['date']]=row
    if sorted(by_date)!=expected:raise Problem(409,'Jeden Kalendertag der geprüften Beschäftigung bis zum tatsächlichen Prüfungstag genau einmal belegen.')
    candidates=[];active=[]
    def flush():
        if active:
            candidates.append(dict(from_date=active[0],to_date=active[-1],qualifying_workdays=list(active),
                workday_count=len(active),letter_u=len(active)>=5))
            active.clear()
    for interval in periods:
        flush()
        for date in _dates(max(first,day(interval['from'])),min(end,day(interval['to']) if interval['to'] else end)):
            row=by_date[date]
            if row['section41_1_4_payment_kind']!='none':flush();continue
            if not row['contractual_workday']:continue
            if row['wage_claim']=='none':active.append(date)
            else:flush()
        flush()
    periods=[value for value in candidates if value['letter_u']]
    result=dict(schema_version=1,rule_version=RULE_VERSION,rules_sha256=RULES_SHA256,year=2026,
        assessment_through=end.isoformat(),source_hash=hashlib.sha256(canonical(source).encode()).hexdigest(),
        can_determine=not blockers,number_u=None if blockers else len(periods),periods=periods,candidates=candidates,
        covered_dates=expected,blockers=sorted(blockers,key=lambda value:value['code']),
        automatic_payment_created=False,statutory_transmitted=False)
    return dict(result,plan_hash=hashlib.sha256(canonical(result).encode()).hexdigest())
