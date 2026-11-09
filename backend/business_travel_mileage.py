"""Explicit private-car travel originals; reuse the existing actual-cash ledger."""
from copy import deepcopy
import json
import re

from core import Problem, canonical
from business_operations import identifier, text, transaction
from business_personnel_workflow import _shape, _sha
from business_travel_allowances import TravelAllowances, _ref, validate_record
from payroll_travel_2026 import day, moment, integer
from payroll_travel_mileage_2026 import calculate, RULE_VERSION, RULE_HASH, TABLE_HASH, RATE_TABLE, SOURCES

FEATURE = 'travel_private_car_mileage'
ID = r'[a-f0-9]{32}'


def is_mileage(value):
    if value.get('kind') == 'trip':
        return value.get('rule_version') == RULE_VERSION
    if value.get('kind') == 'settlement':
        return value.get('calculation', {}).get('rule_version') == RULE_VERSION
    if value.get('kind') == 'payment':
        return is_mileage(value.get('sources', {}).get('settlement', {}))
    return False


def catalog():
    return dict(schema_version=1, feature=FEATURE, rule_version=RULE_VERSION,
        rule_hash=RULE_HASH, table_hash=TABLE_HASH, rate=dict(RATE_TABLE), sources=list(SOURCES),
        scope='employee_domestic_private_car_one_day_round_trip', max_legs=100,
        max_leg_distance_m=2000000, rounding='half_up_once_on_total_metres',
        payroll_supported=False, automatic_payment=False)


def _date_of(trip):
    return trip['details']['departed_at'][:10]


def _proof_key(calculation, employee_id):
    return 'mileage:' + _sha(sorted({x['evidence_sha256'] for x in calculation['mileage_items']}))


def claims(record):
    calc = record['calculation']; date = calc['days'][0]['date']; trip = record['sources']['trips'][0]
    base = dict(settlement_id=record['id'], revision=record['revision'], employee_id=record['employee_id'])
    return [dict(base, claim_key='day:'+record['employee_id']+':'+date,
        source_kind='employee_day', source_id=date, source_revision=record['revision'],
        amount_minor=calc['totals']['mileage_allowance_minor']),
        dict(base, claim_key=_proof_key(calc, record['employee_id']), source_kind='mileage',
        source_id=trip['id'], source_revision=trip['revision'], amount_minor=calc['totals']['mileage_allowance_minor'])]


def _preview_value(employee_id, data, source_hash, trip, sites, calculation):
    value = dict(employee_id=employee_id, source_hash=source_hash,
        trip_refs=[_ref(trip)], site_refs=[_ref(x) for x in sites], expense_refs=[],
        **{key:deepcopy(data[key]) for key in ('period_from','period_to','settlement_unit','tax_choice',
            'requested_meal_minor','requested_lodging_minor','correction_of','review_note')},
        payroll_month=data.get('payroll_month'), **calculation)
    value['preview_hash'] = _sha({k:v for k,v in value.items() if k not in ('can_approve','can_pay')})
    return value


