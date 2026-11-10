"""Narrow employee statements derived from verified immutable payroll records.

No source profiles, facts, originals, entitlement reasons or tax identities leave
this adapter. It is routed through the existing payroll capability, without new
storage or a second payroll calculation. PDF generation happens outside locks.
"""
import io
import re

from core import Problem, canonical
from business_foundation import permissions, require_permission
from business_operations import transaction
from business_personnel_workflow import _sha, _shape
from workspace_api import BinaryAttachment

ID = r'[a-f0-9]{32}'
ROOT = '/payroll/employee-statements'
AMOUNTS = ('gross_minor', 'employee_social_total_minor', 'individual_wage_tax_minor',
           'solidarity_minor', 'church_tax_minor', 'employee_tax_minor', 'net_minor',
           'payout_minor', 'employee_additional_payment_minor', 'employer_flat_tax_minor')
CONTRIBUTIONS = ('health_general', 'health_additional', 'pension', 'unemployment', 'care')
LABELS = dict(gross_minor='Brutto', employee_social_total_minor='Arbeitnehmerbeiträge gesamt',
              individual_wage_tax_minor='Lohnsteuer', solidarity_minor='Solidaritätszuschlag',
              church_tax_minor='Kirchenlohnsteuer', employee_tax_minor='Arbeitnehmersteuern gesamt',
              net_minor='Netto', payout_minor='Berechneter Auszahlungsbetrag',
              employee_additional_payment_minor='Zusätzlicher Arbeitnehmerbeitrag',
              employer_flat_tax_minor='Arbeitgeber-Pauschsteuer')
BRANCH_LABELS = dict(health_general='Krankenversicherung', health_additional='KV-Zusatzbeitrag',
                    pension='Rentenversicherung', unemployment='Arbeitslosenversicherung', care='Pflegeversicherung')


