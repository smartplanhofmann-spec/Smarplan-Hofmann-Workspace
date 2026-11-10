"""Explicit evidenced revocation of one established commercial-minijob exemption.

It records an explicitly reviewed objection deadline; it does not calculate regional holiday
or administrative appeal law or create an authority decision from elapsed time.
"""
from calendar import monthrange
from copy import deepcopy
from datetime import date
from pathlib import Path
import hashlib
import json
import re

RULE_VERSION = 'de_2026_minijob_rv_revocation_v1'
RULES = dict(version=RULE_VERSION, source_encoding='UTF8_CANONICAL_LF',
    statutory_source='https://www.gesetze-im-internet.de/sgb_6/__6.html',
    guideline='https://www.minijob-zentrale.de/SharedDocs/Downloads/DE/Rundschreiben/Geringfuegigkeitsrichtlinien-2026.pdf?__blob=publicationFile',
    supported_scope='ONE_ESTABLISHED_SOLE_CONTINUOUS_COMMERCIAL_MINIJOB_EXEMPTION_2026',
    request_scope='RECEIVED_ON_OR_AFTER_2026_07_01',
    deadline='EXPLICIT_ORIGINAL_REVIEW_INCLUDING_APPLICABLE_HOLIDAYS_NO_AUTOMATIC_ACCEPTANCE',
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    external_transmission=False,official_system_approval=False)
RULES_SHA256=hashlib.sha256(json.dumps(RULES,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
FIELDS = frozenset(('schema_version', 'employee_id', 'episode_id', 'employment_from', 'employment_to',
    'target_month', 'reviewed_as_of', 'sole_continuous_commercial_minijob_confirmed',
    'no_old_age_or_other_exclusion_confirmed', 'established_exemption', 'revocation', 'review_note'))
EXEMPTION_FIELDS = frozenset(('effective_from', 'profile_ref', 'evidence_ref', 'established_status_confirmed'))
REVOCATION_FIELDS = frozenset(('received_on', 'request_format', 'request_ref', 'notification_received_on',
    'notification_ref', 'authority_status', 'objection_deadline_on', 'deadline_ref',
    'deadline_review_confirmed', 'authority_status_on', 'authority_evidence_ref', 'review_note'))


class InvalidEvidence(ValueError):
    pass


def _shape(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise InvalidEvidence('Complete explicit source fields required')


def _date(value):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise InvalidEvidence('Exact calendar date required')
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidEvidence('Actual calendar date required') from error


def _id(value, length=32):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{'+str(length)+'}', value):
        raise InvalidEvidence('Original identity required')
    return value


def _ref(value):
    _shape(value, {'id', 'revision', 'content_hash'})
    _id(value['id']); _id(value['content_hash'], 64)
    if type(value['revision']) is not int or value['revision'] < 1:
        raise InvalidEvidence('Original revision required')


def _bool(value):
    if type(value) is not bool:
        raise InvalidEvidence('Explicit confirmation required')


def _note(value):
    if type(value) is not str or not value.strip() or len(value) > 3000:
        raise InvalidEvidence('Actual review note required')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise InvalidEvidence('Valid Unicode required') from error
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise InvalidEvidence('Unsupported control character')


def _month_after(value):
    return date(value.year+int(value.month == 12), value.month % 12+1, 1)


def _minimum_month_deadline(value):
    start = _month_after(value)
    return date(start.year, start.month, min(value.day, monthrange(start.year, start.month)[1]))


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def normalize(value):
    _shape(value, FIELDS)
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise InvalidEvidence('Known lifecycle version required')
    for name in ('employee_id', 'episode_id'):
        _id(value[name])
    start, as_of = _date(value['employment_from']), _date(value['reviewed_as_of'])
    end = None if value['employment_to'] is None else _date(value['employment_to'])
    if start < date(2013,1,1) or (end is not None and end < start) or as_of.year != 2026:
        raise InvalidEvidence('Supported actual employment and 2026 review required')
    if type(value['target_month']) is not str or not re.fullmatch(r'2026-(0[1-9]|1[0-2])', value['target_month']):
        raise InvalidEvidence('Explicit supported payroll month required')
    _note(value['review_note'])
    for key in ('sole_continuous_commercial_minijob_confirmed', 'no_old_age_or_other_exclusion_confirmed'):
        _bool(value[key])
    old = value['established_exemption']; _shape(old, EXEMPTION_FIELDS)
    effective = _date(old['effective_from']); _ref(old['profile_ref']); _ref(old['evidence_ref'])
    _bool(old['established_status_confirmed'])
    if effective < start or effective > as_of:
        raise InvalidEvidence('Actual established exemption within employment required')
    r = value['revocation']
    if r is not None:
        _shape(r, REVOCATION_FIELDS); received = _date(r['received_on'])
        if received < date(2026,7,1) or not start <= received <= as_of or (end is not None and received > end) or received < effective:
            raise InvalidEvidence('Actual request received in this employment after June2026 required')
        if r['request_format'] not in ('written', 'electronic'):
            raise InvalidEvidence('Written or electronic request required')
        _ref(r['request_ref']); _bool(r['deadline_review_confirmed']); _note(r['review_note'])
        status = r['authority_status']
        if status not in ('not_notified', 'pending', 'non_objection_verified', 'objected'):
            raise InvalidEvidence('Explicit actual authority evidence state required')
        notified = r['notification_received_on']
        if notified is None:
            if status != 'not_notified' or any(r[k] is not None for k in ('notification_ref', 'objection_deadline_on', 'deadline_ref', 'authority_status_on', 'authority_evidence_ref')) or r['deadline_review_confirmed']:
                raise InvalidEvidence('Unsent application cannot invent notification or authority outcome')
        else:
            notified = _date(notified); _ref(r['notification_ref'])
            if not received <= notified <= as_of or status == 'not_notified':
                raise InvalidEvidence('Actual notification receipt chronology required')
            if r['objection_deadline_on'] is not None:
                deadline = _date(r['objection_deadline_on']); _ref(r['deadline_ref'])
                if deadline < _minimum_month_deadline(notified):
                    raise InvalidEvidence('A reviewed deadline cannot shorten a calendar month')
            elif r['deadline_ref'] is not None or r['deadline_review_confirmed']:
                raise InvalidEvidence('Deadline review requires its actual date and original')
            recorded = r['authority_status_on']
            if status == 'pending':
                if recorded is not None or r['authority_evidence_ref'] is not None:
                    raise InvalidEvidence('Pending procedure cannot invent a final authority record')
            else:
                _ref(r['authority_evidence_ref']); recorded = _date(recorded)
                if not notified <= recorded <= as_of:
                    raise InvalidEvidence('Actual authority evidence chronology required')
                if status == 'non_objection_verified' and (r['objection_deadline_on'] is None or not r['deadline_review_confirmed'] or recorded <= _date(r['objection_deadline_on'])):
                    raise InvalidEvidence('Non-objection needs explicit verified expiry including applicable holidays')
    return deepcopy(value)


def assess(value, *, original_profile, source_files, prior_assessments=()):
    v = normalize(value); old = v['established_exemption']; r = v['revocation']
    if type(source_files) not in (list, tuple) or type(prior_assessments) not in (list, tuple) or len(source_files)>1000 or len(prior_assessments)>1000:
        raise InvalidEvidence('Bounded complete original lists required')
    if (original_profile.get('employee_id') != v['employee_id'] or original_profile.get('kind') != 'profile'
            or {k: original_profile.get(k) for k in ('id','revision','content_hash')} != old['profile_ref']
            or original_profile.get('profile',{}).get('employment_kind') != 'minijob'
            or original_profile['profile'].get('minijob_rv_exempt') is not True
            or original_profile['profile'].get('special_cases')
            or original_profile['profile'].get('effective_from') != old['effective_from']):
        raise InvalidEvidence('Exact original established exemption profile required')
    refs = [old['evidence_ref']]
    if r:
        refs += [r[key] for key in ('request_ref','notification_ref','deadline_ref','authority_evidence_ref') if r[key] is not None]
    for ref in refs:
        files = [f for f in source_files if f.get('id') == ref['id']]
        if len(files) != 1 or any(files[0].get(k) != ref[k] for k in ('id','revision','content_hash')) or files[0].get('employee_id') != v['employee_id'] or files[0].get('purpose') != 'personnel':
            raise InvalidEvidence('Unchanged private original for this person required')
    for previous in prior_assessments:
        p = normalize(previous)
        if p['employee_id'] != v['employee_id'] or p['episode_id'] != v['episode_id'] or p['employment_from'] != v['employment_from'] or {k:x for k,x in p['established_exemption'].items() if k!='established_status_confirmed'} != {k:x for k,x in old.items() if k!='established_status_confirmed'}:
            raise InvalidEvidence('Complete same-episode original history required')
        if p['reviewed_as_of'] > v['reviewed_as_of']:
            raise InvalidEvidence('Known later review cannot disappear behind an earlier as-of date')
        before = p['revocation']
        if before is not None:
            if r is None or any(before[k] != r[k] for k in ('received_on','request_format','request_ref')):
                raise InvalidEvidence('A previously received request cannot disappear or become a second request')
            for date_key, ref_key in (('notification_received_on','notification_ref'),('objection_deadline_on','deadline_ref'),('authority_status_on','authority_evidence_ref')):
                if before[date_key] is not None and (before[date_key] != r[date_key] or before[ref_key] != r[ref_key]):
                    raise InvalidEvidence('Previously established original history cannot be replaced')
            if before['authority_status'] in ('non_objection_verified','objected') and before != r:
                raise InvalidEvidence('A settled decision requires its own later correction contract')
    month = _date(v['target_month']+'-01'); last = date(month.year,month.month,monthrange(month.year,month.month)[1])
    blockers = []
    def block(code):
        if code not in blockers: blockers.append(code)
    if not v['sole_continuous_commercial_minijob_confirmed'] or not v['no_old_age_or_other_exclusion_confirmed']:
        block('employment_scope_not_verified')
    if not old['established_status_confirmed']:
        block('original_exemption_not_verified')
    if old['effective_from'] > month.isoformat() or month > _date(v['reviewed_as_of']) or (v['employment_to'] is not None and last > _date(v['employment_to'])):
        block('whole_month_not_covered')
    candidate = None if r is None else _month_after(_date(r['received_on'])).isoformat()
    state = 'exempt'
    if r is not None and month.isoformat() >= candidate:
        if r['authority_status'] == 'non_objection_verified': state = 'compulsory_after_revocation'
        else:
            state = 'unresolved'; block('revocation_procedure_not_settled')
    source = dict(assessment=v,original_profile=original_profile,source_files=source_files,prior_assessments=list(prior_assessments))
    return dict(rule_version=RULE_VERSION, rules_sha256=RULES_SHA256, source_hash=hashlib.sha256(_canonical(source).encode()).hexdigest(),
        employee_id=v['employee_id'],episode_id=v['episode_id'],month=v['target_month'],
        status=state if not blockers else 'unresolved',candidate_effective_from=candidate,
        can_bind_payroll=not blockers,minijob_rv_exempt=None if blockers else state=='exempt',
        blockers=sorted(blockers),deadline_method='EXPLICIT_REVIEWED_ORIGINAL_NOT_AUTOMATIC_HOLIDAY_CALCULATION',
        creates_profile=False,payment_created=False,external_transmission=False,official_system_approval=False)