class MileageTravel(TravelAllowances):
    mileage_mode = True

    def _only(self, value):
        if not is_mileage(value):
            raise Problem(404, 'Kein Kilometeroriginal unter diesem Pfad.')
        return value

    def _previous(self, kind, data):
        value = super()._previous(kind, data)
        return self._only(value) if value is not None else None

    def get(self, actor, kind, object_id, revision=None, history=False):
        self._only(self._get(kind, object_id, revision))
        return super().get(actor, kind, object_id, revision, history)

    def listing(self, actor, kind, employee_id):
        result = super().listing(actor, kind, employee_id)
        result['items'] = [x for x in result['items'] if is_mileage(x)]
        return result

    def _trip_details(self, actor, employee, details, *, current=True, rule_version=None):
        fields = ('purpose','project_id','departed_at','returned_at','timezone','home_site_ref',
                  'first_workplace_ref','source_file_ids','mileage')
        _shape(details, fields, fields)
        if rule_version not in (None, RULE_VERSION):
            raise Problem(400, 'Unveränderten Kilometerregelvertrag verwenden.')
        mileage = details['mileage']
        if not isinstance(mileage, dict) or not isinstance(mileage.get('legs'), list) or not 1<=len(mileage['legs'])<=100:
            raise Problem(400, 'Strukturierte Kilometerfahrt erforderlich.')
        refs = [details['home_site_ref']]
        if details['first_workplace_ref'] is not None:
            refs.append(details['first_workplace_ref'])
        for leg in mileage['legs']:
            if not isinstance(leg, dict):
                raise Problem(400, 'Strukturierter Streckennachweis erforderlich.')
            refs.extend((leg.get('from_site_ref'), leg.get('to_site_ref')))
        sites = []
        for ref in refs:
            site = self._resolve(actor, 'site', ref, employee['id'], current=current)
            if _ref(site) not in [_ref(x) for x in sites]: sites.append(site)
        sites.sort(key=lambda x:x['id'])
        files = self._files(actor, employee['id'], details['source_file_ids'])
        for site in sites: files.extend(site['sources']['files'])
        files = sorted({x['id']:x for x in files}.values(), key=lambda x:x['id'])
        sources = dict(files=files, sites=sites, expenses=[])
        dummy = dict(id='0'*32, revision=1, content_hash='0'*64, employee_id=employee['id'],
            kind='trip', rule_version=RULE_VERSION, details=details, sources=sources)
        calculation = calculate([dummy], sites)
        if details['project_id'] is not None and actor is not None:
            self.office.project(actor, details['project_id'])
        if current:
            date = calculation['days'][0]['date']
            if moment(details['returned_at']) > moment(self.now()):
                raise Problem(400, 'Nur eine tatsächlich abgeschlossene Fahrt erfassen.')
            active = [x for x in self._all('site', employee['id']) if x['status']=='active'
                and x['details']['effective_from']<=date
                and (x['details']['effective_to'] is None or date<=x['details']['effective_to'])]
            for kind, ref in (('home', details['home_site_ref']), ('first_workplace',details['first_workplace_ref'])):
                expected = [_ref(x) for x in active if x['details']['kind']==kind]
                if expected != ([] if ref is None else [ref]):
                    raise Problem(409, 'Eindeutige aktuelle Wohn-/erste Tätigkeitsstätte vollständig binden.')
        return deepcopy(details), sources, calculation

    def save_trip(self, actor, data):
        fields = ('request_id','employee_id','id','revision','details','correction_reason')
        _shape(data, fields, fields)
        def save(fresh, employee, fingerprint):
            old = self._previous('trip',data)
            if old and old['status']=='submitted':
                raise Problem(409, 'Eingereichte Fahrt zunächst unabhängig zurückweisen lassen.')
            reason = text(data['correction_reason'],'Änderungsgrund',1000,required=bool(old))
            details,sources,unused = self._trip_details(fresh,employee,data['details'])
            return self._append('trip',fresh,employee,data['id'],dict(status='draft',details=details,sources=sources,
                rule_version=RULE_VERSION,correction_reason=reason,submitted_by=None,submitted_at=None,
                decision=None,command_hash=fingerprint),old)
        return self._command(actor,'trip','trip.save',data,save)

    def trip_action(self,actor,trip_id,action,data):
        identifier(trip_id)
        fields = ('request_id','employee_id','revision','source_hash','confirmed')+(('reason',) if action=='reject' else ())
        _shape(data,fields,fields); original=data; command=dict(data,id=trip_id)
        def save(fresh,employee,fingerprint):
            old=self._previous('trip',command)
            if old is None:raise Problem(404,'Fahrt nicht verfügbar.')
            if data['confirmed'] is not True or data['source_hash']!=self._basis(employee['id']):
                raise Problem(409,'Aktuelle Fahrtquellen ausdrücklich bestätigen.')
            if action=='submit':
                if old['status'] not in ('draft','rejected'):raise Problem(409,'Nur offene Fahrt einreichen.')
                self._trip_details(fresh,employee,old['details'])
                status='submitted';submitted_by=fresh['id'];submitted_at=self.now();decision=None
            elif action=='reject':
                if old['status']!='submitted' or fresh['id'] in (employee['user_id'],old['submitted_by']):
                    raise Problem(409,'Fahrt durch eine andere Person prüfen.')
                status='rejected';submitted_by=old['submitted_by'];submitted_at=old['submitted_at']
                decision=dict(by=fresh['id'],reason=text(data['reason'],'Prüfgrund',1000,required=True))
            else:raise Problem(404,'Unbekannte Fahrtaktion.')
            return self._append('trip',fresh,employee,trip_id,dict(status=status,details=old['details'],sources=old['sources'],
                rule_version=RULE_VERSION,correction_reason=old['correction_reason'],submitted_by=submitted_by,
                submitted_at=submitted_at,decision=decision,command_hash=fingerprint),old)
        return self._command(actor,'trip','trip.'+action,command,save,permission='personnel.approve' if action=='reject' else 'personnel.write',
            own=action!='reject',original_body=original)

    def _preview(self,actor,data,*,historical=False):
        fields=('employee_id','trip_refs','period_from','period_to','settlement_unit','tax_choice',
                'requested_meal_minor','requested_lodging_minor','correction_of','review_note')
        _shape(data,fields+('payroll_month',),fields)
        fresh,employee=self._employee(actor,data['employee_id'])
        if not isinstance(data['trip_refs'],list) or len(data['trip_refs'])!=1 or data.get('payroll_month') is not None:
            raise Problem(400,'Genau eine Kilometerfahrt ohne Lohnmonat auswählen.')
        trip=self._only(self._resolve(fresh,'trip',data['trip_refs'][0],employee['id']))
        if trip['status']!='submitted':raise Problem(409,'Eingereichte eigene Fahrt auswählen.')
        self._trip_details(fresh,employee,trip['details'])
        date=_date_of(trip)
        if data['period_from']!=date or data['period_to']!=date:
            raise Problem(400,'Unveränderten ursprünglichen Fahrttag abrechnen.')
        text(data['review_note'],'Prüfvermerk',2000,required=True)
        old=None
        if data['correction_of'] is not None:
            old=self._only(self._resolve(fresh,'settlement',data['correction_of'],employee['id']))
            if old['sources']['trips'][0]['id']!=trip['id'] or old['details']['period_from']!=date:
                raise Problem(409,'Korrektur bei ihrer ursprünglichen Fahrt und ihrem Tag belassen.')
        from travel_allowance_cash import _paid
        after=self.db.execute('SELECT COALESCE(MAX(sequence),0) AS n FROM business_travel_payments').fetchone()['n']
        paid=_paid(self,old['id'],through_sequence=after) if old else 0
        sites=trip['sources']['sites']
        calc=calculate([trip],sites,settlement_unit=data['settlement_unit'],tax_choice=data['tax_choice'],
            requested_meal_minor=data['requested_meal_minor'],requested_lodging_minor=data['requested_lodging_minor'],already_paid_minor=paid)
        used=self.db.execute('SELECT DISTINCT settlement_id FROM business_travel_claims WHERE source_kind=? AND claim_key=?',
            ('mileage',_proof_key(calc,employee['id']))).fetchall()
        if any(row['settlement_id']!=(old['id'] if old else None) for row in used):
            calc['blockers'].append(dict(code='mileage_original_already_settled',text='Das tatsächliche Streckenoriginal ist bereits an eine andere Abrechnung gebunden.',source_ref=None))
            calc['can_approve']=False;calc['can_pay']=False
        for existing in self._all('settlement',employee['id']):
            if old and existing['id']==old['id']:continue
            duplicate_day=any(x['date']==date for x in existing['calculation']['days'])
            duplicate_proof=is_mileage(existing) and _proof_key(existing['calculation'],employee['id'])==_proof_key(calc,employee['id'])
            if duplicate_day or duplicate_proof:
                calc['blockers'].append(dict(code='mileage_already_settled',text='Fahrtoriginal oder Personentag ist bereits abgerechnet.',source_ref=_ref(existing)))
                calc['can_approve']=False;calc['can_pay']=False
        source_hash=self._basis(employee['id'])
        value=_preview_value(employee['id'],data,source_hash,trip,sites,calc)
        sources=dict(employee={k:employee[k] for k in ('id','user_id','name','revision')},trips=[trip],history_trips=[],
            sites=sites,files=trip['sources']['files'],expenses=[],after_payment_sequence=after)
        return value,sources,old

    def approve(self,actor,data):
        fields=('employee_id','trip_refs','period_from','period_to','settlement_unit','tax_choice','requested_meal_minor',
            'requested_lodging_minor','correction_of','review_note','id','request_id','revision','source_hash','preview_hash','confirmed')
        _shape(data,fields+('payroll_month',),fields)
        def save(fresh,employee,fingerprint):
            old=self._previous('settlement',data)
            base={k:v for k,v in data.items() if k not in ('id','request_id','revision','source_hash','preview_hash','confirmed')}
            preview,sources,corrected=self._preview(fresh,base)
            if data['confirmed'] is not True or any(data[k]!=preview[k] for k in ('source_hash','preview_hash')):
                raise Problem(409,'Neue Fahrtvorschau ausdrücklich prüfen und bestätigen.')
            if not preview['can_approve']:raise Problem(409,'Offene Kilometerfakten vor Freigabe vervollständigen.')
            if fresh['id'] in (employee['user_id'],sources['trips'][0]['submitted_by']):
                raise Problem(409,'Eigene oder selbst eingereichte Fahrt braucht eine andere prüfende Person.')
            if (old is None)!=(corrected is None) or old and old['id']!=corrected['id']:
                raise Problem(409,'Ausdrücklich genau die bisherige Abrechnung fortschreiben.')
            calc={k:v for k,v in preview.items() if k in ('rule_version','rule_hash','table_hash','days','totals','blockers',
                'can_approve','can_pay','expense_items','payroll_required','transport_sources','ground_calendar_sources','mixed_program_sources','mileage_items')}
            record=self._append('settlement',fresh,employee,data['id'],dict(status='approved',details=base,sources=sources,
                calculation=calc,source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],command_hash=fingerprint),old,pdf=True)
            for claim in claims(record):
                self.db.execute('INSERT INTO business_travel_claims(settlement_id,revision,employee_id,claim_key,source_kind,source_id,source_revision,amount_minor,content_hash) VALUES(?,?,?,?,?,?,?,?,?)',
                    tuple(claim.values())+(_sha(claim),))
            return record
        return self._command(actor,'settlement','settlement.approve',data,save,permission='personnel.approve',own=False)


