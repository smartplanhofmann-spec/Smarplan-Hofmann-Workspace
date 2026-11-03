"""Read-only yearly projection of immutable effective payroll revisions.

This is a calculation ledger, not a claim of a complete statutory wage account.
Exports are deterministic and tied to the exact preview snapshot.
"""
import csv
import io
from xml.sax.saxutils import escape

from core import canonical
from business_personnel_workflow import _sha
from payroll_de_2026 import month_range

AMOUNTS = ('gross_minor','individual_wage_tax_minor','solidarity_minor','church_tax_minor',
    'employee_tax_minor','employee_social_total_minor','employer_social_total_minor',
    'employer_flat_tax_minor','employer_total_excluding_accident_insurance_minor',
    'net_minor','payout_minor','employee_additional_payment_minor')
COMPONENTS = ('health_general','health_additional','pension','unemployment','care')
LEVIES = ('u1','u2','insolvency')
INDIVIDUAL_TAX = ('individual_wage_tax_minor','solidarity_minor','church_tax_minor')
LABELS = dict(gross_minor='Brutto',individual_wage_tax_minor='Lohnsteuer',solidarity_minor='Solidaritätszuschlag',
    church_tax_minor='Kirchenlohnsteuer',employee_tax_minor='Arbeitnehmersteuern',
    employee_social_total_minor='Arbeitnehmer-SV',employer_social_total_minor='Arbeitgeber-SV',
    employer_flat_tax_minor='Arbeitgeber-Pauschsteuer',
    employer_total_excluding_accident_insurance_minor='Arbeitgeberbetrag ohne Unfallversicherung',
    net_minor='Netto',payout_minor='Auszahlungsbetrag laut Berechnung',
    employee_additional_payment_minor='Zusätzlicher Arbeitnehmerbeitrag',
    health_general='Krankenversicherung allgemein',health_additional='KV-Zusatzbeitrag',
    pension='Rentenversicherung',unemployment='Arbeitslosenversicherung',care='Pflegeversicherung',
    u1='U1',u2='U2',insolvency='Insolvenzgeldumlage')
LIMITATIONS = [
    'Summen enthalten ausschließlich die aufgeführten wirksamen Monatsrevisionen; fehlende Monate und Vortragswerte werden nicht als null ergänzt.',
    'Korrekturdifferenzen sind Nachweise und werden nicht zusätzlich zu den wirksamen Monatsbeträgen summiert.',
    'Kein vollständiges gesetzliches Lohnkonto: Arbeitgeber-/Arbeitnehmer-Steuerkennungen, weitere Pflichtangaben und erforderliche Vorträge sind hier nicht vollständig erfasst.',
    'Auslagen, Unfallversicherung und Sonderfälle außerhalb des unterstützten Rechenumfangs sind nicht enthalten.',
    'Keine Zahlung, amtliche Übermittlung, Annahmebestätigung oder Systemzulassung.',
]


def _total(records,key,group=None):
    if not records:
        return None
    values=[]
    for record in records:
        calculation=record['calculation']
        value=calculation[group][key] if group else calculation[key]
        # Under the explicit flat-tax method no individual tax is withheld.
        # Preserve the original nulls in the per-month calculation archive.
        if group is None and key in INDIVIDUAL_TAX and calculation['scope']=='commercial_minijob_flat_tax':
            value=0
        if value is None:
            return None
        values.append(value)
    return sum(values)


def _ref(record):
    return {key:record[key] for key in ('id','revision','content_hash')}


def _account(record,accounts):
    missing=dict(complete=False,issues=['payment_evidence_missing'],identity_ref=None,payment_ref=None,
        payments=[],tax_free_payments_minor=None)
    if not record['calculation']['payroll_calculation_complete']:
        missing['issues']=['tax_calculation_incomplete'];return missing
    evidence=record.get('account')
    if evidence is None:
        evidence=next((item for item in accounts if item['kind']=='payment' and item['details']['run_id']==record['id']
            and item['details']['run_revision']==record['revision']),None)
    if evidence is None:
        return missing
    identity=evidence['sources']['identity']
    latest=next((item for item in accounts if item['id']==identity['id']),None)
    issues=[]
    if latest is None or latest['revision']!=identity['revision']:
        issues.append('identity_revision_outdated')
    return dict(complete=not issues,issues=issues,identity_ref=_ref(identity),payment_ref=_ref(evidence),
        payments=evidence['details']['payments'],tax_free_payments_minor=evidence['details']['tax_free_payments_minor'])