def _revision(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[1-9]\d{0,7}', value):
        raise Problem(400, 'Eine gültige historische Fassung angeben.')
    return int(value)


def project(record):
    """Positive allowlist, including nested fields; never copy arbitrary extras."""
    source, calculation = record['source'], record['calculation']
    factor_oneoff=calculation.get('rule_version')=='de_2026_factor_claims_oneoff_v15'
    if (factor_oneoff or calculation.get('scope')=='regular_standard_factor_claims_oneoff') and (
            not factor_oneoff or source.get('source_schema_version')!=4
            or calculation.get('source_contract_version')!=2
            or calculation.get('scope')!='regular_standard_factor_claims_oneoff'
            or calculation.get('payroll_calculation_complete') is not True):
        raise Problem(409,'Der Faktor-Einmalbeleg benötigt seinen vollständigen ausdrücklich versionierten Originalfall.')
    source5 = source.get('source_schema_version') == 5
    source5_extra = None
    if source5:
        # A separate projection version accepts only the currently verified,
        # complete single-claim branch. Private source/group/event identities
        # are deliberately absent from the employee-facing statement.
        private = calculation.get('multiple_one_off_details', {})
        single = private.get('single_original_calculation', {})
        components, events = private.get('components', []), private.get('receipt_events', [])
        source5_extra = single.get('one_off_details', {})
        if (calculation.get('rule_version') != 'de_2026_multiple_oneoff_v7'
                or calculation.get('source_contract_version') != 1
                or calculation.get('scope') != 'regular_standard_multiple_oneoff'
                or calculation.get('payroll_calculation_complete') is not True
                or single.get('rule_version') != 'de_2026_oneoff_composition_v6'
                or single.get('payroll_calculation_complete') is not True
                or len(components) != 1 or len(events) != 1
                or components[0].get('remaining_claim_minor') != 0
                or components[0].get('claim_minor') != source5_extra.get('amount_minor')
                or events[0].get('gross_minor') != source5_extra.get('amount_minor')
                or events[0].get('receipt_date') != source5_extra.get('receipt_date')
                or any(calculation.get(key) != single.get(key) for key in AMOUNTS)):
            raise Problem(409, 'Dieser Mitarbeiterbeleg benötigt einen vollständig geprüften einzelnen Source5-Anspruch; eine ungeklärte Mehrfachgruppe bleibt gesperrt.')
    contributions = calculation['employee_contributions']
    narrow = {key: calculation[key] for key in AMOUNTS}
    narrow.update(rule_version=calculation['rule_version'], scope=calculation['scope'], currency='EUR',
                  payroll_calculation_complete=calculation['payroll_calculation_complete'],
                  employee_contributions=None if contributions is None else
                  {key: contributions[key] for key in CONTRIBUTIONS if key in contributions})
    periods = calculation.get('period_details')
    summary = None if periods is None else {
        name: [{key: item[key] for key in keys} for item in periods[name]]
        for name, keys in (
            ('employment_intervals', ('start', 'end', 'calendar_days')),
            ('tax_periods', ('start', 'end', 'lzz', 'tax_days')),
            ('social_periods', ('start', 'end', 'days', 'full_month')))}
    base = dict(schema_version=1, employee_id=record['employee_id'],
                employee_name=source['preparation']['snapshot']['employee']['name'],
                run_ref={key: record[key] for key in ('id', 'revision', 'content_hash')},
                month=source['month'], created_at=record['created_at'], calculation=narrow,
                period_summary=summary, transmission_status='not_transmitted',
                payment_status='not_evidenced_by_calculation')
    if source.get('source_schema_version') in (3, 4, 5):
        # A new projection version preserves every legacy statement/PDF byte.
        # Only the employee's own amounts and dates leave the private case.
        base['schema_version'] = 2
        narrow['net_deductions_minor'] = calculation['net_deductions_minor']
        base['earnings_summary'] = [
            dict(kind=item['kind'], dates=list(item['claim_dates']), gross_minor=item['gross_minor'])
            for item in periods['earnings']]
        base['travel_summary'] = {
            key: periods['travel'][key] for key in (
                'tax_free_external_minor', 'flat_taxable_payroll_minor',
                'individual_taxable_payroll_minor', 'benefit_in_kind_non_cash_minor', 'letter_m')}
        base['travel_summary']['employee_flat_tax_deduction_minor'] = (
            periods['flat_travel_tax']['employee_tax_minor'] if periods['flat_travel_tax'] else 0)
    if source.get('source_schema_version') in (4, 5):
        # Source4 carries private annual evidence. Only the employee's amounts
        # and the resulting year assignment belong in the employee statement.
        extra = source5_extra if source5 else calculation['one_off_details']
        base['schema_version'] = 4 if source5 else 5 if factor_oneoff else 3
        base['one_off_summary'] = dict(
            amount_minor=extra['amount_minor'], receipt_date=extra['receipt_date'],
            **{key: extra['assignment'][key] for key in ('tax_year', 'social_year', 'march_clause')},
            employee_contributions={key: extra['social']['employee_contributions'][key]
                                    for key in CONTRIBUTIONS},
            employee_social_total_minor=extra['social']['employee_total_minor'],
            individual_wage_tax_minor=extra['tax']['STS'], solidarity_minor=extra['tax']['SOLZS'],
            church_tax_minor=extra['church_tax_minor'])
    return dict(base, statement_hash=_sha(base))


def _money(value):
    if value is None:
        return 'Nicht ermittelt'
    sign = '-' if value < 0 else ''
    absolute = abs(value)
    return f'{sign}{absolute // 100:,}'.replace(',', '.') + f',{absolute % 100:02} EUR'


def render_pdf(statement):
    """Deterministic employee-only bytes; never call the private payroll renderer."""
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.utils import simpleSplit
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(595.28, 841.89), invariant=1, pageCompression=0)
    canvas.setTitle('Lohnnachweis ' + statement['month'])
    canvas.setAuthor('Smartplan')
    top = 790

    def line(value, title=False):
        nonlocal top
        font, size = ('Helvetica-Bold', 15) if title else ('Helvetica', 10)
        for part in simpleSplit(str(value), font, size, 495):
            if top < 50:
                canvas.showPage()
                top = 790
            canvas.setFont(font, size)
            canvas.drawString(50, top, part)
            top -= 16 if title else 14
        top -= 5

    line('Lohnnachweis ' + statement['month'], True)
    line(statement['employee_name'])
    line('Berechnungsfassung ' + str(statement['run_ref']['revision']))
    line('Erfasster Rechenstand: ' + statement['created_at'])
    calculation = statement['calculation']
    if not calculation['payroll_calculation_complete']:
        line('Unvollständiger Rechenumfang: Lohnsteuer und Netto sind noch nicht vollständig ermittelt.')
    for key in AMOUNTS:
        line(LABELS[key] + ': ' + _money(calculation[key]))
    if statement['schema_version'] in (2, 3, 4, 5):
        line('Belegte Nettoabzüge: ' + _money(calculation['net_deductions_minor']))
        line('Eigene Entgeltbestandteile', True)
        labels = dict(ordinary_work='Regelmäßiges Arbeitsentgelt',
                      public_holiday='Feiertagsvergütung', sickness='Entgeltfortzahlung',
                      first_sickness_day_regular_wage='Entgelt am ersten Krankheitstag', vacation='Urlaubsentgelt')
        for item in statement['earnings_summary']:
            line(labels.get(item['kind'], 'Belegtes Anspruchsentgelt') + ': '
                 + ', '.join(item['dates']) + ' / ' + _money(item['gross_minor']))
        travel = statement['travel_summary']
        for key, label in (
            ('tax_free_external_minor', 'Steuerfreie Reiseerstattung außerhalb des Lohnnettos'),
            ('flat_taxable_payroll_minor', 'Pauschal versteuerter Reiselohn'),
            ('individual_taxable_payroll_minor', 'Individuell versteuerter Reiselohn'),
            ('benefit_in_kind_non_cash_minor', 'Sachbezug ohne Barauszahlung'),
            ('employee_flat_tax_deduction_minor', 'Belegter Arbeitnehmer-Steuerkostenabzug')):
            line(label + ': ' + _money(travel[key]))
        line('Mahlzeitenmerkmal M: ' + ('Ja' if travel['letter_m'] else 'Nein'))
    if statement['schema_version'] in (3, 4, 5):
        extra = statement['one_off_summary']
        line('Einmalzahlung / sonstiger Bezug', True)
        line('Brutto der Einmalzahlung: ' + _money(extra['amount_minor']))
        line('Berechneter Zuflussstichtag: ' + extra['receipt_date'])
        line(f"Steuerjahr: {extra['tax_year']} / SV-Zuordnungsjahr: {extra['social_year']}")
        line('Märzklausel: ' + ('Ja' if extra['march_clause'] else 'Nein'))
        for key in ('employee_social_total_minor', 'individual_wage_tax_minor', 'solidarity_minor', 'church_tax_minor'):
            line(LABELS[key] + ' der Einmalzahlung: ' + _money(extra[key]))
        for key, value in extra['employee_contributions'].items():
            line(BRANCH_LABELS[key] + ' der Einmalzahlung: ' + _money(value))
    if calculation['employee_contributions'] is not None:
        line('Arbeitnehmerbeiträge', True)
        for key, value in calculation['employee_contributions'].items():
            line(BRANCH_LABELS[key] + ': ' + _money(value))
    summary = statement['period_summary']
    if summary is not None:
        line('Belegte Zeiträume', True)
        for name, title, days in (('employment_intervals', 'Beschäftigung / Kalendertage', 'calendar_days'),
                                  ('tax_periods', 'Steuerzeitraum / Steuertage', 'tax_days'),
                                  ('social_periods', 'Sozialversicherung / SV-Tage', 'days')):
            for item in summary[name]:
                line(f"{title}: {item['start']} bis {item['end']} / {item[days]}")
    line('Berechneter Auszahlungsbetrag ist kein Zahlungsnachweis. '
         + ('Steuerfreie Reiseerstattungen werden außerhalb dieses Lohnnettos gezahlt.' if statement['schema_version'] in (2, 3, 4, 5)
            else 'Auslagen und Reisekosten werden gesondert belegt.'))
    line('Keine amtliche Meldung oder vollständige gesetzliche Entgeltbescheinigung. Nachweis des ausgewiesenen Rechenumfangs.')
    line('Beleg-SHA256: ' + statement['statement_hash'])
    canvas.save()
    return stream.getvalue()