def validate_mileage_record(api,value,previous):
    """Verify stored V4 arithmetic, original sources, independent review and receipt binding."""
    helper=MileageTravel(api.office,clock=api.clock)
    if previous is not None and not is_mileage(previous):raise Problem(409,'Historischer Kilometervertrag wurde gewechselt.')
    if value['kind']=='trip':
        details,sources,unused=helper._trip_details(None,dict(id=value['employee_id']),value['details'],current=False)
        if moment(details['returned_at'])>moment(value['created_at']):raise Problem(409,'Historische Fahrt lag noch in der Zukunft.')
        if details!=value['details'] or sources!=value['sources']:raise Problem(409,'Historische Kilometerquellen wurden verändert.')
        status=value['status']
        if status=='draft':
            if previous and previous['status']=='submitted' or any(value[k] is not None for k in ('submitted_by','submitted_at','decision')):
                raise Problem(409,'Fremde Einreichung im Fahrtentwurf.')
        elif status=='submitted':
            if previous is None or previous['status'] not in ('draft','rejected') or value['submitted_by']!=value['created_by'] or value['submitted_at']!=value['created_at'] or value['decision'] is not None:
                raise Problem(409,'Unbelegte Kilometer-Einreichung.')
            if any(value[k]!=previous[k] for k in ('details','sources','correction_reason')):raise Problem(409,'Einreichung verändert Originale.')
        elif status=='rejected':
            user=api.db.execute('SELECT user_id FROM business_employees WHERE id=?',(value['employee_id'],)).fetchone()['user_id']
            if previous is None or previous['status']!='submitted' or value['created_by'] in (value['submitted_by'],user) or value['submitted_by']!=previous['submitted_by'] or value['submitted_at']!=previous['submitted_at'] or value['decision']['by']!=value['created_by']:
                raise Problem(409,'Unbelegte unabhängige Fahrtprüfung.')
            text(value['decision']['reason'],'Prüfgrund',1000,required=True)
            if any(value[k]!=previous[k] for k in ('details','sources','correction_reason')):raise Problem(409,'Zurückweisung verändert Originale.')
        else:raise Problem(409,'Unbekannter Kilometer-Fahrtstatus.')
        return True
    if value['kind']!='settlement':raise Problem(409,'Unbekanntes Kilometeroriginal.')
    d=value['details'];sources=value['sources'];person=sources['employee']
    _shape(person,('id','user_id','name','revision'),('id','user_id','name','revision'))
    originals=[json.loads(r['result_json']) for r in api.db.execute("SELECT result_json FROM business_planning_requests WHERE operation='employee'")]
    originals=[x for x in originals if x.get('id')==value['employee_id'] and x.get('revision')==person['revision']]
    current=api.db.execute('SELECT user_id FROM business_employees WHERE id=?',(value['employee_id'],)).fetchone()
    if len(originals)!=1 or current is None or current['user_id']!=person['user_id'] or any(originals[0].get(k)!=v for k,v in person.items()) or value['created_by']==person['user_id'] or value['status']!='approved':
        raise Problem(409,'Historische Person/Gegenfreigabe fehlt.')
    if len(sources['trips'])!=1 or sources['history_trips'] or sources['expenses']:raise Problem(409,'Fremde Kilometerquellen.')
    trip=sources['trips'][0]
    if not is_mileage(trip) or trip['status']!='submitted' or trip['submitted_by']==value['created_by'] or api._resolve(None,'trip',_ref(trip),value['employee_id'],current=False)!=trip:
        raise Problem(409,'Unabhängige ursprüngliche Fahrt fehlt.')
    validate_record(api,trip)
    if sources['sites']!=trip['sources']['sites'] or sources['files']!=trip['sources']['files']:raise Problem(409,'Andere Kilometeroriginale gebunden.')
    for site in sources['sites']:
        if api._resolve(None,'site',_ref(site),value['employee_id'],current=False)!=site:raise Problem(409,'Andere Stättenfassung gebunden.')
        validate_record(api,site)
    fields=('employee_id','trip_refs','period_from','period_to','settlement_unit','tax_choice','requested_meal_minor','requested_lodging_minor','correction_of','review_note')
    _shape(d,fields+('payroll_month',),fields)
    if d['employee_id']!=value['employee_id'] or d['trip_refs']!=[_ref(trip)] or d['period_from']!=_date_of(trip) or d['period_to']!=_date_of(trip) or d.get('payroll_month') is not None:
        raise Problem(409,'Andere ursprüngliche Fahrt/Person/Tag gebunden.')
    text(d['review_note'],'Prüfvermerk',2000,required=True)
    if (previous is None)!=(d['correction_of'] is None) or previous and (_ref(previous)!=d['correction_of'] or previous['sources']['trips'][0]['id']!=trip['id'] or previous['details']['period_from']!=d['period_from']):
        raise Problem(409,'Unpassender Kilometer-Korrekturvorgänger.')
    from travel_allowance_cash import _paid
    after=integer(sources['after_payment_sequence'])
    if after>api.db.execute('SELECT COALESCE(MAX(sequence),0) AS n FROM business_travel_payments').fetchone()['n']:raise Problem(409,'Fremde Zahlungsgrenze.')
    calc=calculate([trip],sources['sites'],settlement_unit=d['settlement_unit'],tax_choice=d['tax_choice'],
        requested_meal_minor=d['requested_meal_minor'],requested_lodging_minor=d['requested_lodging_minor'],already_paid_minor=_paid(api,value['id'],through_sequence=after))
    if calc!=value['calculation'] or not calc['can_approve']:raise Problem(409,'Historische Kilometerberechnung ist nicht reproduzierbar.')
    preview=_preview_value(value['employee_id'],d,value['source_hash'],trip,sources['sites'],calc)
    if preview['preview_hash']!=value['preview_hash']:raise Problem(409,'Unpassender ursprünglicher Kilometer-Vorschauhash.')
    expected=[dict(x,content_hash=_sha(x)) for x in claims(value)]
    actual=[dict(r) for r in api.db.execute('SELECT * FROM business_travel_claims WHERE settlement_id=? AND revision=? ORDER BY claim_key',(value['id'],value['revision']))]
    if sorted(expected,key=lambda x:x['claim_key'])!=actual:raise Problem(409,'Unpassende ursprüngliche Streckenbelegung.')
    return True


