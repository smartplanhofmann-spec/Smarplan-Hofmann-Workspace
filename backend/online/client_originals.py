"""Fresh online wrapping keys for private browser originals, never credentials.

The browser persists ciphertext only. A key is reproducible only by this
verified company server and the currently authorized account/resource scope.
This module grants no command, offline, provider or payment authority.
"""
import base64
import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from core import Problem, canonical
from business_foundation import _fresh, require_permission, project_creation_scope
from business_operations import identifier
from business_schema import state


FEATURE = 'client_original_key'


def wrapping_key(office, actor, query, *, master_key, instance, host):
    if not isinstance(query, dict) or set(query) != {'kind', 'subject_id'}:
        raise Problem(400, 'Auftragsart und ursprünglichen Bezug eindeutig angeben.')
    kind, subject = query['kind'], identifier(query['subject_id'], 'Originalbezug')
    if kind not in ('material_return', 'private_car_mileage'):
        raise Problem(400, 'Unbekannte geschützte Auftragsart.')
    with office.lock, office.db:
        fresh = _fresh(office, actor)
        scope = project_creation_scope(office, fresh)
        if (instance is None or scope is None or
                scope['instance_id'] != instance.get('instance_id') or
                instance.get('public_host') != host):
            raise Problem(409, 'Eine bestätigte Unternehmensbindung ist erforderlich.')
        mode = state(office)
        readable = mode['capabilities'] if mode.get('compatibility_mode') == 'business' else mode.get('read_capabilities', [])
        required = 'business_inventory' if kind == 'material_return' else 'business_travel_allowances'
        if required not in readable:
            raise Problem(409, 'Der ursprüngliche Fachbereich ist nicht lesbar freigegeben.')
        if kind == 'material_return':
            require_permission(office, fresh, 'inventory.read', project_id=subject)
        else:
            from business_personnel_workflow import PersonnelWorkflow
            PersonnelWorkflow(office)._employee(fresh, subject, own=True)
        binding = dict(schema_version=1, instance_id=scope['instance_id'],
                       account_id=fresh['id'], host=host, api_version='v1',
                       kind=kind, subject_id=subject)
        # Never use the server's encryption/signing key as the browser key.
        # HKDF separates this protocol, instance, account and resource.
        try:
            secret = base64.urlsafe_b64decode(master_key)
            if len(secret) != 32:
                raise ValueError('Invalid configured master key')
            derived = HKDF(algorithm=hashes.SHA256(), length=32,
                salt=hashlib.sha256(b'smartplan.browser-originals.v1').digest(),
                info=canonical(binding).encode('utf-8')).derive(secret)
        except (ValueError, TypeError):
            raise Problem(503, 'Der geschützte Browserauftrag ist derzeit nicht verfügbar.') from None
        return dict(schema_version=1, binding=binding,
                    wrapping_key=base64.b64encode(derived).decode('ascii'))