def package(statement):
    content = render_pdf(statement)
    return dict(statement, pdf_sha256=_sha(content), pdf_size=len(content))


class PayrollStatements:
    def __init__(self, office):
        from business_payroll import Payroll
        self.office, self.db = office, office.db
        self.payroll = Payroll(office)

    def _access(self, actor, employee_id=None, *, exporting=False):
        fresh, employee = self.payroll._access(actor, employee_id, own=True)
        can_export = employee['user_id'] == fresh['id'] or 'personnel.export' in permissions(self.office, fresh)
        if exporting and not can_export:
            require_permission(self.office, fresh, 'personnel.export')
        return fresh, employee, can_export

    def _verified(self, row):
        from business_payroll import calculation_matches_source
        record = self.payroll._event(row)
        if record['source'].get('source_schema_version') in (3, 4, 5):
            self.payroll._verify_calculation_record(record)
        elif record['source'].get('source_schema_version') == 2:
            self.payroll._verify_period_record(record)
        elif not calculation_matches_source(record['source'],record['calculation']):
            raise Problem(500, 'Der gespeicherte Lohnnachweis ist nicht reproduzierbar.')
        return project(record)

    def records(self, actor, query=None):
        query = query or {}
        _shape(query, ('employee_id',))
        with transaction(self.office):
            _, employee, _ = self._access(actor, query.get('employee_id'))
            rows = self.db.execute('SELECT e.* FROM business_payroll_events e WHERE e.kind=? AND e.employee_id=? '
                'AND NOT EXISTS (SELECT 1 FROM business_payroll_events n WHERE n.id=e.id AND n.revision>e.revision) '
                'ORDER BY e.created_at,e.id', ('run', employee['id'])).fetchall()
            values = [self._verified(row) for row in rows]
        items = [package(value) for value in values]
        with transaction(self.office):
            _, employee, can_export = self._access(actor, employee['id'])
            return dict(employee_id=employee['id'], can_export=can_export, items=items)

    def get(self, actor, object_id, query=None, *, history=False):
        query = query or {}
        _shape(query, () if history else ('revision',))
        revision = None if history else _revision(query.get('revision'))
        with transaction(self.office):
            row = self.payroll._row(object_id, 'run', revision)
            _, employee, _ = self._access(actor, row['employee_id'])
            rows = self.db.execute('SELECT * FROM business_payroll_events WHERE id=? ORDER BY revision', (object_id,)).fetchall() if history else [row]
            values = [self._verified(value) for value in rows]
        items = [package(value) for value in values]
        with transaction(self.office):
            _, employee, can_export = self._access(actor, employee['id'])
            return dict(employee_id=employee['id'], can_export=can_export,
                        **({'items': items} if history else {'statement': items[0]}))

    def export(self, actor, object_id, query, *, file_format='pdf'):
        _shape(query, ('revision', 'statement_hash'), ('revision', 'statement_hash'))
        revision = _revision(query['revision'])
        if not isinstance(query['statement_hash'], str) or not re.fullmatch(r'[a-f0-9]{64}', query['statement_hash']):
            raise Problem(400, 'Den zuvor geprüften Mitarbeiterbeleg angeben.')
        with transaction(self.office):
            row = self.payroll._row(object_id, 'run', revision)
            _, employee, _ = self._access(actor, row['employee_id'], exporting=True)
            statement = self._verified(row)
        if statement['statement_hash'] != query['statement_hash']:
            raise Problem(409, 'Der gewählte Mitarbeiterbeleg stimmt nicht mit der geprüften Fassung überein.')
        if file_format not in ('pdf', 'json'):
            raise Problem(400, 'PDF oder JSON als Mitarbeiterbelegformat wählen.')
        content = render_pdf(statement) if file_format == 'pdf' else canonical(package(statement)).encode('utf-8')
        with transaction(self.office):
            fresh, _, _ = self._access(actor, employee['id'], exporting=True)
            self.office.audit(fresh, 'payroll.employee_statement.exported', object_id + ':' + str(revision))
        return BinaryAttachment(content, f"lohnnachweis-{statement['month']}-v{revision}.{file_format}"), 'application/pdf' if file_format == 'pdf' else 'application/json; charset=utf-8'


def methods(path):
    if path == ROOT or re.fullmatch(ROOT + '/' + ID + r'(?:/(?:history|pdf|json))?', path):
        return 'GET'
    return None


def dispatch(office, actor, path, method, data):
    if methods(path) is None:
        return None
    if method != 'GET':
        raise Problem(405, 'Mitarbeiterbelege sind ausschließlich lesbar.')
    _shape(data, ('_query',))
    query = data.get('_query', {})
    api = PayrollStatements(office)
    if path == ROOT:
        value = api.records(actor, query)
    else:
        parts = path[len(ROOT) + 1:].split('/')
        if len(parts) == 2 and parts[1] in ('pdf', 'json'):
            value, mime = api.export(actor, parts[0], query, file_format=parts[1])
            return value, 200, mime
        value = api.get(actor, parts[0], query, history=len(parts) == 2)
    return value, 200, 'application/json'