def build_ledger(employee,year,records,histories,accounts=(),carry_histories=None):
    by_month={record['source']['month']:record for record in records}
    months=[]; corrections=[]
    for number in range(1,13):
        month=year+'-'+str(number).zfill(2)
        record=by_month.get(month)
        item=dict(month=month,status='missing',run_id=None,revision=None,content_hash=None,
            calculation=None,source_refs=None,origin=None,carryover_id=None,wage_account=dict(
                complete=False,issues=['calculation_missing'],identity_ref=None,payment_ref=None,payments=[],tax_free_payments_minor=None))
        if record:
            source=record['source']
            item.update(status='complete' if record['calculation']['payroll_calculation_complete'] else 'social_only',
                run_id=record['id'] if record.get('origin')!='external_carryover' else None,
                carryover_id=record['id'] if record.get('origin')=='external_carryover' else None,
                origin=record.get('origin','local'),revision=record['revision'],content_hash=record['content_hash'],
                calculation=record['calculation'],source_refs={kind:_ref(source[kind]) if source[kind] else None
                    for kind in ('profile','preparation')},wage_account=_account(record,accounts))
            for prior in histories[record['id']]:
                if prior['revision']>1:
                    corrections.append(dict(month=month,run_id=prior['id'],revision=prior['revision'],
                        previous_hash=prior['previous_hash'],content_hash=prior['content_hash'],
                        reason=prior['correction_reason'],delta=prior['delta'],created_at=prior['created_at']))
        months.append(item)
    for chain in (carry_histories or {}).values():
        previous=None
        for record in chain:
            if previous:
                delta={}
                for key in AMOUNTS:
                    before=previous['sources']['calculation'][key] if previous['details']['status']=='active' else 0
                    after=record['sources']['calculation'][key] if record['details']['status']=='active' else 0
                    delta[key]=after-before if before is not None and after is not None else None
                corrections.append(dict(month=record['details']['month'],run_id=record['id'],revision=record['revision'],
                    previous_hash=record['previous_hash'],content_hash=record['content_hash'],reason=record['correction_reason'],
                    delta=delta,created_at=record['created_at'],origin='external_carryover',effect='projection_only'))
            previous=record
    missing=[item['month'] for item in months if item['status']=='missing']
    partial=[item['month'] for item in months if item['status']=='social_only']
    totals={key:_total(records,key) for key in AMOUNTS}
    for group,keys in (('employee_contributions',COMPONENTS),('employer_contributions',COMPONENTS),('employer_levies',LEVIES)):
        totals[group]={key:_total(records,key,group) for key in keys}
    selected=[]
    for account in accounts:
        details=account['details']
        if (account['kind']=='identity' and details['valid_from']<=year+'-12-31' and details['valid_to']>=year+'-01-01'
                or account['kind']=='payment' and account['sources']['run']['source']['month'].startswith(year+'-')
                or account['kind']=='carryover' and details['month'].startswith(year+'-')):
            selected.append(account)
    identities=[account for account in selected if account['kind']=='identity']
    periods={(item['details']['employment_from'],item['details']['employment_to']) for item in identities}
    expected=set()
    for first,last in periods:
        for item in months:
            start,end=month_range(item['month'])
            if end.isoformat()>=first and (last is None or start.isoformat()<=last):
                expected.add(item['month'])
    account_issues=[] if len(periods)==1 else ['employment_period_missing' if not periods else 'employment_periods_conflict']
    complete_months={item['month'] for item in months if item['wage_account']['complete']}
    account_missing=sorted(expected-complete_months)
    field_complete=bool(records) and all(item['wage_account']['complete'] for item in months if item['status']!='missing')
    statutory_complete=field_complete and bool(expected) and not account_missing and not account_issues
    limitations=list(LIMITATIONS)
    limitations[2]='Feldvollständigkeit gilt nur für die belegten unterstützten Standardfälle nach § 4 LStDV / § 41 EStG; keine externe Fachabnahme und kein amtlicher Prüfexport nach der Digitalen LohnSchnittstelle.'
    ledger=dict(schema_version=1,employee={key:employee[key] for key in ('id','name')},year=year,currency='EUR',
        months=months,recorded_months=len(records),missing_months=missing,partial_months=partial,
        calendar_year_complete=not missing,tax_totals_complete=bool(records) and not partial,
        annual_totals_complete=not missing and not partial,totals_scope='recorded_effective_months_only',
        totals=totals,correction_history=corrections,statutory_wage_account_complete=statutory_complete,
        supported_wage_account_fields_complete=field_complete,expected_employment_months=sorted(expected),
        account_missing_months=account_missing,account_completeness_issues=account_issues,account_records=selected,
        recorded_tax_free_payments_minor=sum(item['wage_account']['tax_free_payments_minor'] for item in months
            if item['status']!='missing') if field_complete else None,digital_audit_export_compliant=False,
        limitations=limitations,statutory_report_status='not_transmitted',official_system_approval=False)
    ledger['snapshot_hash']=_sha(ledger)
    return ledger


