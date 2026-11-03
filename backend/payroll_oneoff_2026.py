"""Pure, source-bound social one-off primitives for 2026 receipts.

Inputs are normalized historical period facts, never free annual totals. Their
canonical database/original-document validation belongs to the private annual
basis resolver. This new component does not alter any stored payroll v1-v5.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
from pathlib import Path
import re

from core import Problem

SOCIAL_ONEOFF_VERSION='de_social_oneoff_2025_2026_v1'
BRANCHES=('health','care','pension','unemployment')
YEAR_RULES={
    2025:dict(health_cap_minor=6615000,pension_cap_minor=9660000,minijob_minor=55600,transition_factor='0.6683'),
    2026:dict(health_cap_minor=6975000,pension_cap_minor=10140000,minijob_minor=60300,transition_factor='0.6619')}
SOURCES={
    'allocation':'https://www.gesetze-im-internet.de/sgb_4/__23a.html',
    'interpretation':'https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/01_GRA_SGB/04_SGB_IV/pp_0001_25/gra_sgb004_p_0023a.html',
    'caps_2025':'https://www.gesetze-im-internet.de/svbezgrv_2025/BJNR16D0A0024.html',
    'care_2025':'https://www.gesetze-im-internet.de/pbav_2025/BJNR1BE0A0024.html',
    'factor_2025':'https://www.bmas.de/DE/Service/Presse/Pressemitteilungen/2024/das-aendert-sich-im-neuen-jahr.html',
    'minijob_2026':'https://www.deutsche-rentenversicherung.de/SharedDocs/Downloads/DE/Fachliteratur_Kommentare_Gesetzestexte/summa_summarum/rundschreiben/2026/geringfuegigkeits-richtlinien.pdf?__blob=publicationFile&v=2',
    'transition':'https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/05_Normen_und_Vertraege/10_Rundschreiben_SpV/12_gleitzone_uebergangsbereich/74_rssp_2022_12_20.pdf?__blob=publicationFile&v=2'}


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


SOCIAL_ONEOFF_HASH=_sha(dict(version=SOCIAL_ONEOFF_VERSION,rules=YEAR_RULES,sources=SOURCES,
    module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


def _shape(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys.split()):
        raise Problem(400,'Jahresquelle benötigt genau die dokumentierten Felder.')


def _int(value,low=0,high=10**12):
    if type(value) is not int or not low<=value<=high:raise Problem(400,'Ungültiger ganzzahliger Jahresquellenwert.')
    return value


def _date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise Problem(400,'Genaues Datum erforderlich.')
    try:return date.fromisoformat(value)
    except ValueError:raise Problem(400,'Ungültiges Datum.')


def _ref(value):
    _shape(value,'id revision content_hash')
    if not isinstance(value['id'],str) or not re.fullmatch('[a-f0-9]{32}',value['id']):raise Problem(400,'Genaue Quellen-ID erforderlich.')
    _int(value['revision'],1)
    if not isinstance(value['content_hash'],str) or not re.fullmatch('[a-f0-9]{64}',value['content_hash']):raise Problem(400,'Genaue Quellenfassung erforderlich.')
    return value


def _round(value):return int(value.quantize(Decimal(1),rounding=ROUND_HALF_UP))


def _range(start,end):
    while start<=end:
        yield start
        start+=timedelta(days=1)


def _sv_days(days):
    months={}
    for value in days:months.setdefault((value.year,value.month),set()).add(value.day)
    return sum(30 if len(values)==calendar.monthrange(year,month)[1] else len(values)
               for (year,month),values in months.items())


def annual_social_room(basis,*,through,section_key):
    """Derive branch room from exact period intervals and prior allocations.

    Periods bind an insurance section (regular and minijob origins must not be
    mixed). ``eligible_intervals`` are legal SV intervals, including evidenced
    continued employment under §7(3), not merely dates with positive pay.
    Calendar coverage, legal reasons and originals are verified by the API.
    """
    _shape(basis,'year employee_id employer_key coverage_to periods prior_one_offs source_ref')
    year=_int(basis['year'],2025,2026);end=_date(through);coverage=_date(basis['coverage_to'])
    _ref(basis['source_ref'])
    if end.year!=year or coverage.year!=year or end>coverage:raise Problem(409,'Die Jahresquelle deckt den Zuordnungszeitraum nicht ab.')
    if not isinstance(section_key,str) or not section_key or len(section_key)>100:raise Problem(400,'Belegter Beschäftigungsabschnitt erforderlich.')
    if not isinstance(basis['periods'],list) or len(basis['periods'])>1000 or not isinstance(basis['prior_one_offs'],list) or len(basis['prior_one_offs'])>1000:
        raise Problem(400,'Begrenzte konkrete Perioden- und Einmalbezugsquellen erforderlich.')
    dates={branch:set() for branch in BRANCHES};used={branch:0 for branch in BRANCHES};seen=set();bindings=[]
    for period in basis['periods']:
        _shape(period,'source_ref part_key section_key start end branches')
        ref=_ref(period['source_ref']);start,last=_date(period['start']),_date(period['end'])
        if start.year!=year or last.year!=year or start>last or last>coverage:raise Problem(400,'Vortragsperiode liegt außerhalb des belegten Jahres.')
        if not isinstance(period['part_key'],str) or not period['part_key'] or len(period['part_key'])>100:raise Problem(400,'Eindeutiger Periodenabschnitt erforderlich.')
        key=(ref['id'],ref['revision'],period['part_key'])
        if key in seen:raise Problem(400,'Eine konkrete Vortragsperiode darf nur einmal zählen.')
        seen.add(key);_shape(period['branches'],' '.join(BRANCHES))
        for branch in BRANCHES:
            item=period['branches'][branch];_shape(item,'eligible_intervals contributed_minor')
            _int(item['contributed_minor'])
            if not isinstance(item['eligible_intervals'],list) or len(item['eligible_intervals'])>100:raise Problem(400,'Belegte SV-Intervalle je Zweig erforderlich.')
            own=set()
            for interval in item['eligible_intervals']:
                _shape(interval,'start end legal_reason source_ref');_ref(interval['source_ref'])
                left,right=_date(interval['start']),_date(interval['end'])
                if not start<=left<=right<=last:raise Problem(400,'SV-Intervall liegt außerhalb seiner tatsächlichen Vortragsperiode.')
                if interval['legal_reason'] not in ('paid_employment','continued_section_7_3','contributory_section_23c','short_time_contributory'):
                    raise Problem(400,'SV-Intervall benötigt einen belegten gesetzlichen Grund.')
                values=set(_range(left,right))
                if own & values:raise Problem(400,'Doppelte SV-Zeiten innerhalb einer Vortragsperiode.')
                own.update(values)
            if item['contributed_minor'] and not own:raise Problem(400,'Laufende Beitragsbasis ohne zugehörige SV-Zeit.')
            if period['section_key']!=section_key or start>end:continue
            if last>end:raise Problem(409,'Die Zuordnung benötigt eine konkret abgeschlossene Teilperiode.')
            if dates[branch]&own:raise Problem(400,'Vortragsperioden zählen dieselben SV-Zeiten mehrfach.')
            dates[branch].update(own);used[branch]+=item['contributed_minor']
        if period['section_key']==section_key and last<=end:bindings.append(dict(source_ref=ref,part_key=period['part_key']))
    oneoff_ids=set()
    for item in basis['prior_one_offs']:
        _shape(item,'source_ref section_key assigned_period_end bases_minor');ref=_ref(item['source_ref'])
        if ref['id'] in oneoff_ids:raise Problem(400,'Ein früherer Einmalbezug darf nur in seiner wirksamen Fassung zählen.')
        oneoff_ids.add(ref['id']);assigned=_date(item['assigned_period_end'])
        if assigned.year!=year or assigned>coverage:raise Problem(400,'Früherer Einmalbezug gehört nicht zum belegten Jahreszeitraum.')
        _shape(item['bases_minor'],' '.join(BRANCHES))
        for branch in BRANCHES:_int(item['bases_minor'][branch])
        if item['section_key']==section_key and assigned<=end:
            for branch in BRANCHES:used[branch]+=item['bases_minor'][branch]
            bindings.append(dict(source_ref=ref,part_key='one_off'))
    result={}
    for branch in BRANCHES:
        count=_sv_days(dates[branch]);annual=YEAR_RULES[year]['health_cap_minor' if branch in ('health','care') else 'pension_cap_minor']
        cap=_round(Decimal(annual)*count/360)
        result[branch]=dict(sv_days=count,annual_cap_minor=annual,partial_cap_minor=cap,
            contributed_minor=used[branch],room_minor=max(0,cap-used[branch]))
    output=dict(year=year,employee_id=basis['employee_id'],employer_key=basis['employer_key'],
        through=through,section_key=section_key,branches=result,source_ref=basis['source_ref'],period_bindings=bindings)
    return dict(output,source_hash=_sha(dict(basis=basis,through=through,section_key=section_key)),
                rule_version=SOCIAL_ONEOFF_VERSION,rules_hash=SOCIAL_ONEOFF_HASH)


def select_one_off_assignment(*,receipt_date,amount_minor,current_room,previous_room,
        current_period_ref,previous_period_ref,mandatory_statutory_health,previous_year_employment):
    """Choose current/previous year from actual receipt and evidenced room.

    The resolver supplies the last actual current/prior assignment periods.
    Missing previous-year evidence is not evidence of no previous employment.
    """
    receipt=_date(receipt_date);_int(amount_minor,1)
    if receipt.year!=2026:raise Problem(400,'Dieser Zuordnungsstand verarbeitet tatsächliche Zuflüsse 2026.')
    if type(mandatory_statutory_health) is not bool or type(previous_year_employment) is not bool:
        raise Problem(400,'KV-Pflicht und belegte Vorjahresbeschäftigung ausdrücklich bestimmen.')
    if current_period_ref is not None:_ref(current_period_ref)
    if previous_period_ref is not None:_ref(previous_period_ref)
    if current_room is not None and (current_room['year']!=2026 or current_room['through'][:7]>receipt_date[:7]):
        raise Problem(400,'Aktuelle SV-Luft liegt nicht im zulässigen Zuordnungszeitraum.')
    if previous_room is not None and previous_room['year']!=2025:raise Problem(400,'Märzklausel benötigt eine tatsächliche 2025-Quelle.')
    branch='health' if mandatory_statutory_health else 'pension'
    room=current_room['branches'][branch]['room_minor'] if current_room else 0
    march=receipt.month<=3 and previous_year_employment and amount_minor>room
    if march:
        if previous_room is None or previous_period_ref is None:raise Problem(409,'Vorjahresperiode und tatsächliche SV-Luft 2025 fehlen für die Märzklausel.')
        chosen,period,reason=previous_room,previous_period_ref,'march_clause'
    elif current_room is not None:
        if current_period_ref is None:raise Problem(409,'Tatsächliche Zuordnungsperiode des laufenden Jahres fehlt.')
        chosen,period,reason=current_room,current_period_ref,'current_year_last_period'
    else:
        chosen,period,reason=None,None,'no_contributory_current_year_period'
    if current_room is not None and previous_room is not None and any(current_room[k]!=previous_room[k] for k in ('employee_id','employer_key','section_key')):
        raise Problem(400,'Vorjahres- und aktuelle Quelle gehören nicht zu derselben Person, Arbeitgeberidentität und Anspruchssektion.')
    bases={key:min(amount_minor,chosen['branches'][key]['room_minor']) if chosen else 0 for key in BRANCHES}
    return dict(tax_year=2026,social_year=chosen['year'] if chosen else 2026,reason=reason,
        march_clause=march,decisive_branch=branch,assigned_period_ref=period,
        assigned_period_end=chosen['through'] if chosen else None,bases_minor=bases,
        annual_basis_ref=chosen['source_ref'] if chosen else None,
        source_hash=_sha(dict(receipt_date=receipt_date,amount_minor=amount_minor,current=current_room,
            previous=previous_room,current_period_ref=current_period_ref,previous_period_ref=previous_period_ref,
            mandatory_statutory_health=mandatory_statutory_health,previous_year_employment=previous_year_employment)))


def transition_bases(*,year,actual_minor,comparison_minor=None,numerator=1,denominator=1):
    """2025/2026 midijob bases, final cent rounding only.

    comparison_minor explicitly represents lost regular pay plus the one-off in
    a no-running-pay month; it determines whether the upper bound is crossed.
    The annual forecast, not this monthly amount, establishes midijob status.
    """
    _int(year,2025,2026);_int(actual_minor);_int(numerator,1);_int(denominator,1)
    if numerator>denominator:raise Problem(400,'Belegte Teilmonatsquote darf eins nicht überschreiten.')
    if comparison_minor is not None:_int(comparison_minor)
    with localcontext() as context:
        context.prec=50
        fraction=Decimal(numerator)/denominator
        actual=Decimal(actual_minor)/fraction
        comparison=Decimal(comparison_minor) if comparison_minor is not None else actual
        if comparison<actual:raise Problem(400,'Ausfallvergleich darf das tatsächliche hochgerechnete Entgelt nicht unterschreiten.')
        lower=Decimal(YEAR_RULES[year]['minijob_minor']);factor=Decimal(YEAR_RULES[year]['transition_factor'])
        if comparison>200000:total=employee=actual;method='above_upper_bound'
        elif actual<=lower:total=actual*factor;employee=Decimal(0);method='below_lower_bound'
        else:
            total=factor*lower+(Decimal(200000)/(200000-lower)-lower/(200000-lower)*factor)*(actual-lower)
            employee=Decimal(200000)/(200000-lower)*(actual-lower);method='transition'
        return dict(total_minor=_round(total*fraction),employee_minor=_round(employee*fraction),
                    method=method,year=year,numerator=numerator,denominator=denominator)


def classify_regular_pay(*,year,months):
    """Determine mini/midi/ordinary status from explicitly sourced forecast months.

    The resolver establishes the real forecast duration and excludes evidence-
    backed non-recurring/unforeseeable items. A forecast is not a payment claim.
    """
    _int(year,2025,2026)
    if not isinstance(months,list) or not 1<=len(months)<=12:raise Problem(400,'Ein bis zwölf belegte Prognosemonate erforderlich.')
    total=0;previous=None;seen=set()
    for month in months:
        _shape(month,'month earnings source_ref');_ref(month['source_ref'])
        value=month['month']
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}',value):raise Problem(400,'Genauer Prognosemonat erforderlich.')
        current=_date(value+'-01')
        if previous is not None and (current.year*12+current.month)!=(previous.year*12+previous.month+1):
            raise Problem(400,'Prognosemonate müssen lückenlos in tatsächlicher Reihenfolge stehen.')
        previous=current
        if not isinstance(month['earnings'],list) or len(month['earnings'])>100:raise Problem(400,'Belegte Entgeltbestandteile erforderlich.')
        for earning in month['earnings']:
            _shape(earning,'source_ref amount_minor kind');ref=_ref(earning['source_ref']);_int(earning['amount_minor'])
            if earning['kind'] not in ('running','foreseeable_one_off'):raise Problem(400,'Prognose nur aus laufenden und vorhersehbaren einmaligen Ansprüchen bilden.')
            key=(value,ref['id'],ref['revision'],earning['kind'])
            if key in seen:raise Problem(400,'Derselbe Prognoseanspruch darf nur einmal zählen.')
            seen.add(key);total+=earning['amount_minor']
    count=len(months);lower=YEAR_RULES[year]['minijob_minor']
    classification='minijob' if total<=lower*count else 'midijob' if total<=200000*count else 'regular'
    return dict(year=year,months=count,forecast_total_minor=total,
        monthly_average_minor=_round(Decimal(total)/count),classification=classification,
        monthly_limit_minor=lower,source_hash=_sha(dict(year=year,months=months)),
        rule_version=SOCIAL_ONEOFF_VERSION,rules_hash=SOCIAL_ONEOFF_HASH)


def _percent(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,2}(?:\.\d{1,3})?',value):
        raise Problem(400,'Belegten historischen Prozentsatz als Dezimaltext angeben.')
    result=Decimal(value)
    if result>30:raise Problem(400,'Historischer Beitragssatz außerhalb des zulässigen Bereichs.')
    return result


def _portion(amount,rate):return _round(Decimal(amount)*Decimal(rate)/100)


def assess_social_contributions(*,year,branch_bases,profile,reduced=False):
    """Calculate actual 2025/2026 contributions from source-resolved bases.

    The historical assignment profile supplies the actual fund contribution,
    insurance branches and child status. No current rate or average-rate fallback.
    Both years use PV 3.6% under PBAV 2025, not the superseded statute's 3.4%.
    This primitive deliberately excludes U1/U2: their ongoing assessment is a
    separate recalculation when a bonus crosses the transition upper bound.
    """
    _int(year,2025,2026);_shape(branch_bases,' '.join(BRANCHES))
    _shape(profile,'source_ref health_additional_percent saxony childless_surcharge care_child_discounts')
    _ref(profile['source_ref']);additional=_percent(profile['health_additional_percent'])
    if any(type(profile[key]) is not bool for key in ('saxony','childless_surcharge')) or type(reduced) is not bool:
        raise Problem(400,'Historische Pflege- und Beitragsmerkmale ausdrücklich bestimmen.')
    discounts=_int(profile['care_child_discounts'],0,4)
    if discounts and profile['childless_surcharge']:raise Problem(400,'Kinderlosenzuschlag und Kinderabschläge widersprechen sich.')
    for item in branch_bases.values():
        _shape(item,'total_minor employee_minor');_int(item['total_minor']);_int(item['employee_minor'])
        if item['employee_minor']>item['total_minor'] or not reduced and item['employee_minor']!=item['total_minor']:
            raise Problem(400,'Arbeitnehmerbasis widerspricht der belegten Beitragsbasis.')
    own={};firm={}
    for key,branch,rate in (('health_general','health',Decimal('7.3')),
            ('health_additional','health',additional/2),('pension','pension',Decimal('9.3')),
            ('unemployment','unemployment',Decimal('1.3'))):
        total,employee=branch_bases[branch]['total_minor'],branch_bases[branch]['employee_minor']
        own[key]=_portion(employee,rate)
        firm[key]=2*_portion(total,rate)-own[key] if reduced else _portion(total,rate)
    total,employee=branch_bases['care']['total_minor'],branch_bases['care']['employee_minor']
    theoretical=_portion(employee,'2.3' if profile['saxony'] else '1.8')
    firm['care']=2*_portion(total,'1.8')-theoretical if reduced else _portion(total,'1.3' if profile['saxony'] else '1.8')
    surcharge=_portion(total,'0.6') if profile['childless_surcharge'] else 0
    discount=_portion(employee,Decimal('0.25')*discounts)
    own['care']=theoretical+surcharge-discount
    return dict(year=year,employee_contributions=own,employer_contributions=firm,
        employee_total_minor=sum(own.values()),employer_total_minor=sum(firm.values()),
        insolvency_minor=_portion(branch_bases['pension']['total_minor'],'0.15'),
        care_adjustments=dict(employee_before_adjustments_minor=theoretical,
            childless_surcharge_minor=surcharge,children_discount_minor=discount),
        branch_bases=branch_bases,profile_ref=profile['source_ref'],
        rule_version=SOCIAL_ONEOFF_VERSION,rules_hash=SOCIAL_ONEOFF_HASH)


def calculate_regular_one_off_contributions(*,assignment,profile):
    """Contributions for an ordinary, individually insured assignment section."""
    _shape(assignment['bases_minor'],' '.join(BRANCHES))
    bases={key:dict(total_minor=_int(value),employee_minor=value) for key,value in assignment['bases_minor'].items()}
    result=assess_social_contributions(year=assignment['social_year'],branch_bases=bases,profile=profile)
    return dict(result,assignment=assignment,employer_levies=dict(u1=0,u2=0,insolvency=result['insolvency_minor']),
                source_hash=_sha(dict(assignment=assignment,profile=profile)))


def reassess_transition_one_off(*,year,running_minor,bonus_minor,profile,u1_percent,u2_percent,
        original_assessment,comparison_minor=None,numerator=1,denominator=1):
    """Recalculate the assigned midijob period and return the actual difference.

    Inputs are the concrete period, its previous calculation and allocated bonus.
    The annual-room resolver must establish that this bonus is fully contributory
    in all four branches. Capped, mixed-insurance or multiple-employer cases need
    their respective source composition rather than calling this homogeneous helper.
    A crossed 2,000-EUR boundary changes the ongoing U1/U2 basis as well (GR2022
    example27); it never includes the bonus itself in U1/U2.
    """
    _int(running_minor);_int(bonus_minor,1);u1=_percent(u1_percent);u2=_percent(u2_percent)
    before_base=transition_bases(year=year,actual_minor=running_minor,numerator=numerator,denominator=denominator)
    after_base=transition_bases(year=year,actual_minor=running_minor+bonus_minor,
        comparison_minor=comparison_minor,numerator=numerator,denominator=denominator)
    def assessment(base):
        branches={key:dict(total_minor=base['total_minor'],employee_minor=base['employee_minor']) for key in BRANCHES}
        return assess_social_contributions(year=year,branch_bases=branches,profile=profile,reduced=base['method']!='above_upper_bound')
    before=assessment(before_base);after=assessment(after_base)
    if original_assessment!=before:raise Problem(409,'Die konkrete Vorberechnung der Zuordnungsperiode widerspricht der historischen Quelle.')
    ongoing_before=before_base['total_minor']
    ongoing_after=running_minor if after_base['method']=='above_upper_bound' else ongoing_before
    own={key:after['employee_contributions'][key]-before['employee_contributions'][key] for key in before['employee_contributions']}
    firm={key:after['employer_contributions'][key]-before['employer_contributions'][key] for key in before['employer_contributions']}
    levies=dict(u1=_portion(ongoing_after,u1)-_portion(ongoing_before,u1),
               u2=_portion(ongoing_after,u2)-_portion(ongoing_before,u2),
               insolvency=after['insolvency_minor']-before['insolvency_minor'])
    return dict(year=year,before=before,after=after,transition_before=before_base,transition_after=after_base,
        employee_contributions=own,employer_contributions=firm,employer_levies=levies,
        employee_total_minor=sum(own.values()),employer_total_minor=sum(firm.values()),
        additional_contributed_bases_minor={key:after['branch_bases'][key]['total_minor']-before['branch_bases'][key]['total_minor'] for key in BRANCHES},
        u1_u2_ongoing_basis_before_minor=ongoing_before,u1_u2_ongoing_basis_after_minor=ongoing_after,
        source_hash=_sha(dict(year=year,running_minor=running_minor,bonus_minor=bonus_minor,profile=profile,
            u1_percent=u1_percent,u2_percent=u2_percent,original_assessment=original_assessment,
            comparison_minor=comparison_minor,numerator=numerator,denominator=denominator)),
        rule_version=SOCIAL_ONEOFF_VERSION,rules_hash=SOCIAL_ONEOFF_HASH)


def assess_minijob_unforeseen_month(*,year,month,total_minor,annual_limit_exceeded,
        unforeseen,history,source_ref):
    """§8(1b): actual total <= twice limit, at most two exception months/year.

    History contains every preceding eleven calendar months, including explicit
    no-employment/ordinary months. ``exception_used`` means an unforeseen excess
    which also exceeded the regular annual limit, not every high seasonal month.
    The private resolver binds these classifications to original assessments.
    """
    _int(year,2025,2026);_int(total_minor);_ref(source_ref)
    current=_date(month+'-01')
    if current.year!=year:raise Problem(400,'Prüfmonat gehört nicht zum angegebenen Grenzwertjahr.')
    if any(type(value) is not bool for value in (annual_limit_exceeded,unforeseen)):
        raise Problem(400,'Belegte Jahresüberschreitung und Unvorhersehbarkeit erforderlich.')
    if not isinstance(history,list) or len(history)!=11:raise Problem(409,'Die elf vorausgehenden Prüfmonate müssen lückenlos belegt sein.')
    count=0
    for offset,item in zip(range(-11,0),history):
        _shape(item,'month exception_used source_ref');_ref(item['source_ref'])
        absolute=current.year*12+current.month-1+offset
        expected=f'{absolute//12:04}-{absolute%12+1:02}'
        if item['month']!=expected or type(item['exception_used']) is not bool:
            raise Problem(400,'Vorausgehende Prüfmonate müssen chronologisch und eindeutig belegt sein.')
        count+=item['exception_used']
    limit=YEAR_RULES[year]['minijob_minor']
    needed=total_minor>limit and annual_limit_exceeded
    accepted=not needed or unforeseen and total_minor<=2*limit and count<2
    return dict(month=month,total_minor=total_minor,monthly_limit_minor=limit,
        exception_required=needed,exception_used=needed and accepted,previous_exception_months=count,
        remains_minijob=accepted,reason='within_regular_forecast' if not needed else
            'occasional_unforeseen_excess' if accepted else 'minijob_exception_not_met',
        source_hash=_sha(dict(year=year,month=month,total_minor=total_minor,annual_limit_exceeded=annual_limit_exceeded,
            unforeseen=unforeseen,history=history,source_ref=source_ref)),
        rule_version=SOCIAL_ONEOFF_VERSION,rules_hash=SOCIAL_ONEOFF_HASH)


def calculate_minijob_one_off_contributions(*,year,running_bases,bonus_bases,bonus_minor,
        minimum_pension_basis_minor,statutory_health,rv_exempt,pension_other_compulsory,profile_ref):
    """Commercial minijob: assess the assigned period before/after the bonus.

    Status eligibility has already been established from the actual forecast or
    exception. The actual proportional 175-EUR minimum comes from the assignment
    period. It is not charged a second time on the bonus. A bonus below the floor
    can reduce the employee share while increasing the employer share.
    """
    _int(year,2025,2026);_int(bonus_minor,1);_int(minimum_pension_basis_minor,0,17500);_ref(profile_ref)
    for item in (running_bases,bonus_bases):
        _shape(item,'health pension')
        for value in item.values():_int(value)
    if any(type(value) is not bool for value in (statutory_health,rv_exempt,pension_other_compulsory)):
        raise Problem(400,'Historische Minijob-Versicherungsmerkmale ausdrücklich bestimmen.')
    if bonus_bases['health']>bonus_minor or bonus_bases['pension']>bonus_minor:
        raise Problem(400,'Die beitragspflichtige Einmalzahlung überschreitet ihren tatsächlichen Betrag.')
    def assessment(bases):
        health=_portion(bases['health'],'13') if statutory_health else 0
        pension=_portion(bases['pension'],'15')
        if rv_exempt or not bases['pension']:employee=0
        elif bases['pension']<minimum_pension_basis_minor and not pension_other_compulsory:
            employee=_portion(minimum_pension_basis_minor,'18.6')-pension
        else:employee=_portion(bases['pension'],'3.6')
        return dict(employee_pension_minor=employee,employer_health_minor=health,
                    employer_pension_minor=pension,insolvency_minor=_portion(bases['pension'],'0.15'))
    before=assessment(running_bases);after=assessment({key:running_bases[key]+bonus_bases[key] for key in running_bases})
    return dict(year=year,before=before,after=after,employee_pension_minor=after['employee_pension_minor']-before['employee_pension_minor'],
        employer_health_minor=after['employer_health_minor']-before['employer_health_minor'],
        employer_pension_minor=after['employer_pension_minor']-before['employer_pension_minor'],
        employer_levies=dict(u1=0,u2=0,insolvency=after['insolvency_minor']-before['insolvency_minor']),
        employer_flat_tax_minor=_portion(bonus_minor,'2'),profile_ref=profile_ref,
        source_hash=_sha(dict(year=year,running_bases=running_bases,bonus_bases=bonus_bases,bonus_minor=bonus_minor,
            minimum_pension_basis_minor=minimum_pension_basis_minor,statutory_health=statutory_health,
            rv_exempt=rv_exempt,pension_other_compulsory=pension_other_compulsory,profile_ref=profile_ref)),
        rule_version=SOCIAL_ONEOFF_VERSION,rules_hash=SOCIAL_ONEOFF_HASH)
