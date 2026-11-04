"""Private payroll evidence adapters; no inferred payments or public DTOs."""
from business_accounting import _evidence
from business_operations import identifier
from business_personnel_workflow import _sha,_shape,_integer
from business_payroll import _calculate_source
from core import Problem

COMPONENTS=('employee_tax','employee_social','employer_social','employer_levies','employer_flat_tax')
CATEGORIES=tuple('payroll_'+name for name in ('net',)+COMPONENTS)


def calculated(value):
    if not value['payroll_calculation_complete']:
        raise Problem(409,'Vollständig unterstützte Lohnberechnung erforderlich.')
    return dict(employee_tax=value['employee_tax_minor'],employee_social=value['employee_social_total_minor'],
        employer_social=value['employer_social_total_minor'],employer_levies=sum(value['employer_levies'].values()),
        employer_flat_tax=value['employer_flat_tax_minor'])


def part_key(employee_id,payment):
    return _sha([employee_id,payment['paid_on'],_evidence(payment['payment_reference'])[1]])


def require_preserved_actual_net_parts(office,employee_id,month,payments):
    """A new Source4 account must retain already adopted actual money facts.

    This is a fresh-write guard only. Historical source reconstruction remains
    tied to its accepted original, including after later payment corrections.
    """
    from business_schema import _tables
    if 'business_payroll_cash_batches' not in _tables(office):return
    from business_payroll_cash import PayrollCash
    api=PayrollCash(office);scope=employee_id+':'+month
    full={part_key(employee_id,value):value['amount_minor'] for value in payments}
    for row in api._latest():
        for value in api._private(row)['transactions']:
            if value['component']=='net' and value['scope_key']==scope and full.get(value['part_key'])!=value['amount_minor']:
                raise Problem(409,'Bereits tatsächlich übernommene Nettozahlungen müssen mit unverändertem Tag, Betrag und Originalreferenz enthalten bleiben; zuerst deren bestehenden Zahlungsnachweis ausdrücklich korrigieren.')