def _csv(ledger):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream,delimiter=';',lineterminator='\r\n')
    def row(values):
        safe=[]
        for value in values:
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
                value="'"+value
            safe.append('' if value is None else value)
        writer.writerow(safe)
    row(['metadata','year',ledger['year'],'employee_id',ledger['employee']['id'],'snapshot_hash',ledger['snapshot_hash']])
    row(['metadata','employee_name',ledger['employee']['name'],'totals_scope',ledger['totals_scope']])
    row(['metadata','report_status','not_transmitted','system_approval','false','statutory_wage_account_complete',str(ledger['statutory_wage_account_complete']).lower()])
    for note in ledger['limitations']:
        row(['limitation',note])
    fields=list(AMOUNTS)+[group+'.'+key for group,keys in (('employee_contributions',COMPONENTS),
        ('employer_contributions',COMPONENTS),('employer_levies',LEVIES)) for key in keys]
    row(['type','month','status','run_id','revision','content_hash',*fields,'reason'])
    def values(calculation):
        if calculation is None:
            return [None]*len(fields)
        return [calculation[field] if '.' not in field else calculation[field.split('.')[0]][field.split('.')[1]] for field in fields]
    for item in ledger['months']:
        row(['month',item['month'],item['status'],item['run_id'],item['revision'],item['content_hash'],*values(item['calculation']),''])
        if item['calculation'] and item['calculation'].get('transition'):
            row(['transition_assessment',item['month'],item['calculation']['rule_version'],
                item['calculation']['rules_sha256'],canonical(item['calculation']['transition'])])
    row(['totals',ledger['year'],ledger['totals_scope'],'','',ledger['snapshot_hash'],*values(ledger['totals']),''])
    for item in ledger['correction_history']:
        delta=[item['delta'].get(field) for field in fields]
        row(['correction',item['month'],'not_added_to_totals',item['run_id'],item['revision'],item['content_hash'],*delta,item['reason']])
    for record in ledger['account_records']:
        row(['account_evidence',record['kind'],record['id'],record['revision'],record['content_hash'],record['source_file']['id'],record['source_file']['sha256']])
        for key,value in record['details'].items():
            row(['account_field',record['id'],key,canonical(value) if isinstance(value,(list,dict)) else value])
    return ('\ufeff'+stream.getvalue()).encode('utf-8')


