"""Explicit product jurisdiction routing; no inferred foreign tax rules.

Country support belongs to a domain and currency, never to UI language or the
customer's address. Future rule packages get their own registered contract.
Historical document payloads and calculation hashes are not rewritten here.
"""
from types import MappingProxyType

from core import Problem, canonical, digest


_INVOICE = MappingProxyType(dict(
    schema_version=1, domain='commercial_invoice', country='DE', currency='EUR',
    currency_scale=2, contract='de_commercial_invoice_eur_v1',
    country_label='Deutschland', currency_label='Euro',
))
_PACKAGES = MappingProxyType({('commercial_invoice', 'DE', 'EUR'): _INVOICE})


def resolve(*, domain, country, currency):
    """Exact allowlist; no arbitrary imports, country aliases or EUR fallback."""
    if any(type(value) is not str for value in (domain, country, currency)):
        raise Problem(400, 'Regelbereich, Ausstellerland und Währung ausdrücklich angeben.')
    package = _PACKAGES.get((domain, country, currency))
    if package is None:
        raise Problem(409, 'Eigene Rechnungsstellung unterstützt derzeit Aussteller in Deutschland und EUR. '
            'Für dieses Ausstellerland oder diese Währung ist kein Regelpaket implementiert.')
    result = dict(package)
    return dict(result, package_hash=digest(canonical(result)))


def invoice_scope(country, *, currency='EUR'):
    """Descriptive product boundary, not permission or a tax-case approval."""
    try:
        selected = resolve(domain='commercial_invoice', country=country, currency=currency)
    except Problem:
        selected = None
    return dict(schema_version=1, domain='commercial_invoice',
        issuer_country=country, currency=currency, selected=selected,
        supported=[resolve(domain='commercial_invoice', country='DE', currency='EUR')],
        supported_issuer=selected is not None,
        scope_note='Eigene Rechnungsstellung: Aussteller in Deutschland, Beträge in EUR. '
            'Kundenanschriften bestimmen nicht das Regelwerk des Ausstellers. '
            'Steuerfälle, Ausstellerfreigabe und Belegprüfung werden zusätzlich geprüft.')
