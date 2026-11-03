"""Pure, source-bound statutory entitlement primitives; no payroll-v4 changes.

The caller resolves actual employee-owned originals. References alone cannot
prove those originals. Unsupported overlapping recurrence/contract cases are
rejected explicitly; these primitives are not a complete payroll calculation.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import re

from core import Problem, canonical
from payroll_de_2026 import day, integer

ENTITLEMENT_RULE_VERSION = 'de_2026_entitlements_v1'
ENTITLEMENT_RULES = dict(version=ENTITLEMENT_RULE_VERSION,
    sickness='ENTGFG_3_4_WAIT_28_CALENDAR_DAYS_RECURRENT_42_6_12_MONTHS',
    vacation='BURLG_11_COMPLETE_13_WEEK_REGULAR_WORKDAY_REFERENCE',
    unpaid='SGB_IV_7_3_BGB_187_2_188_CALENDAR_MONTH_SEPARATE_EXCLUSIONS',
    rounding='ROUND_COMPONENT_TOTAL_HALF_UP_NO_EARLY_DAILY_AVERAGE',
    actual_project_time='UNCHANGED_SEPARATE_ENTITLEMENT_SECONDS')
ENTITLEMENT_RULES_SHA256 = hashlib.sha256(canonical(ENTITLEMENT_RULES).encode()).hexdigest()
ONE_DAY = timedelta(days=1)
EXCEPTIONS = frozenset(('sickness_benefit', 'private_sickness_benefit', 'injury_benefit',
    'social_compensation_sickness_benefit', 'soldier_compensation_sickness_benefit',
    'transition_benefit', 'care_support_benefit', 'maternity_benefit',
    'child_raising_benefit', 'parental_benefit', 'parental_leave',
    'military_service', 'civilian_service', 'care_leave_section_3'))
ENTITLEMENT_KINDS = ('sickness_history','regular_absence','vacation_reference','unpaid_continuation')


def _shape(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise Problem(400, 'Der Anspruchsnachweis hat fehlende oder unbekannte Felder.')


def _identifier(value):
    if not isinstance(value, str) or re.fullmatch('[a-f0-9]{32}', value) is None:
        raise Problem(400, 'Eine unveränderliche private Fallkennung ist erforderlich.')
    return value


def _refs(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 100:
        raise Problem(400, 'Mindestens eine konkrete Originalfassung ist erforderlich.')
    result = []
    for value in values:
        _shape(value, 'id revision content_hash')
        _identifier(value['id']); integer(value['revision'], 1, 10**9)
        if not isinstance(value['content_hash'], str) or not re.fullmatch('[a-f0-9]{64}', value['content_hash']):
            raise Problem(400, 'Der Originalhash ist ungültig.')
        result.append(dict(value))
    if len({(r['id'], r['revision']) for r in result}) != len(result):
        raise Problem(400, 'Doppelte Originalfassungen sind nicht zulässig.')
    return sorted(result, key=lambda r: (r['id'], r['revision']))


def _interval(first, last):
    first, last = day(first), day(last)
    if last < first or (last-first).days > 366*60:
        raise Problem(400, 'Der belegte Zeitraum ist ungültig.')
    return first, last


def _dates(first, last):
    return [first + timedelta(days=i) for i in range((last-first).days+1)]


def calendar_month_period_end(start, months=1):
    """Inclusive end of a period starting at beginning of day, BGB 187(2).

    Missing *end* days use BGB 188(3): Jan 29/30/31 + one month all
    end Feb 28 in 2026. Clamping an anniversary then subtracting one is wrong.
    """
    start = day(start) if isinstance(start, str) else start
    if type(start) is not date:
        raise Problem(400, 'Fristbeginn als Datum angeben.')
    integer(months, 1, 120)
    total = start.year*12 + start.month-1 + months
    year, month0 = divmod(total, 12)
    if not 1 <= year <= 9999:
        raise Problem(400, 'Die Monatsfrist liegt außerhalb des Datumsbereichs.')
    if start.day == 1:
        return date(year, month0+1, 1)-ONE_DAY
    return date(year, month0+1, min(start.day-1, calendar.monthrange(year, month0+1)[1]))


def _money(numerator, denominator=1):
    if denominator <= 0:
        raise Problem(400, 'Die Anspruchsreferenz hat keinen positiven Nenner.')
    with localcontext() as context:
        context.prec = 50
        return int((Decimal(numerator)/Decimal(denominator)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _result(kind, source, **values):
    result = dict(schema_version=1, rule_version=ENTITLEMENT_RULE_VERSION,
        rules_hash=ENTITLEMENT_RULES_SHA256, kind=kind,
        source_hash=hashlib.sha256(canonical(source).encode()).hexdigest(), **values)
    result['plan_hash'] = hashlib.sha256(canonical(result).encode()).hexdigest()
    return result


def derive_sickness_entitlement(source):
    """Derive ordinary EFZ periods from complete evidenced same-illness history.

    One episode is one independently evidenced prevention case. Overlapping
    causes and a change of controlling illness need their later phase model.
    No request may supply consumed/remaining entitlement days.
    """
    _shape(source, 'employment_from employment_to pay_basis complete_from complete_through history_evidence_refs episodes')
    employment = day(source['employment_from'])
    end = day(source['employment_to']) if source['employment_to'] is not None else None
    if end is not None and end < employment:
        raise Problem(400, 'Beschäftigungsende liegt vor dem Beginn.')
    if source['pay_basis'] not in ('monthly', 'hourly'):
        raise Problem(400, 'Die Entgeltbasis ist unbekannt.')
    complete_from, complete_through = _interval(source['complete_from'], source['complete_through'])
    _refs(source['history_evidence_refs'])
    if complete_from < employment:
        raise Problem(400, 'Vorzeiten gehören zu diesem tatsächlichen Beschäftigungsverhältnis.')
    episodes = source['episodes']
    if not isinstance(episodes, list) or len(episodes) > 2000:
        raise Problem(400, 'Die belegten AU-Vorzeiten sind ungültig.')
    ordered = []
    identities = set()
    for episode in episodes:
        _shape(episode, 'id from to onset first_scheduled_day continuation_group recovery_before unculpable evidence_refs')
        identity = _identifier(episode['id']); _identifier(episode['continuation_group'])
        if identity in identities:
            raise Problem(400, 'Der AU-Fall ist doppelt enthalten.')
        identities.add(identity)
        first, last = _interval(episode['from'], episode['to'])
        if first < complete_from or last > complete_through or first < employment or end and last > end:
            raise Problem(400, 'AU-Fall liegt außerhalb der belegten Beschäftigungs-/Vollständigkeitsgrenze.')
        if episode['onset'] not in ('before_work', 'during_work', 'non_workday'):
            raise Problem(400, 'Der tatsächliche AU-Beginn muss belegt werden.')
        if episode['recovery_before'] is not True or episode['unculpable'] is not True:
            raise Problem(409, 'Ungeklärter Verhinderungszusammenhang oder Verschulden benötigt eine eigene Anspruchsentscheidung.')
        _refs(episode['evidence_refs'])
        count_from = first + (ONE_DAY if episode['onset'] == 'during_work' else timedelta(0))
        scheduled = episode['first_scheduled_day']
        if source['pay_basis'] == 'hourly' and episode['onset'] == 'non_workday':
            scheduled = day(scheduled)
            if scheduled < first or scheduled > last:
                raise Problem(400, 'Der erste ausgefallene Arbeitstag muss im AU-Zeitraum liegen.')
            count_from = scheduled
        elif scheduled is not None:
            raise Problem(400, 'Ein verschobener erster Arbeitstag gehört nur zum belegten Stundenlohnfall an einem freien Tag.')
        ordered.append((first, last, count_from, episode))
    ordered.sort(key=lambda row: (row[0], row[3]['id']))
    if ordered:
        first = ordered[0][0]
        if complete_from != employment and first <= calendar_month_period_end(complete_from, 6):
            raise Problem(409, 'Vor dem ersten eingebrachten Fall fehlen vollständige sechs krankheitsfreie Monate oder die Beschäftigungsvorzeiten.')
    waiting_end = employment + timedelta(days=27)
    groups = {}; rows = []; previous_end = None
    for first, last, count_from, episode in ordered:
        if previous_end is not None and first <= previous_end:
            raise Problem(409, 'Überlappende Erkrankungsursachen benötigen den gesonderten phasenbezogenen Verhinderungsfall.')
        previous_end = last
        group = episode['continuation_group']; state = groups.get(group)
        reset = 'first_evidenced_case'
        if state is not None:
            if first > calendar_month_period_end(state['last_end'] + ONE_DAY, 6):
                reset = 'six_months_without_same_illness'
            elif count_from > calendar_month_period_end(state['anchor'], 12):
                reset = 'twelve_months_since_first_case'
            else:
                reset = 'same_illness_remaining_entitlement'
        if reset != 'same_illness_remaining_entitlement':
            state = dict(anchor=count_from, used=0, last_end=last)
        available = max(0, 42-state['used'])
        paid_first = max(count_from, waiting_end+ONE_DAY)
        count_days = max(0, (last-paid_first).days+1)
        paid_days = min(available, count_days)
        paid_last = paid_first + timedelta(days=paid_days-1) if paid_days else None
        extra_first = first if episode['onset'] == 'during_work' and first > waiting_end and available else None
        state['used'] += paid_days; state['last_end'] = last; groups[group] = state
        rows.append(dict(episode_id=episode['id'], continuation_group=group,
            from_date=first.isoformat(), to_date=last.isoformat(),
            count_from=count_from.isoformat(), waiting_period_end=waiting_end.isoformat(),
            entitlement_from=paid_first.isoformat() if paid_days else None,
            entitlement_to=paid_last.isoformat() if paid_last else None,
            entitlement_calendar_days=paid_days,
            first_day_remaining_regular_wage=extra_first.isoformat() if extra_first else None,
            reset_reason=reset, twelve_month_anchor=state['anchor'].isoformat(),
            prior_used_days=42-available, remaining_days=max(0,42-state['used']),
            evidence_refs=_refs(episode['evidence_refs'])))
    return _result('sickness', source, episodes=rows, waiting_period_end=waiting_end.isoformat())


def derive_unpaid_continuation(source):
    """One continuous no-wage episode; replacement benefits are actual evidence.

    Does not produce insurance membership, payroll caps or tax days. A period
    after an actual statutory exclusion gets its own month (DRV GRA section 6).
    Unlike an inserted paid vacation day, preceding benefits are not counted.
    """
    _shape(source, 'from to employment_to employment_continues no_wage_claim intervening_paid_days evidence_refs exceptions')
    first, last = _interval(source['from'], source['to'])
    if source['employment_continues'] is not True or source['no_wage_claim'] is not True:
        raise Problem(409, 'Fortbestand und tatsächlicher fehlender Entgeltanspruch müssen belegt sein.')
    if source['intervening_paid_days'] != []:
        raise Problem(409, 'Bezahlte Zwischentage benötigen den gesonderten Wiederaufnahme-/Unterbrechungsnachweis; keine automatische neue Monatsfrist.')
    _refs(source['evidence_refs'])
    if source['employment_to'] is not None:
        employment_to = day(source['employment_to'])
        if employment_to < first or last > employment_to:
            raise Problem(400, 'Unbezahlter Fortbestand liegt außerhalb der Beschäftigung.')
    exceptions = source['exceptions']
    if not isinstance(exceptions, list) or len(exceptions) > 100:
        raise Problem(400, 'Ausnahmetatbestände müssen als datierte Originale vorliegen.')
    excluded = {}
    for exception in exceptions:
        _shape(exception, 'kind from to employment_scope evidence_refs')
        if not isinstance(exception['kind'],str) or exception['kind'] not in EXCEPTIONS:
            raise Problem(400, 'Unbekannter Ausschluss nach §7 Abs.3 SGB IV.')
        if exception['employment_scope'] != 'this_employment':
            raise Problem(409, 'Entgeltersatz aus einer anderen Beschäftigung darf diesen Fortbestand nicht verkürzen.')
        ex_first, ex_last = _interval(exception['from'], exception['to'])
        if ex_first < first or ex_last > last:
            raise Problem(400, 'Ausnahmetatbestand liegt außerhalb der Unterbrechung.')
        refs = _refs(exception['evidence_refs'])
        for current in _dates(ex_first, ex_last):
            if current in excluded:
                raise Problem(409, 'Überlagerte Ausnahmetatbestände benötigen einen eindeutigen beitragsrechtlichen Verlauf.')
            excluded[current] = (exception['kind'], refs)
    intervals = []; windows = []; deadline = None; previous_excluded = True
    for current in _dates(first, last):
        exception = excluded.get(current)
        if exception is None and previous_excluded:
            deadline = calendar_month_period_end(current)
            windows.append(dict(**{'from':current.isoformat()},statutory_deadline=deadline.isoformat(),
                basis='first_no_wage_period' if current==first else 'after_evidenced_statutory_exclusion'))
        basis = 'exception:'+exception[0] if exception else ('section_7_3_continued' if current <= deadline else 'one_month_exhausted')
        refs = exception[1] if exception else _refs(source['evidence_refs'])
        if intervals and intervals[-1]['basis'] == basis and intervals[-1]['evidence_refs'] == refs:
            intervals[-1]['to'] = current.isoformat(); intervals[-1]['calendar_days'] += 1
        else:
            intervals.append(dict(**{'from':current.isoformat(),'to':current.isoformat()},calendar_days=1,
                basis=basis, employment_for_contributions_continues=basis=='section_7_3_continued',evidence_refs=refs))
        previous_excluded = exception is not None
    return _result('unpaid_continuation', source, continuation_windows=windows,
        intervals=intervals, tax_lzz_reduced_by_unpaid_days=False,
        insurance_membership_determined=False)


def calculate_regular_absence_pay(source):
    """Explicit fixed hourly regular-work loss, excluding overtime/expenses."""
    _shape(source, 'kind hourly_rate_minor days evidence_refs')
    if source['kind'] not in ('public_holiday','sickness','first_sickness_day_regular_wage'):
        raise Problem(400, 'Unbekannte regelmäßige Ausfallvergütung.')
    integer(source['hourly_rate_minor'], 1, 10**7); _refs(source['evidence_refs'])
    if not isinstance(source['days'], list) or not 1 <= len(source['days']) <= 366:
        raise Problem(400, 'Ausfalltage fehlen.')
    seen = set(); rows = []; seconds = 0
    for item in source['days']:
        _shape(item, 'date scheduled_regular_seconds worked_regular_seconds entitled absence_is_only_cause holiday_adjacent_unexcused evidence_refs')
        current = day(item['date'])
        if current in seen:
            raise Problem(400, 'Doppelte Ausfalltage sind nicht zulässig.')
        seen.add(current)
        expected = integer(item['scheduled_regular_seconds'],0,86400)
        worked = integer(item['worked_regular_seconds'],0,86400)
        if worked > expected:
            raise Problem(409, 'Tatsächliche regelmäßige Arbeit überschreitet den gebundenen Sollplan.')
        if type(item['entitled']) is not bool or type(item['absence_is_only_cause']) is not bool:
            raise Problem(400, 'Anspruch und alleiniger Ausfallgrund benötigen eine ausdrückliche Entscheidung.')
        if source['kind']=='public_holiday':
            if type(item['holiday_adjacent_unexcused']) is not bool:
                raise Problem(400, 'Der Feiertagsausschluss unmittelbar vor/nach dem Tag muss geprüft sein.')
        elif item['holiday_adjacent_unexcused'] is not None:
            raise Problem(400, 'Der Feiertagsausschluss gehört ausschließlich zum Feiertagsfall.')
        entitled = item['entitled'] and item['absence_is_only_cause'] and not item['holiday_adjacent_unexcused']
        paid = expected-worked if entitled else 0
        if worked and source['kind'] != 'first_sickness_day_regular_wage':
            raise Problem(409, 'Teilweise tatsächlich geleistete Arbeit benötigt eine gesonderte eindeutige Tagesentscheidung.')
        seconds += paid
        rows.append(dict(date=current.isoformat(), paid_absence_seconds=paid,
            actual_work_seconds=worked, evidence_refs=_refs(item['evidence_refs'])))
    return _result(source['kind'], source, days=sorted(rows,key=lambda r:r['date']),
        paid_absence_seconds=seconds, actual_project_time_modified=False,
        gross_minor=_money(source['hourly_rate_minor']*seconds,3600),
        ratio=dict(numerator=source['hourly_rate_minor']*seconds,denominator=3600))


def calculate_vacation_reference(source):
    """13 complete weeks, fixed contractual workday denominator, exact ratio.

    Adjustment amounts are separately evidenced facts, never silent defaults.
    A changing workweek/on-call/shorter employment requires a separate branch.
    """
    _shape(source, 'vacation_from vacation_to reference_days vacation_days in_kind_daily_minor evidence_refs')
    first, last = _interval(source['vacation_from'],source['vacation_to'])
    refs = _refs(source['evidence_refs']); integer(source['in_kind_daily_minor'],0,10**7)
    history = source['reference_days']; requested = source['vacation_days']
    if not isinstance(history,list) or len(history)!=91:
        raise Problem(409,'Urlaubsentgelt benötigt die vollständigen 13 Wochen vor Beginn.')
    if not isinstance(requested,list) or not 1<=len(requested)<=366:
        raise Problem(400,'Die tatsächlich ausfallenden Urlaubstage fehlen.')
    seen = set(); numerator = 0; denominator = 0; components = []
    for item in history:
        _shape(item,'date contractual_workday base_earnings_minor overtime_earnings_minor protected_reduction_minor permanent_raise_minor evidence_refs')
        current=day(item['date'])
        if current in seen:
            raise Problem(400,'Doppelte Referenztage sind nicht zulässig.')
        seen.add(current)
        if type(item['contractual_workday']) is not bool:
            raise Problem(400,'Der vertragliche Arbeitstag muss eindeutig belegt sein.')
        for key in ('base_earnings_minor','overtime_earnings_minor','protected_reduction_minor','permanent_raise_minor'):
            integer(item[key],0,10**9)
        if item['overtime_earnings_minor']>item['base_earnings_minor']:
            raise Problem(400,'Ausgeschlossene Überstundenvergütung übersteigt den belegten Verdienst.')
        value=item['base_earnings_minor']-item['overtime_earnings_minor']+item['protected_reduction_minor']+item['permanent_raise_minor']
        if value and not item['contractual_workday']:
            raise Problem(409,'Entgelt an arbeitsfreien Referenztagen benötigt eine eigene belegte Verteilungsregel.')
        numerator+=value;denominator+=int(item['contractual_workday'])
        components.append(dict(date=current.isoformat(),adjusted_earnings_minor=value,evidence_refs=_refs(item['evidence_refs'])))
    if seen!=set(_dates(first-timedelta(days=91),first-ONE_DAY)):
        raise Problem(409,'Die Referenz muss exakt die 13 Wochen vor Urlaubsbeginn abdecken.')
    patterns = {}
    for item in history:
        weekday=day(item['date']).weekday()
        if weekday in patterns and patterns[weekday] != item['contractual_workday']:
            raise Problem(409,'Wechselnde Wochenarbeitstage benötigen eine eigene belegte Urlaubsreferenz.')
        patterns[weekday]=item['contractual_workday']
    vacation_dates=[];paid_seconds=0
    for item in requested:
        _shape(item,'date scheduled_regular_seconds evidence_refs')
        current=day(item['date']);integer(item['scheduled_regular_seconds'],1,86400);_refs(item['evidence_refs'])
        if not first<=current<=last or current in vacation_dates or not patterns[current.weekday()]:
            raise Problem(400,'Die Urlaubstage sind doppelt oder außerhalb des belegten Urlaubs.')
        vacation_dates.append(current);paid_seconds+=item['scheduled_regular_seconds']
    if min(vacation_dates)!=first:
        raise Problem(409,'Der Beginn muss dem ersten tatsächlich ausfallenden Urlaubstag entsprechen.')
    workday_average=dict(numerator=numerator,denominator=denominator)
    cash_compensation=source['in_kind_daily_minor']*len(vacation_dates)
    gross=_money(numerator*len(vacation_dates),denominator)+cash_compensation
    return _result('vacation',source,reference_from=(first-timedelta(days=91)).isoformat(),
        reference_to=(first-ONE_DAY).isoformat(),reference_components=sorted(components,key=lambda r:r['date']),
        workday_average=workday_average,vacation_days=[d.isoformat() for d in sorted(vacation_dates)],
        paid_absence_seconds=paid_seconds,in_kind_cash_compensation_minor=cash_compensation,
        gross_minor=gross,due_before=first.isoformat(),evidence_refs=refs,
        actual_project_time_modified=False)


def calculate_entitlement_input(kind, source):
    calculators = dict(sickness_history=derive_sickness_entitlement,
        regular_absence=calculate_regular_absence_pay,vacation_reference=calculate_vacation_reference,
        unpaid_continuation=derive_unpaid_continuation)
    if not isinstance(kind,str) or kind not in calculators:
        raise Problem(400,'Unbekannte belegte Lohnanspruchsart.')
    return calculators[kind](source)


def build_entitlement_plan(snapshot, rule_version=ENTITLEMENT_RULE_VERSION):
    """Versioned composition boundary for the independent private fact service.

    Source validation belongs to that service. All original bindings are hashed
    here, including metadata irrelevant to arithmetic. Never reuse a new rule
    for a historical plan, even if that plan originally had a blocker.
    """
    if rule_version != ENTITLEMENT_RULE_VERSION:
        raise Problem(409,'Die gespeicherte Anspruchsregelversion ist nicht verfügbar.')
    if not isinstance(snapshot,dict) or snapshot.get('schema_version') != 1:
        raise Problem(400,'Unbekannte Anspruchsquellenversion.')
    primitive=calculate_entitlement_input(snapshot['kind'],snapshot['details']['input'])
    result={key:value for key,value in primitive.items() if key not in ('plan_hash','source_hash','kind')}
    result.update(kind=snapshot['kind'],entitlement_kind=primitive['kind'],
        input_hash=primitive['source_hash'],source_hash=hashlib.sha256(canonical(snapshot).encode()).hexdigest())
    result['plan_hash']=hashlib.sha256(canonical(result).encode()).hexdigest()
    return result