def _pdf(ledger):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from reportlab.lib import colors
    stream=io.BytesIO();styles=getSampleStyleSheet()
    story=[Paragraph('Abrechnungsjahressicht '+ledger['year'],styles['Title'])]
    def line(value):
        story.extend([Paragraph(escape(str(value)),styles['Normal']),Spacer(1,5)])
    def amount(value):
        if value is None:
            return 'offen / entfällt'
        sign='-' if value<0 else ''
        return sign+str(abs(value)//100)+','+str(abs(value)%100).zfill(2)
    line(ledger['employee']['name']+' / '+ledger['employee']['id'])
    line('Snapshot-SHA256: '+ledger['snapshot_hash'])
    for note in ledger['limitations']:
        line(note)
    line('Fehlende Monate: '+(', '.join(ledger['missing_months']) or 'keine'))
    line('Monate mit offener Steuerberechnung: '+(', '.join(ledger['partial_months']) or 'keine'))
    line('Pflichtfelder des unterstützten Lohnkontofalls vollständig: '+('ja' if ledger['statutory_wage_account_complete'] else 'nein'))
    line('Beschäftigungsmonate ohne vollständige Nachweise: '+(', '.join(ledger['account_missing_months']) or 'keine; Beschäftigungszeitraum gesondert prüfen'))
    columns=['Monat','Revision','Brutto EUR','AN-SV EUR','AN-Steuer EUR','Netto EUR']
    rows=[columns]
    for item in ledger['months']:
        calculation=item['calculation']
        rows.append([item['month'],str(item['revision']) if item['revision'] else 'fehlt',
            *[amount(calculation[key]) if calculation else 'fehlt' for key in ('gross_minor',
                'employee_social_total_minor','employee_tax_minor','net_minor')]])
    table=Table(rows,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.whitesmoke),('GRID',(0,0),(-1,-1),.3,colors.grey),
        ('FONTSIZE',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.extend([table,Spacer(1,12),Paragraph('Summen der aufgeführten wirksamen Monate',styles['Heading2'])])
    for key in AMOUNTS:
        line(LABELS[key]+': '+amount(ledger['totals'][key])+' EUR')
    for label,group in (('Arbeitnehmer','employee_contributions'),('Arbeitgeber','employer_contributions'),('Arbeitgeber-Umlagen','employer_levies')):
        for key,value in ledger['totals'][group].items():
            line(label+' / '+LABELS[key]+': '+amount(value)+' EUR')
    story.append(Paragraph('Quellen und Korrekturen',styles['Heading2']))
    for item in ledger['months']:
        if item['run_id'] or item['carryover_id']:
            line(item['month']+': '+(item['run_id'] or item['carryover_id'])+' Revision '+str(item['revision'])+' / '+item['content_hash'])
            for kind,source in item['source_refs'].items():
                if source:
                    line(kind+': '+source['id']+' Revision '+str(source['revision'])+' / '+source['content_hash'])
            if item['calculation'].get('transition'):
                transition=item['calculation']['transition']
                line('Midijob-Regel: '+item['calculation']['rule_version']+' / '+item['calculation']['rules_sha256'])
                line('Prognose '+amount(transition['regular_monthly_gross_minor'])+' EUR; Monatsfall '+transition['regime'])
                line('Gesamtbasis '+amount(transition['total_assessment_minor'])+' EUR; AN-Basis '+amount(transition['employee_assessment_minor'])+
                    ' EUR; Umlagebasis '+amount(transition['levy_assessment_minor'])+' EUR')
    for correction in ledger['correction_history']:
        line(correction['month']+' Revision '+str(correction['revision'])+': '+correction['reason'])
        line('Vorgänger '+correction['previous_hash']+' / Ergebnis '+correction['content_hash'])
        for key,value in correction['delta'].items():
            line('Differenz '+LABELS[key]+': '+amount(value)+' EUR (nicht zusätzlich summiert)')
    story.append(Paragraph('Geschützte Lohnkontonachweise',styles['Heading2']))
    for account in ledger['account_records']:
        details=account['details']
        line(account['kind']+' / '+account['id']+' Revision '+str(account['revision'])+' / '+account['content_hash'])
        line('Original: '+account['source_file']['id']+' / '+account['source_file']['sha256'])
        if account['kind']=='identity':
            line(details['given_name']+' '+details['family_name']+', geboren '+details['date_of_birth'])
            line(details['address_line']+', '+details['postal_code']+' '+details['city']+', '+details['country_code'])
            line('Steuer-ID: '+details['tax_id']+' / Religionsmerkmal: '+details['religion_code'])
            line('Arbeitgeber: '+details['employer_name']+', '+details['employer_address']+' / Steuernummer: '+details['employer_tax_number'])
            line('Beschäftigung: '+details['employment_from']+' bis '+str(details['employment_to'] or 'fortdauernd'))
            line('Steuermerkmale: '+details['tax_source']+' vom '+details['tax_source_date']+' / gültig '+details['valid_from']+' bis '+details['valid_to'])
            line('Jahresfreibetrag: '+amount(details['tax_allowance_yearly_minor'])+' EUR / Jahreshinzurechnung: '+amount(details['tax_addition_yearly_minor'])+' EUR')
            profile=account['sources']['profile']['profile']
            line('Steuerklasse: '+str(profile['tax_class'])+' / Kinderfreibeträge in halben Einheiten: '+str(profile['tax_children_half_units']))
            line('Monatsfreibetrag: '+amount(profile.get('tax_allowance_monthly_minor'))+' EUR / Monatshinzurechnung: '+amount(profile.get('tax_addition_monthly_minor'))+' EUR')
        else:
            for payment in details['payments']:
                line('Tatsächliche Nettozahlung '+payment['paid_on']+': '+amount(payment['amount_minor'])+' EUR / '+payment['payment_reference'])
            line('Zusätzliche steuerfreie Bezüge: '+amount(details['tax_free_payments_minor'])+' EUR / '+details['tax_free_basis'])
            line('Ausdrücklich bestätigter Fall: laufender Barlohn, keine weiteren Sach-/Sonderbezüge und keine U/S-Fälle.')
    SimpleDocTemplate(stream,invariant=1,pageCompression=0).build(story)
    return stream.getvalue()


def export_contents(ledger):
    return dict(json=canonical(ledger).encode('utf-8'),csv=_csv(ledger),pdf=_pdf(ledger))


def export_manifest(ledger,contents):
    media=dict(json='application/json; charset=utf-8',csv='text/csv; charset=utf-8',pdf='application/pdf')
    return {kind:dict(sha256=_sha(content),size=len(content),filename='lohn-jahressicht-'+ledger['year']+'-'+ledger['employee']['id']+'.'+kind,
        media_type=media[kind]) for kind,content in contents.items()}
