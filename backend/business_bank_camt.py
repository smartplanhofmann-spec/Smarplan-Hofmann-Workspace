"""Additive CAMT importer using the existing immutable bank identities/journal."""
import base64
import binascii

from core import Problem
from business_operations import transaction
from business_bank_reconciliation import BankReconciliation, MAX_FILE, _shape, _sha, _line
from bank_camt_2026_v1 import parse, CONTRACT

DELIMITER = 'camt.053.001.08'  # Closed format selector; never treated as CSV punctuation.
INSPECT_FIELDS = ('account_id', 'account_revision', 'bank_revision', 'filename', 'content_base64')


def original(data):
    value = data.get('content_base64')
    if not isinstance(value, str) or len(value) > ((MAX_FILE+2)//3)*4:
        raise Problem(400, 'Bankdatei ist zu groß.')
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise Problem(400, 'Gültige Base64-Originaldatei erforderlich.') from None


def verify_projection(metadata, raw):
    parsed = parse(raw)
    if (metadata['contract'] != CONTRACT or metadata['delimiter'] != DELIMITER
            or metadata['bank']['payload']['iban'] != parsed['iban']
            or metadata['file_sha256'] != parsed['proof']['file_sha256']
            or metadata['camt'] != parsed['proof']
            or any(metadata[key] != parsed[key] for key in (
                'statement_reference', 'period_from', 'period_to', 'opening_balance', 'closing_balance', 'rows'))):
        raise Problem(409, 'CAMT-Original, Auszugsangaben und gebundenes Bankkonto stimmen nicht überein.')
    return parsed['rows'], []


class CamtBankReconciliation(BankReconciliation):
    statement_contract = CONTRACT

    def _import_filename(self, filename):
        if '/' in filename or '\\' in filename or not filename.lower().endswith('.xml'):
            raise Problem(400, 'Einfachen XML-Dateinamen angeben.')

    def _import_rows(self, raw, data, start, end, binding):
        if data['delimiter'] != DELIMITER:
            raise Problem(400, 'Ausdrücklich camt.053.001.08 wählen.')
        parsed = parse(raw)
        if (binding['payload']['iban'] != parsed['iban']
                or any(data[key] != parsed[key] for key in (
                    'statement_reference', 'period_from', 'period_to', 'opening_balance', 'closing_balance'))):
            raise Problem(409, 'Geprüfte Angaben müssen mit dem CAMT-Original und der gebundenen IBAN übereinstimmen.')
        return parsed['rows'], []

    def _import_metadata(self, metadata, raw):
        metadata['camt'] = parse(raw)['proof']
        return metadata

    def inspect(self, actor, data):
        _shape(data, INSPECT_FIELDS)
        with transaction(self.office):
            self._access(actor, True)
            # Reuse the complete account/version/coverage/period checks after
            # deriving exact suggestions from the immutable supplied original.
            self._import_filename(_line(data['filename'], 'Dateiname', 200))
            raw = original(data)
            parsed = parse(raw)
            body = dict(data, delimiter=DELIMITER, complete_statement_confirmed=True,
                **{key: parsed[key] for key in ('statement_reference', 'period_from',
                    'period_to', 'opening_balance', 'closing_balance')})
            preview, _ = self._import(actor, body)
            self._access(actor, True)
            return dict(schema_version=1, contract=CONTRACT, original_sha256=_sha(raw),
                suggested_body={key:value for key,value in body.items() if key not in ('content_base64','complete_statement_confirmed')}, camt=parsed['proof'], preview=preview,
                confirmation_required=True, financial_changes=False)
