"""Explicit actual employee expenses; no assumed VAT or duplicate allowance."""
from core import Problem
from business_personnel_workflow import _shape


def calculate_expenses(trips):
    from payroll_travel_2026 import integer, day, moment, zone, _reference
    rows=[];seen=set();blockers=[];lodging={}
    for trip in trips:
        details=trip['details'];allocations=details.get('expense_allocations',[])
        if not isinstance(allocations,list) or len(allocations)>1000:raise Problem(400,'Begrenzte strukturierte Auslagenaufteilung erforderlich.')
        sources={_reference({k:e[k] for k in ('id','revision','content_hash')}):e for e in trip.get('sources',{}).get('expenses',[])}
        required={(_reference(ref),item['receipt_file_id']) for ref in details['expense_refs'] for item in sources.get(_reference(ref),{}).get('items',[])}
        supplied=set();first=moment(details['departed_at']).astimezone(zone(details['timezone'])).date();last=moment(details['returned_at']).astimezone(zone(details['timezone'])).date()
        for allocation in allocations:
            fields=('expense_ref','receipt_file_id','kind','business_minor','private_minor','provided_minor','review_note')
            _shape(allocation,fields,fields);key=_reference(allocation['expense_ref']);source=sources.get(key)
            if source is None:raise Problem(400,'Aufteilung benötigt die ausdrücklich gebundene Auslagenfassung.')
            matches=[i for i in source['items'] if i['receipt_file_id']==allocation['receipt_file_id']]
            if len(matches)!=1:raise Problem(400,'Genau eine vorhandene Originalposition auswählen.')
            item=matches[0];identity=(key,item['receipt_file_id'])
            if identity in supplied or item['receipt_sha256'] in seen:raise Problem(400,'Ein Original darf nur einmal in der Reiseabrechnung stehen.')
            supplied.add(identity);seen.add(item['receipt_sha256'])
            if source['status'] not in ('approved','reimbursed','reversed'):
                blockers.append(dict(code='expense_not_reviewed',text='Auslage benötigt eine unabhängige Freigabe.',source_ref=allocation['expense_ref']))
            if allocation['kind'] not in ('transport','lodging','incidental'):raise Problem(400,'Fahrt, Unterkunft oder Reisenebenkosten ausdrücklich zuordnen.')
            amounts=[integer(allocation[k]) for k in ('business_minor','private_minor','provided_minor')]
            if sum(amounts)!=item['amount_minor']:raise Problem(400,'Betrieblicher, privater und bereits gestellter Anteil müssen den Originalbetrag vollständig aufteilen.')
            if not isinstance(allocation['review_note'],str) or not allocation['review_note'].strip() or len(allocation['review_note'])>2000:
                raise Problem(400,'Begründete Prüfung des tatsächlichen Auslagenanteils erforderlich.')
            if not first<=day(item['date'])<=last:raise Problem(400,'Auslagenposition liegt außerhalb der ausgewählten Reise.')
            actual=sum(p['amount_minor']*(1 if p['kind']=='reimbursement' else -1) for p in source['payments'])
            if actual not in (0,source['total_minor']):raise Problem(409,'Bisherige Auslagenzahlungen sind nicht vollständig nachvollziehbar.')
            paid=allocation['business_minor'] if actual else 0
            if actual and (allocation['private_minor'] or allocation['provided_minor']):
                blockers.append(dict(code='legacy_nonbusiness_reimbursement',text='Bereits erstattete private oder gestellte Anteile benötigen eine belegte Rückzahlung beziehungsweise eigenständige Lohnkorrektur.',source_ref=allocation['expense_ref']))
            row=dict(expense_ref=allocation['expense_ref'],receipt_file_id=item['receipt_file_id'],receipt_sha256=item['receipt_sha256'],
                kind=allocation['kind'],date=item['date'],business_minor=amounts[0],private_minor=amounts[1],provided_minor=amounts[2],
                already_paid_minor=paid,review_note=allocation['review_note'])
            rows.append(row)
            if row['kind']=='lodging':lodging[(key,item['receipt_file_id'])]=row
        if set(details['expense_refs'][i]['id'] for i in range(len(details['expense_refs']))) and supplied!=required:
            blockers.append(dict(code='expense_allocation_missing',text='Jede ausgewählte Originalposition vollständig als tatsächliche Auslage aufteilen.',source_ref=None))
        used_nights=set()
        for night in details['overnights']:
            if night['claim_method']!='expense':
                if night['expense_ref'] is not None:raise Problem(400,'Originalauslage und Übernachtungspauschale dürfen sich nicht doppeln.')
                continue
            key=_reference(night['expense_ref']);file_id=night.get('expense_receipt_file_id')
            matches=[(ident,row) for ident,row in lodging.items() if ident[0]==key and (file_id is None or ident[1]==file_id)]
            if len(matches)!=1:raise Problem(400,'Tatsächliche Unterkunft benötigt eine eindeutig zugeordnete Originalposition.')
            ident,row=matches[0]
            # A single hotel invoice may substantiate several nights. The
            # original allocation remains one row and one reimbursement cap.
            used_nights.add(ident)
        for ident,row in lodging.items():
            if ident[0] in sources and ident not in used_nights:
                blockers.append(dict(code='lodging_night_binding',text='Tatsächliche Unterkunft benötigt den zugehörigen einzelnen Übernachtungsnachweis.',source_ref=row['expense_ref']))
    return dict(items=rows,allowance_minor=sum(r['business_minor'] for r in rows),already_paid_minor=sum(r['already_paid_minor'] for r in rows),blockers=blockers)


