"""New sickness v2; immutable v1 readers remain in payroll_entitlements_2026.

IKK2026 p8 distinguishes an hourly free first day (following-day start)
from fixed monthly pay (first-day start). It does not postpone the legal
calendar period until a later scheduled shift. No diagnosis is stored.
"""
from datetime import timedelta
import hashlib

from core import Problem, canonical
from payroll_de_2026 import day
from payroll_entitlements_2026 import (
    ONE_DAY, _shape, _refs, _identifier, _interval, calendar_month_period_end)

SICKNESS_RULE_VERSION = 'de_2026_sickness_v2'
SICKNESS_RULES = dict(version=SICKNESS_RULE_VERSION,
    waiting='ENTGFG_3_3_28_CALENDAR_DAYS_NOT_CONSUMED',
    duration='ENTGFG_3_1_42_CALENDAR_DAYS',
    hourly_non_workday_start='FOLLOWING_CALENDAR_DAY_NOT_FIRST_LATER_SHIFT',
    monthly_non_workday_start='FIRST_CALENDAR_DAY',
    during_work_start='NEXT_DAY_PLUS_SEPARATE_ORDINARY_REMAINING_WAGE',
    recurrence='SAME_ILLNESS_6_12_MONTHS_EVIDENCED_RECOVERY',
    overlaps='SEPARATE_PHASE_MODEL_REQUIRED',
    input='EXACT_ORIGINAL_SHIFT_DATE_UNCHANGED',
    evidence='IKK_2026_35_EDITION_PAGE_8')
SICKNESS_RULES_SHA256 = hashlib.sha256(canonical(SICKNESS_RULES).encode()).hexdigest()


def _result(kind, source, **values):
    result = dict(schema_version=1, rule_version=SICKNESS_RULE_VERSION,
        rules_hash=SICKNESS_RULES_SHA256, kind=kind,
        source_hash=hashlib.sha256(canonical(source).encode()).hexdigest(), **values)
    result['plan_hash'] = hashlib.sha256(canonical(result).encode()).hexdigest()
    return result


def derive_sickness_entitlement(source):
    """Calculate evidenced separate sickness episodes under the v2 rule.

    A free first day for hourly pay is excluded; later free days still count.
    The first actual missed shift remains an original fact, never the legal
    start-date input. Overlapping causes retain their explicit later branch.
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
            if scheduled == first:
                raise Problem(400, 'Ein arbeitsfreier Anfang darf nicht zugleich erster ausgefallener Solltag sein.')
            count_from = first + ONE_DAY
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

