"""Canonical period projections for evidence-bound payroll annual history.

This module assembles exact period sources. It never accepts a desired annual
tax amount, ready-made annual SV room, or implicit zero for an uncovered month.
The private resolver owns source existence, authority and current revisions.
"""
import calendar
from datetime import date,timedelta
from decimal import Decimal
import hashlib
import re

from core import Problem,canonical
from payroll_oneoff_2026 import (BRANCHES,YEAR_RULES,_date,_int,_ref,_shape,_percent,
    _round,assess_social_contributions,annual_social_room)

ANNUAL_BASIS_VERSION='de_2025_2026_annual_basis_v1'
KINDS=('imported_period','imported_one_off','annual_basis','one_off_earning','annual_tax_forecast')
PROFILE_FIELDS='scheme health_insurance health_additional_percent saxony childless_surcharge care_child_discounts minijob_rv_exempt pension_other_compulsory u1_percent u2_percent'


def sha(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def reference(value):return {key:value[key] for key in ('id','revision','content_hash')}


def dates(start,end):
    first,last=_date(start),_date(end)
    if first>last:raise Problem(400,'Zeitraum endet vor seinem Beginn.')
    return [(first+timedelta(days=index)).isoformat() for index in range((last-first).days+1)]


def note(value,label):
    if not isinstance(value,str) or not value.strip() or len(value)>3000 or value!=value.strip() or any(ord(c)<32 for c in value):
        raise Problem(400,label+' vollständig und ohne Steuerzeichen angeben.')
    return value


def refs(value,*,minimum=0):
    if not isinstance(value,list) or not minimum<=len(value)<=1000:raise Problem(400,'Eine begrenzte Liste konkreter Quellenfassungen angeben.')
    result=[dict(_ref(item)) for item in value]
    if len({item['id'] for item in result})!=len(result):raise Problem(400,'Eine Quelle darf nur in einer Fassung verwendet werden.')
    return sorted(result,key=lambda item:item['id'])


def profile(value):
    _shape(value,PROFILE_FIELDS)
    if value['scheme'] not in ('regular_standard','regular_transition','commercial_minijob') or value['health_insurance'] not in ('statutory_mandatory','statutory_voluntary','private'):
        raise Problem(400,'Tatsächlichen historischen Versicherungs- und Beitragszweig angeben.')
    for name in ('saxony','childless_surcharge','minijob_rv_exempt','pension_other_compulsory'):
        if type(value[name]) is not bool:raise Problem(400,'Historische Versicherungsmerkmale ausdrücklich angeben.')
    _int(value['care_child_discounts'],0,4)
    for name in ('health_additional_percent','u1_percent','u2_percent'):_percent(value[name])
    if value['childless_surcharge'] and value['care_child_discounts']:raise Problem(400,'Kinderlosenzuschlag und Kinderabschläge widersprechen sich.')
    if value['scheme']!='commercial_minijob' and (value['minijob_rv_exempt'] or value['pension_other_compulsory']):
        raise Problem(400,'Minijobmerkmale gehören nicht zur regulären Beitragsrechnung.')
    return dict(value)


def normalize_details(kind,value):
    if kind not in KINDS:raise Problem(400,'Unbekannte Jahresfaktenart.')
    common='employer_identity_ref verification_note'
    if kind=='imported_period':
        _shape(value,common+' period_start period_end employment_from employment_to section_key profile branches running_gross_minor running_taxable_minor running_receipts original_rule_version original_rule_hash original_payroll_reference document_refs')
        first,last=_date(value['period_start']),_date(value['period_end'])
        if first.year not in YEAR_RULES or (first.year,first.month)!=(last.year,last.month) or first>last:
            raise Problem(400,'Eine konkrete 2025-/2026-Vortragsperiode innerhalb eines Monats angeben.')
        employed=_date(value['employment_from']);end=_date(value['employment_to']) if value['employment_to'] else None
        if employed>last or end is not None and (end<employed or end<first):raise Problem(400,'Vortragsperiode und tatsächliche Beschäftigung überschneiden sich nicht.')
        _int(value['running_gross_minor']);_int(value['running_taxable_minor'])
        if value['running_taxable_minor']>value['running_gross_minor']:raise Problem(400,'Laufendes Steuerbrutto überschreitet den dokumentierten Gesamtlohn.')
        receipts=[]
        if not isinstance(value['running_receipts'],list) or len(value['running_receipts'])>100:raise Problem(400,'Tatsächliche Zuflussbelege als begrenzte Liste angeben.')
        for item in value['running_receipts']:
            _shape(item,'received_on taxable_minor evidence_ref');_date(item['received_on']);_int(item['taxable_minor'],1);_ref(item['evidence_ref'])
            if item['received_on'][:7]<value['period_start'][:7]:raise Problem(400,'Zufluss liegt vor dem zugehörigen laufenden Lohnzeitraum.')
            receipts.append(dict(item))
        if sum(item['taxable_minor'] for item in receipts)>value['running_taxable_minor']:raise Problem(400,'Belegter Steuerzufluss übersteigt das ursprüngliche laufende Steuerbrutto.')
        p=profile(value['profile']);_shape(value['branches'],' '.join(BRANCHES));branches={}
        if value['section_key']!=('minijob' if p['scheme']=='commercial_minijob' else 'regular'):
            raise Problem(400,'Beschäftigungsabschnitt muss dem belegten regulären oder geringfügigen Versicherungszweig entsprechen.')
        for branch,item in value['branches'].items():
            _shape(item,'eligible_intervals total_minor employee_minor')
            total,employee=_int(item['total_minor']),_int(item['employee_minor'])
            if employee>total or p['scheme']!='regular_transition' and employee!=total:raise Problem(400,'Historische AN-Basis widerspricht der Beitragsbasis.')
            intervals=[];seen=set()
            if not isinstance(item['eligible_intervals'],list) or len(item['eligible_intervals'])>100:raise Problem(400,'Konkrete SV-Intervalle erforderlich.')
            for interval in item['eligible_intervals']:
                _shape(interval,'start end legal_reason evidence_ref');_ref(interval['evidence_ref'])
                current=set(dates(interval['start'],interval['end']))
                if (min(current)<max(first.isoformat(),employed.isoformat()) or max(current)>min(last.isoformat(),end.isoformat() if end else last.isoformat())
                        or current&seen or interval['legal_reason'] not in ('paid_employment','continued_section_7_3','contributory_section_23c','short_time_contributory')):
                    raise Problem(400,'Historische SV-Zeiten überschneiden sich oder widersprechen Beschäftigung und Rechtsgrund.')
                seen.update(current);intervals.append(dict(interval))
            if total and not seen:raise Problem(400,'Beitragsbasis ohne tatsächliche SV-Zeit.')
            cap=YEAR_RULES[first.year]['health_cap_minor' if branch in ('health','care') else 'pension_cap_minor']
            days=30 if len(seen)==calendar.monthrange(first.year,first.month)[1] else len(seen)
            if total>_round(Decimal(cap)*days/360):raise Problem(400,'Historische Beitragsbasis überschreitet ihre belegte Teil-BBG.')
            if p['scheme']=='commercial_minijob' and branch in ('care','unemployment') and (total or seen):raise Problem(400,'Gewerblicher Minijob hat keine eigenständige PV-/AV-Beitragsperiode.')
            if p['health_insurance']=='private' and branch in ('health','care') and (total or seen):raise Problem(400,'Private KV/PV darf keine gesetzlichen Beitragsbasen erzeugen.')
            branches[branch]=dict(eligible_intervals=sorted(intervals,key=lambda v:v['start']),total_minor=total,employee_minor=employee)
        if not re.fullmatch('[a-f0-9]{64}',value['original_rule_hash'] or ''):raise Problem(400,'Originalen Regel-/Verfahrenshash des geprüften Vortrags angeben.')
        note(value['section_key'],'Nachgewiesener Beschäftigungsabschnitt');note(value['original_rule_version'],'Originalverfahren')
        note(value['original_payroll_reference'],'Ursprüngliche Abrechnungsreferenz')
        normalized=dict(value,profile=p,branches=branches,running_receipts=sorted(receipts,key=lambda item:(item['received_on'],item['evidence_ref']['id'])),document_refs=refs(value['document_refs'],minimum=1))
    elif kind=='imported_one_off':
        _shape(value,common+' receipt_date amount_minor assigned_period_ref section_key bases_minor original_reference document_refs')
        received=_date(value['receipt_date'])
        if received.year not in YEAR_RULES:raise Problem(400,'Ein belegter Zufluss aus 2025 oder 2026 ist erforderlich.')
        _int(value['amount_minor'],1);_ref(value['assigned_period_ref']);_shape(value['bases_minor'],' '.join(BRANCHES))
        for amount in value['bases_minor'].values():_int(amount,0,value['amount_minor'])
        note(value['section_key'],'Beschäftigungsabschnitt');note(value['original_reference'],'Originaler Einmalbezug')
        normalized=dict(value,document_refs=refs(value['document_refs'],minimum=1))
    elif kind=='annual_basis':
        _shape(value,common+' year coverage_to as_of_date payroll_run_refs payroll_payment_refs imported_period_refs imported_one_off_refs current_calculation_case_ref gaps completeness_confirmed')
        _int(value['year'],2025,2026);through=_date(value['coverage_to'])
        as_of=_date(value['as_of_date'])
        if through.year!=value['year'] or value['completeness_confirmed'] is not True:raise Problem(400,'Vollständigen tatsächlichen Jahreszeitraum ausdrücklich bestätigen.')
        if as_of.year not in YEAR_RULES or value['as_of_date'][:7]<value['coverage_to'][:7]:raise Problem(400,'Jahresbasis benötigt den tatsächlichen Prüf-/Zuflussstichtag nach ihren abgeschlossenen Monaten.')
        normalized=dict(value)
        for field in ('payroll_run_refs','payroll_payment_refs','imported_period_refs','imported_one_off_refs'):normalized[field]=refs(value[field])
        if value['current_calculation_case_ref'] is not None:_ref(value['current_calculation_case_ref'])
        if not isinstance(value['gaps'],list) or len(value['gaps'])>366:raise Problem(400,'Belegte Lücken als eindeutige Zeiträume angeben.')
        gaps=[]
        for gap in value['gaps']:
            _shape(gap,'start end reason evidence_ref');_ref(gap['evidence_ref']);dates(gap['start'],gap['end'])
            if not f"{value['year']}-01-01"<=gap['start']<=gap['end']<=value['coverage_to'] or gap['reason'] not in ('not_employed','contribution_free_interruption'):
                raise Problem(400,'Jede Jahreslücke benötigt ihren belegten Zeitraum und Rechtsgrund.')
            gaps.append(dict(gap))
        normalized['gaps']=sorted(gaps,key=lambda item:item['start'])
    elif kind=='one_off_earning':
        _shape(value,common+' claim_key claim_reference planned_receipt_date amount_minor tax_classification social_classification section_key employment_terms_refs claim_periods document_refs')
        _ref(value['claim_key']);received=_date(value['planned_receipt_date']);_int(value['amount_minor'],1)
        note(value['claim_reference'],'Eindeutige ursprüngliche Anspruchsposition')
        if received.year!=2026:raise Problem(400,'Dieser neue Einmalbezugsfall gilt für geplanten Zufluss 2026.')
        if value['tax_classification']!='other_payment' or value['social_classification']!='one_off_remuneration':
            raise Problem(400,'Dieser Zweig verarbeitet echte sonstige Bezüge und echtes einmaliges Arbeitsentgelt; laufende Nachzahlungen benötigen ihre eigene Zuordnung.')
        note(value['section_key'],'Nachgewiesener Anspruchsabschnitt')
        if value['section_key'] not in ('regular','minijob'):raise Problem(400,'Tatsächlichen regulären oder geringfügigen Anspruchsabschnitt auswählen.')
        if not isinstance(value['claim_periods'],list) or not 1<=len(value['claim_periods'])<=100:raise Problem(400,'Tatsächliche Anspruchszeiträume erforderlich.')
        periods=[]
        for period in value['claim_periods']:
            _shape(period,'start end evidence_ref');_ref(period['evidence_ref']);dates(period['start'],period['end']);periods.append(dict(period))
        normalized=dict(value,employment_terms_refs=refs(value['employment_terms_refs'],minimum=1),
            claim_periods=sorted(periods,key=lambda item:item['start']),document_refs=refs(value['document_refs'],minimum=1))
    else:
        _shape(value,common+' annual_basis_ref receipt_date remaining_periods previous_employers no_previous_employer_ref identity_ref current_one_off_ref other_tax_receipt_refs')
        _ref(value['annual_basis_ref']);_ref(value['identity_ref']);_ref(value['current_one_off_ref']);received=_date(value['receipt_date'])
        if received.year!=2026:raise Problem(400,'Jahressteuervorschau gehört zum Zuflussjahr 2026.')
        normalized=dict(value,other_tax_receipt_refs=refs(value['other_tax_receipt_refs']))
        if not isinstance(value['remaining_periods'],list) or len(value['remaining_periods'])>12:raise Problem(400,'Belegte verbleibende Monatsquellen erforderlich.')
        periods=[]
        for item in value['remaining_periods']:
            _shape(item,'month employment_terms_ref agreement_refs work_schedule_ref')
            if not isinstance(item['month'],str) or not re.fullmatch('2026-(0[1-9]|1[0-2])',item['month']):raise Problem(400,'Verbleibenden Kalendermonat 2026 angeben.')
            _ref(item['employment_terms_ref'])
            if item['work_schedule_ref'] is not None:_ref(item['work_schedule_ref'])
            periods.append(dict(item,agreement_refs=refs(item['agreement_refs'],minimum=1)))
        normalized['remaining_periods']=sorted(periods,key=lambda item:item['month'])
        previous=[]
        if not isinstance(value['previous_employers'],list) or len(value['previous_employers'])>30:raise Problem(400,'Belegte frühere Arbeitgeberzeiträume angeben.')
        for item in value['previous_employers']:
            _shape(item,'employer_name employer_tax_number start end running_taxable_minor other_paid_minor evidence_ref')
            note(item['employer_name'],'Früherer Arbeitgeber');note(item['employer_tax_number'],'Frühere Arbeitgeber-Steuernummer')
            _ref(item['evidence_ref']);_int(item['running_taxable_minor']);_int(item['other_paid_minor']);dates(item['start'],item['end'])
            if item['start']<'2026-01-01' or item['end']>value['receipt_date']:raise Problem(400,'Vorbezug muss im tatsächlichen Zuflussjahr vorliegen.')
            previous.append(dict(item))
        if bool(previous)==(value['no_previous_employer_ref'] is not None):raise Problem(400,'Entweder belegte Vorbezüge oder ausdrücklicher Nachweis ohne frühere Arbeitgeber erforderlich.')
        if value['no_previous_employer_ref'] is not None:_ref(value['no_previous_employer_ref'])
        normalized['previous_employers']=sorted(previous,key=lambda item:(item['start'],item['employer_tax_number']))
        for left,right in zip(normalized['previous_employers'],normalized['previous_employers'][1:]):
            if right['start']<=left['end']:raise Problem(409,'Überlappende Vorarbeitgeberzeiträume benötigen ihre gesonderte Steuerzuordnung; ein Originalbezug darf nicht doppelt zählen.')
    _ref(normalized['employer_identity_ref']);note(normalized['verification_note'],'Prüfvermerk')
    return normalized


def employer_key(identity):
    d=identity['details']
    return sha(dict(employer_tax_number=re.sub('[ /]','',d['employer_tax_number']),employer_name=d['employer_name']))


def running_tax_year(period_end,received_on):
    """LStR R39b.2(1): a prior-year running wage within three January weeks.

    A later prior-year arrears receipt is a separate tax-classification case,
    not automatically one-off social remuneration under SGBIV23a.
    """
    end,received=_date(period_end),_date(received_on)
    if received.year==end.year:return end.year
    if received.year==end.year+1 and received.month==1 and received.day<=21:return end.year
    raise Problem(409,'Späterer Vorjahreslohn benötigt seine eigene belegte Steuerzuordnung; er ist kein automatisch sozialversicherungspflichtiger Einmalbezug.')


def imported_period_projection(record):
    d=record['details'];ref=reference(record)
    return dict(source_ref=ref,part_key='imported',section_key=d['section_key'],start=d['period_start'],end=d['period_end'],
        branches={key:dict(contributed_minor=value['total_minor'],eligible_intervals=[
            dict(start=interval['start'],end=interval['end'],legal_reason=interval['legal_reason'],source_ref=interval['evidence_ref'])
            for interval in value['eligible_intervals']]) for key,value in d['branches'].items()})


def build_annual_plan(snapshot,*,rule_version=ANNUAL_BASIS_VERSION):
    if rule_version!=ANNUAL_BASIS_VERSION:raise Problem(400,'Unbekannte gespeicherte Jahresquellenregel.')
    kind=snapshot['kind'];d=snapshot['details'];identity=snapshot['identity'];employee=snapshot['employee']
    common=dict(schema_version=1,rule_version=rule_version,employee_id=employee['id'],employer_key=employer_key(identity),source_hash=sha(snapshot))
    if kind=='imported_period':
        plan=dict(common,kind=kind,period_start=d['period_start'],period_end=d['period_end'],
            social_year=int(d['period_start'][:4]),running_gross_minor=d['running_gross_minor'],running_taxable_minor=d['running_taxable_minor'],
            original_rule_version=d['original_rule_version'],original_rule_hash=d['original_rule_hash'],
            source_documents_verified_by_user=True,original_tax_not_recalculated=True)
    elif kind=='imported_one_off':
        period=snapshot['assigned_period']
        if period['details']['section_key']!=d['section_key']:raise Problem(409,'Einmalbezug und ursprünglicher Beschäftigungsabschnitt widersprechen sich.')
        if employer_key(period['sources']['identity'])!=common['employer_key']:raise Problem(409,'Zugeordneter Zeitraum gehört zu einer anderen Arbeitgeberidentität.')
        end=period['details']['period_end']
        if end[:7]>d['receipt_date'][:7]:raise Problem(400,'Einmalbezug ist einer zukünftigen Periode zugeordnet.')
        plan=dict(common,kind=kind,tax_year=int(d['receipt_date'][:4]),social_year=int(end[:4]),
            assigned_period_end=end,bases_minor=d['bases_minor'],amount_minor=d['amount_minor'],section_key=d['section_key'])
    elif kind=='one_off_earning':
        plan=dict(common,kind=kind,planned_receipt_date=d['planned_receipt_date'],amount_minor=d['amount_minor'],
            tax_classification=d['tax_classification'],social_classification=d['social_classification'],
            section_key=d['section_key'],actual_payment_created=False,statutory_transmitted=False)
    elif kind=='annual_basis':
        periods=[];coverage=set();bindings=[];taxable=0;oneoffs=[];unpaid_tax_sources=[]
        def cover(start,end,binding):
            values=set(dates(start,end))
            if min(values)<f"{d['year']}-01-01" or max(values)>d['coverage_to'] or coverage&values:raise Problem(409,'Jahresquellen überlappen oder liegen außerhalb des bestätigten Zeitraums.')
            coverage.update(values);bindings.append(dict(start=start,end=end,source=binding))
        for record in snapshot['imported_periods']:
            part=imported_period_projection(record);periods.append(part)
            cover(part['start'],part['end'],reference(record))
            receipts=[item for item in record['details']['running_receipts'] if item['received_on']<=d['as_of_date']]
            paid=sum(item['taxable_minor'] for item in receipts)
            taxable+=sum(item['taxable_minor'] for item in receipts if running_tax_year(record['details']['period_end'],item['received_on'])==d['year'])
            if paid!=record['details']['running_taxable_minor']:unpaid_tax_sources.append(reference(record))
        for projected in snapshot['internal_periods']:
            if projected['coverage_start'] is not None:cover(projected['coverage_start'],projected['coverage_end'],projected['source_ref'])
            periods.extend(projected['periods']);taxable+=projected['running_taxable_minor']
            if projected['tax_receipt_status']=='unproven':unpaid_tax_sources.append(projected['source_ref'])
        for gap in d['gaps']:cover(gap['start'],gap['end'],dict(kind=gap['reason'],reference=gap['evidence_ref']))
        expected=set(dates(f"{d['year']}-01-01",d['coverage_to']))
        if coverage!=expected:raise Problem(409,'Jahresquelle lässt ungeklärte Kalendertage aus; fehlende Monate sind kein Nullbezug.')
        for record in snapshot['imported_one_offs']:
            p=record['plan']
            if record['details']['receipt_date']>d['as_of_date']:raise Problem(409,'Späterer Einmalzufluss darf frühere SV-Luft nicht verbrauchen.')
            if p['social_year']!=d['year'] or p['assigned_period_end']>d['coverage_to']:raise Problem(409,'Früherer Einmalbezug liegt außerhalb der Jahreszuordnung.')
            if not any(value['source_ref']==record['details']['assigned_period_ref'] for value in periods):raise Problem(409,'Ursprüngliche Zuordnungsperiode des früheren Einmalbezugs fehlt.')
            oneoffs.append(dict(source_ref=reference(record),section_key=p['section_key'],assigned_period_end=p['assigned_period_end'],bases_minor=p['bases_minor']))
        internal_other=0
        for projected in snapshot['internal_periods']:
            bonus=projected.get('one_off_payment')
            if bonus is None:continue
            if bonus['receipt_date']>d['as_of_date']:raise Problem(409,'Späterer interner Einmalzufluss gehört nicht zum Jahresstichtag.')
            if bonus['tax_year']==d['year']:internal_other+=bonus['amount_minor']
            if bonus['social_year']!=d['year']:continue
            if bonus['assigned_period_end']>d['coverage_to'] or not any(
                    value['source_ref']==bonus['assigned_period_ref'] and value['part_key']==bonus['assigned_part_key']
                    and value['end']==bonus['assigned_period_end'] for value in periods):
                raise Problem(409,'Die tatsächliche Zuordnungsperiode des internen Einmalbezugs fehlt in der Jahresquelle.')
            oneoffs.append({key:bonus[key] for key in ('source_ref','section_key','assigned_period_end','bases_minor')})
        projection=dict(year=d['year'],employee_id=employee['id'],employer_key=common['employer_key'],coverage_to=d['coverage_to'],
            periods=sorted(periods,key=lambda value:(value['start'],value['part_key'])),prior_one_offs=oneoffs)
        # Temporary ref is only for arithmetic validation; it is not persisted as
        # an accepted fact reference. The resolver supplies the real saved ref.
        temporary=dict(id='0'*32,revision=1,content_hash=common['source_hash'])
        sections=sorted({value['section_key'] for value in periods})
        room={section:annual_social_room(dict(projection,source_ref=temporary),through=d['coverage_to'],section_key=section)['branches'] for section in sections}
        plan=dict(common,kind=kind,year=d['year'],coverage_to=d['coverage_to'],as_of_date=d['as_of_date'],projection=projection,section_rooms=room,
            running_taxable_minor=taxable,earlier_other_taxable_minor=internal_other+sum(record['details']['amount_minor'] for record in snapshot['imported_one_offs'] if record['plan']['tax_year']==d['year']),
            coverage=sorted(bindings,key=lambda value:value['start']),unpaid_tax_sources=unpaid_tax_sources,
            contains_planned_current_period=d['current_calculation_case_ref'] is not None)
    else:
        history=snapshot['annual_basis']['plan'];earning=snapshot['current_one_off']['plan'];identity=snapshot['tax_identity']
        if history['unpaid_tax_sources']:raise Problem(409,'Frühere laufende Steuerbezüge benötigen ihre tatsächlichen Zuflussbelege; fehlender Zufluss ist kein Nullwert.')
        if history['year']!=2026 or earning['planned_receipt_date']!=d['receipt_date']:raise Problem(409,'Steuervorschau und Jahres-/Anspruchsquelle gehören nicht zum selben Zuflussfall.')
        if history['as_of_date']!=d['receipt_date']:raise Problem(409,'Steuervorschau muss genau den belegten Zuflussstichtag verwenden.')
        if history['coverage_to'][:7]!=d['receipt_date'][:7]:raise Problem(409,'Die Jahresbasis muss den laufenden Zuflussmonat enthalten.')
        months=[item['month'] for item in snapshot['future_earnings']]
        expected=[f'2026-{month:02}' for month in range(int(history['coverage_to'][5:7])+1,13)]
        if months!=expected:raise Problem(409,'Alle verbleibenden Kalendermonate bis Dezember ausdrücklich belegen.')
        prior=sum(item['running_taxable_minor']+item['other_paid_minor'] for item in d['previous_employers'])
        own_days={day for period in history['projection']['periods'] for branch in period['branches'].values()
                  for interval in branch['eligible_intervals'] for day in dates(interval['start'],interval['end'])}
        for item in d['previous_employers']:
            if re.sub('[ /]','',item['employer_tax_number'])==re.sub('[ /]','',snapshot['identity']['details']['employer_tax_number']):raise Problem(409,'Eigene Arbeitgeberbezüge dürfen nicht nochmals als Vorarbeitgeber erscheinen.')
            if own_days.intersection(dates(item['start'],item['end'])):raise Problem(409,'Zeitgleiche Arbeitgeberbezüge benötigen eine gesonderte belegte Steuerzuordnung.')
        additional=snapshot['other_tax_receipts_minor']
        total=history['running_taxable_minor']+history['earlier_other_taxable_minor']+prior+additional+sum(item['gross_minor'] for item in snapshot['future_earnings'])
        plan=dict(common,kind=kind,receipt_date=d['receipt_date'],annual_pay_before_minor=total,one_off_minor=earning['amount_minor'],
            annual_allowance_minor=identity['details']['tax_allowance_yearly_minor'],annual_addition_minor=identity['details']['tax_addition_yearly_minor'],
            forecast_future_minor=sum(item['gross_minor'] for item in snapshot['future_earnings']),previous_employer_minor=prior,
            additional_evidenced_tax_receipts_minor=additional,
            current_one_off_excluded=True,actual_payment_created=False)
    return dict(plan,plan_hash=sha(plan),can_confirm=True)