def ensure_expense_unreserved(office,expense,*,own_settlement=None):
    """One original cannot be paid by both the old and travel workflows."""
    from business_travel_allowances import installed,TravelAllowances
    if not installed(office):return
    keys={'expense:'+i['receipt_sha256'] for i in expense['items']}
    api=TravelAllowances(office)
    for row in office.db.execute('SELECT DISTINCT employee_id FROM business_travel_settlements'):
        for settlement in api._all('settlement',row['employee_id']):
            if settlement['id']==own_settlement:continue
            claimed={i['claim_key'] for i in office.db.execute('SELECT claim_key FROM business_travel_claims WHERE settlement_id=? AND revision=?',(settlement['id'],settlement['revision']))}
            if keys & claimed:raise Problem(409,'Auslagenoriginal ist in einer Reiseabrechnung gebunden; dort ausdrücklich korrigieren.')


def validate_expense_source(hr,expense):
    """Reconstruct the actual old approval/payment chain, not only its hashes."""
    from business_personnel_workflow import _validate_expense_transition
    employee=hr.db.execute('SELECT user_id FROM business_employees WHERE id=?',(expense['employee_id'],)).fetchone()
    previous=None
    for row in hr.db.execute("SELECT * FROM business_personnel_events WHERE id=? AND kind='expense' AND revision<=? ORDER BY revision",(expense['id'],expense['revision'])):
        value=hr._event(row)
        if value['revision']!=(previous['revision']+1 if previous else 1) or value['previous_hash']!=(previous['content_hash'] if previous else None) or value['employee_id']!=expense['employee_id']:
            raise Problem(409,'Unvollständige ursprüngliche Auslagenhistorie.')
        fields=('date','description','amount_minor','currency','receipt_file_id','project_id')
        normalized=hr._expense_payload(dict(purpose=value['purpose'],start_date=value['start_date'],end_date=value['end_date'],items=[{k:i[k] for k in fields} for i in value['items']]),expense['employee_id'])
        if any(value[k]!=v for k,v in normalized.items()):raise Problem(409,'Ursprüngliche Auslagenpositionen sind nicht reproduzierbar.')
        try:_validate_expense_transition(value,previous,employee['user_id'])
        except (ValueError,TypeError,KeyError) as error:raise Problem(409,'Ursprüngliche Auslagenfreigabe oder tatsächliche Zahlung ist nicht reproduzierbar.') from error
        previous=value
    if previous!=expense:raise Problem(409,'Genaue Auslagenquellenfassung fehlt.')
