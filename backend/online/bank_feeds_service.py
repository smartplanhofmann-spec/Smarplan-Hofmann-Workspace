"""Online-only bank reads, with fresh authorization on both sides of provider IO.

Configuration is supplied by the operator, not accepted from a browser request.
The existing immutable bank/finance tables are never written here.
"""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import stat

from core import Problem
from business_bank_reconciliation import BankReconciliation
from business_operations import transaction
from business_organization import module_enabled
from business_schema import state
from online.integration_qonto import QontoReader, window, _id


def methods(path):
    return {'/bank-feeds/qonto/status': 'GET', '/bank-feeds/qonto/read': 'POST'}.get(path)


@dataclass(frozen=True)
class Config:
    organization_id: str
    account_id: str
    token: str = field(repr=False)


def environment_config():
    names = ('SMARTPLAN_QONTO_ORGANIZATION_ID', 'SMARTPLAN_QONTO_ACCOUNT_ID', 'SMARTPLAN_QONTO_TOKEN_FILE')
    values = [os.environ.get(name, '') for name in names]
    if not any(values):
        return None
    try:
        organization, account, filename = values
        _id(organization)
        if not re.fullmatch(r'[a-f0-9]{32}', account) or not Path(filename).is_absolute():
            raise ValueError()
        descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
                    info.st_uid not in (0, os.geteuid()) or info.st_size > 8194):
                raise ValueError()
            token = handle.read(8195).decode('ascii').strip()
        if not re.fullmatch(r'[A-Za-z0-9._~+/-]{16,8192}={0,2}', token):
            raise ValueError()
        return Config(organization, account, token)
    except (OSError, ValueError, UnicodeError, Problem):
        raise Problem(409, 'Die serverseitige Qonto-Lesekonfiguration muss geprüft werden.') from None


class BankFeeds:
    def __init__(self, office, *, config=environment_config, reader=None):
        self.office = office
        self.config = config
        self.reader = reader or QontoReader()

    def _access(self, token, config):
        actor = self.office.user(token)
        bank = BankReconciliation(self.office)
        bank._access(actor)
        if state(self.office)['compatibility_mode'] != 'business' or not module_enabled(self.office, 'finance'):
            raise Problem(423, 'Finanzen sind für neue Bankabrufe deaktiviert.')
        if config is None:
            return None
        binding = bank._account(config.account_id)
        if not binding['payload']['active']:
            raise Problem(409, 'Das zugeordnete Bankkonto ist nicht aktiv.')
        # Also checks the current accounting account version; a historical bank
        # binding must not silently follow a changed/deactivated money account.
        accounts = bank.accounts(actor)['available_accounts']
        account = next((a for a in accounts if a['id'] == config.account_id), None)
        if account != binding['payload']['account']:
            raise Problem(409, 'Die Bankkontozuordnung muss mit dem aktuellen Geldkonto geprüft werden.')
        return binding

    def dispatch(self, token, path, method, data):
        expected = methods(path)
        if expected is None:
            raise Problem(404, 'Bankverbindung nicht gefunden.')
        if method != expected:
            raise Problem(405, 'HTTP-Methode nicht erlaubt.')
        required = set() if path.endswith('/status') else {'updated_from', 'updated_to'}
        if not isinstance(data, dict) or set(data) != required:
            raise Problem(400, 'Nur den ausdrücklichen Lesezeitraum angeben; keine Zugangsdaten oder zusätzlichen Filter.')
        with transaction(self.office):
            # Authorize before inspecting even the operator configuration.
            self._access(token, None)
            config = self.config()
            binding = self._access(token, config)
        if path.endswith('/status'):
            return dict(schema_version=1, provider='qonto', configured=config is not None,
                        account_id=config.account_id if config else None,
                        read_only=True, direct_payments=False, complete_statements=False,
                        authentication='operator_oauth_access_token'), 200, 'application/json'
        if config is None:
            raise Problem(409, 'Qonto ist serverseitig noch nicht als Lesezugang eingerichtet.')
        window(data['updated_from'], data['updated_to'])
        result = self.reader.collect(token=config.token, organization_id=config.organization_id,
                                     iban=binding['payload']['iban'], **data)
        with transaction(self.office):
            fresh_config = self.config()
            fresh = self._access(token, fresh_config)
            if fresh_config != config or fresh is None or fresh['content_hash'] != binding['content_hash']:
                raise Problem(409, 'Qonto-Zugang oder Bankkontozuordnung wurde während des Abrufs geändert.')
        return dict(result, local_account_id=config.account_id, bank_binding_hash=binding['content_hash']), 200, 'application/json'