def methods(path):
    if not path.startswith('/personnel/travel/mileage/'):return None
    tail=path.split('/mileage/',1)[1]
    if not (tail in ('catalog','sources','trips','settlements','payments','settlements/preview')
            or re.fullmatch(r'(?:trips|settlements|payments)/'+ID+r'(?:/history)?',tail)
            or re.fullmatch(r'trips/'+ID+r'/(?:submit|reject)',tail)
            or re.fullmatch(r'settlements/'+ID+r'/export',tail)
            or re.fullmatch(r'requests/'+ID,tail)):
        return None
    return __import__('business_travel_allowances').methods(path.replace('/mileage/','/',1))


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'HTTP-Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=MileageTravel(office);tail=path.split('/mileage/',1)[1].split('/')
    query=data.get('_query',{});body={k:v for k,v in data.items() if k!='_query'}
    if method=='GET':
        if body:raise Problem(400,'Keine zusätzlichen Abrufinhalte.')
        if tail==['catalog']:
            from business_foundation import _fresh,permissions
            fresh=_fresh(office,actor)
            if not {'personnel.read','time.own'}&set(permissions(office,fresh)):raise Problem(403,'Personal- oder eigener Zeitzugriff erforderlich.')
            _shape(query,());result=catalog()
        elif tail==['sources']:
            _shape(query,('employee_id',),('employee_id',));result=api.sources(actor,query['employee_id'])
        elif tail[0]=='requests':_shape(query,());result=api.status(actor,tail[1]);api._only(result['result'])
        else:
            from business_travel_allowances import _query_revision
            kind={'trips':'trip','settlements':'settlement','payments':'payment'}.get(tail[0])
            if kind is None:raise Problem(404,'Unbekannter Kilometerpfad.')
            if len(tail)==1:
                _shape(query,('employee_id',),('employee_id',));result=api.listing(actor,kind,query['employee_id'])
            elif len(tail)==2:
                _shape(query,('revision',));result=api.get(actor,kind,tail[1],_query_revision(query))
            elif tail[2]=='history':_shape(query,());result=api.get(actor,kind,tail[1],history=True)
            else:
                _shape(query,('revision','format'),('format',));api._only(api._get('settlement',tail[1],_query_revision(query)))
                content,mime=api.export(actor,tail[1],_query_revision(query),query['format']);return content,200,mime
    else:
        if query:raise Problem(400,'Keine zusätzlichen Schreibfilter.')
        if tail==['trips']:result=api.save_trip(actor,body)
        elif tail==['settlements','preview']:result=api.preview(actor,body)
        elif tail==['settlements']:result=api.approve(actor,body)
        elif tail==['payments']:
            from travel_allowance_cash import record_payment
            reference=body.get('settlement_ref')
            if not isinstance(reference,dict):raise Problem(400,'Unveränderte Kilometerabrechnung auswählen.')
            api._only(api._get('settlement',reference.get('id'),reference.get('revision')))
            result=record_payment(api,actor,body)
        else:result=api.trip_action(actor,tail[1],tail[2],body)
    return result,200,'application/json'