class Sources:
    def __init__(self,api):
        self.api,self.hr,self.accounts,self.payroll=api,api.hr,api.accounts,api.accounts.payroll

    def file(self,actor,file_id,employee_id=None):
        row=self.hr._file(file_id,employee_id)
        if actor is not None:self.hr._employee(actor,row['employee_id'])
        if row['purpose']!='personnel':raise Problem(400,'Geschütztes Personaloriginal als Zahlungsnachweis erforderlich.')
        return self.hr._file_view(row)

    def account(self,actor,ref,*,current=True):
        record=self.accounts._get(ref['account_record_id'],ref['revision'])
        if actor is not None:self.hr._employee(actor,record['employee_id'])
        if record['content_hash']!=ref['content_hash'] or record['kind'] not in ('payment','carryover'):
            raise Problem(409,'Genau passender Lohnkonto-Zahlungsnachweis erforderlich.')
        self.accounts._verify_source5(record)
        details=record['details'];origin=self.file(actor,record['source_file']['id'],record['employee_id'])
        if any(origin[key]!=record['source_file'][key] for key in record['source_file']):
            raise Problem(409,'Lohnkonto-Original wurde verändert.')
        calculation=record['sources']['run']['calculation'] if record['kind']=='payment' else record['sources']['calculation']
        normalized,sources,unused=self.accounts._normalize(record['employee_id'],record['kind'],details,rule_version=calculation['rule_version'])
        if normalized!=details or sources!=record['sources'] or details['tax_free_payments_minor']:
            raise Problem(409,'Unveränderten unterstützten Barlohn ohne zusätzliche steuerfreie Bezüge auswählen.')
        if record['kind']=='payment':
            run=record['sources']['run'];month=run['source']['month']
            if run['source'].get('source_schema_version') in (3,4,5):self.payroll._verify_calculation_record(run)
            if _calculate_source(run['source'],rule_version=calculation['rule_version'])!=calculation:
                raise Problem(409,'Lohnrechnung besteht die Quellenprüfung nicht.')
            if current and self.payroll._row(run['id'],'run')['revision']!=run['revision']:
                raise Problem(409,'Für neue Zahlungen den aktuellen wirksamen Lohnlauf nachweisen.')
        else:
            month=details['month']
            if details['status']!='active' or current and any(run['source']['month']==month for run in self.payroll._all('run',record['employee_id'])):
                raise Problem(409,'Nur aktiven Monatsvortrag ohne zusätzlichen lokalen Lauf verwenden.')
        calculated(calculation)
        if current and (self.accounts._get(record['id'])['revision']!=record['revision']
                or self.accounts._get(details['identity_id'])['revision']!=details['identity_revision']):
            raise Problem(409,'Lohnkonto-/Identitätsnachweis wurde ergänzt; aktuelle Fassung prüfen.')
        if current and any(self.accounts._get(value['identity']['id'])['revision']!=value['identity']['revision']
                for value in record['sources'].get('identity_intervals',[])):
            raise Problem(409,'Ein Identitätsnachweis der tatsächlichen Teilzeiträume wurde korrigiert; Zahlung neu belegen.')
        return dict(record=record,month=month,calculation=calculation,scope_key=record['employee_id']+':'+month,source_file=origin)

    def remittance(self,actor,ref,*,current=True):
        if ref['source_kind']=='carryover':
            return self.account(actor,dict(account_record_id=ref['id'],revision=ref['revision'],content_hash=ref['content_hash']),current=current)
        if ref['source_kind']!='run':raise Problem(400,'Lokalen Lohnlauf oder belegten Monatsvortrag auswählen.')
        record=self.payroll._event(self.payroll._row(ref['id'],'run',ref['revision']))
        if actor is not None:self.hr._employee(actor,record['employee_id'])
        if record['content_hash']!=ref['content_hash'] or current and self.payroll._row(record['id'],'run')['revision']!=record['revision']:
            raise Problem(409,'Genau passende wirksame Lohnrevision auswählen.')
        calculation=record['calculation'];calculated(calculation)
        if record['source'].get('source_schema_version') in (3,4,5):self.payroll._verify_calculation_record(record)
        if _calculate_source(record['source'],rule_version=calculation['rule_version'])!=calculation:
            raise Problem(409,'Lohnrechnung besteht die Quellenprüfung nicht.')
        profile=record['source']['profile'];origin=self.file(actor,profile['source_file']['id'],record['employee_id'])
        if any(origin[key]!=profile['source_file'][key] for key in profile['source_file']):
            raise Problem(409,'Lohnprofil-Original wurde verändert.')
        month=record['source']['month']
        return dict(record=record,month=month,calculation=calculation,scope_key=record['employee_id']+':'+month,source_file=origin)

    def build(self,actor,body,*,current=True):
        records=[];transactions=[];seen=set()
        if not isinstance(body['sources'],list) or not 1<=len(body['sources'])<=100:
            raise Problem(400,'Ein bis hundert ausdrücklich ausgewählte Lohnquellen erforderlich.')
        for ref in body['sources']:
            fields=('account_record_id','revision','content_hash','payment_indexes') if body['kind']=='net' else ('source_kind','id','revision','content_hash','amounts')
            _shape(ref,fields,fields);_integer(ref['revision'],1)
            key=ref.get('account_record_id',ref.get('id'));identifier(key)
            if key in seen:raise Problem(400,'Jede Lohnquelle höchstens einmal auswählen.')
            seen.add(key)
            source=self.account(actor,ref,current=current) if body['kind']=='net' else self.remittance(actor,ref,current=current)
            record=source['record'];records.append(source)
            if body['kind']=='net':
                indexes=ref['payment_indexes'];payments=record['details']['payments']
                if (not isinstance(indexes,list) or not indexes or any(type(i) is not int or not 0<=i<len(payments) for i in indexes)
                        or indexes!=sorted(set(indexes))):raise Problem(400,'Eindeutige geordnete Zahlungsteil-Indizes auswählen.')
                for index in indexes:
                    payment=payments[index]
                    transactions.append(dict(employee_id=record['employee_id'],scope_key=source['scope_key'],source_id=record['id'],source_revision=record['revision'],
                        part_index=index,part_key=part_key(record['employee_id'],payment),paid_on=payment['paid_on'],amount_minor=payment['amount_minor'],
                        reference=payment['payment_reference'],evidence_key=_evidence(payment['payment_reference'])[1],component='net',original_sha256=source['source_file']['sha256']))
            else:
                _shape(ref['amounts'],COMPONENTS,COMPONENTS)
                for name in COMPONENTS:
                    amount=ref['amounts'][name]
                    if type(amount) is not int or not 0<=amount<=10**12:raise Problem(400,'Nichtnegative tatsächliche Abführungsanteile in ganzen Cent erforderlich.')
                    if amount:
                        transactions.append(dict(employee_id=record['employee_id'],scope_key=source['scope_key'],source_id=record['id'],source_revision=record['revision'],
                            part_index=None,part_key=None,component=name,amount_minor=amount))
        if body['kind']=='net':
            if body['settlement'] is not None:raise Problem(400,'Nettozahlungstag und Nachweis stammen ausschließlich aus den ausgewählten Lohnkontoteilen.')
        else:
            proof=body['settlement'];fields=('paid_on','payment_reference','amount_minor','source_file_id','employee_id','sha256')
            _shape(proof,fields,fields)
            if proof['employee_id'] not in {source['record']['employee_id'] for source in records}:raise Problem(404,'Abführungsoriginal gehört nicht zu einer ausgewählten Personalquelle.')
            original=self.file(actor,proof['source_file_id'],proof['employee_id'])
            if original['sha256']!=proof['sha256']:raise Problem(409,'Abführungsoriginal stimmt nicht überein.')
            if type(proof['amount_minor']) is not int or proof['amount_minor']<=0 or proof['amount_minor']!=sum(item['amount_minor'] for item in transactions):
                raise Problem(400,'Tatsächlicher Abführungsbetrag muss den ausdrücklich belegten Anteilen entsprechen.')
            for item in transactions:
                item.update(paid_on=proof['paid_on'],reference=_evidence(proof['payment_reference'])[0],evidence_key=_evidence(proof['payment_reference'])[1],original_sha256=original['sha256'])
        for item in transactions:
            from payroll_de_2026 import day
            paid=day(item['paid_on'])
            if paid.year!=2026 or item['paid_on'][:7]<item['scope_key'][-7:] or current and item['paid_on']>self.hr.now()[:10]:
                raise Problem(400,'Nur tatsächliche Zahlungen ab dem Abrechnungsmonat bis heute im Jahr 2026 sind unterstützt.')
        if not transactions:raise Problem(400,'Mindestens einen tatsächlichen Zahlungsbetrag auswählen.')
        return records,transactions
