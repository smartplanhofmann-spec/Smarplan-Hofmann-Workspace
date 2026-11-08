"""Additive PAP 2026 factor kernel for ordinary class-IV annual/monthly pay.

The caller must establish the existing standard statutory-insurance scope and
the effective, actually supplied ELStAM factor. This function neither derives
a household factor nor admits one-off pay, daily periods, pension/age cases or
additional allowances. Historical standard/one-off/daily kernels are unchanged.
It is a pure tax component, not an independently approved payroll workflow.
"""
import hashlib
import json
from pathlib import Path
import re

from core import Problem
import payroll_pap_2026 as standard


FACTOR_PAP_VERSION = 'bmf_2026_2025_11_12_standard_factor_v1'
FACTOR_PAP_PROVENANCE = dict(
    version=FACTOR_PAP_VERSION,
    annual_primitive_version=standard.PAP_VERSION,
    annual_primitive_sha256=hashlib.sha256(Path(standard.__file__).read_bytes()).hexdigest(),
    module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    official_xml_url='https://www.bmf-steuerrechner.de/javax.faces.resource/daten/xmls/Lohnsteuer2026.xml.xhtml',
    reviewed_mirror_url=('https://raw.githubusercontent.com/manuelbusch/paprun/'
        'cdf564daec7f617d54181eb8b14232e48a59dd7a/tests/data/Lohnsteuer2026.xml'),
    reviewed_xml_sha256='63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4',
    reviewed_pdf_url=standard.PAP_PROVENANCE['reviewed_document_url'],
    methods=['MRE4JL', 'MBERECH', 'UPLSTLZZ', 'MSOLZ', 'UPANTEIL'],
    statute_url='https://www.gesetze-im-internet.de/estg/__39f.html',
    direct_official_xml_download=False, runtime_network=False,
    official_software_approval=False,
    scope=dict(STKL=4, af=1, LZZ=[1, 2], KRV=0, PKV=0, ALTER1=0,
               LZZFREIB=0, LZZHINZU=0, SONSTB=0, VBEZ=0),
    factor_format='EXPLICIT_ASCII_THREE_DECIMALS_ZERO_INCLUSIVE_ONE_EXCLUSIVE',
    rounding='TRUNCATE_FACTORED_ANNUAL_TAX_AND_CHILD_ASSESSMENT_TO_EURO_BEFORE_PERIOD',
)
FACTOR_PAP_SHA256 = hashlib.sha256(json.dumps(FACTOR_PAP_PROVENANCE,
    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def calculate_standard_factor_tax(*, gross_minor, period, tax_class, factor,
        children_half_units, additional_health_percent, saxony,
        childless_surcharge, care_child_discounts, church_member,
        allowance_minor, addition_minor):
    """Return LSTLZZ/SOLZLZZ/BK cents for an explicitly supplied class-IV factor.

    BK is the church assessment base. The factor applies before annual-euro
    truncation and period allocation, and before the solidarity threshold and
    mitigation calculation. A prior monthly tax must never be scaled instead.
    """
    if (not isinstance(factor, str) or not re.fullmatch(r'0\.[0-9]{3}', factor)
            or type(tax_class) is not int or tax_class != 4):
        raise Problem(400, 'Eingetragenen Faktor mit genau drei Nachkommastellen und Steuerklasse IV ausdrücklich angeben.')
    if any(type(value) is not int or value != 0 for value in (allowance_minor, addition_minor)):
        raise Problem(400, 'Der begrenzte Faktorfall unterstützt keine zusätzlichen Frei- oder Hinzurechnungsbeträge.')
    if type(period) is not int or period not in (1, 2):
        raise Problem(400, 'Der Faktorfall unterstützt nur Jahres- oder Monatsberechnung.')
    multiplier = 12 if period == 2 else 1
    if type(gross_minor) is not int or not 0 <= gross_minor <= 10**12 // multiplier:
        raise Problem(400, 'Ganzzahligen Centlohn innerhalb der unterstützten Jahresgrenze angeben.')
    if type(church_member) is not bool:
        raise Problem(400, 'Kirchensteuermerkmal ausdrücklich bestätigen.')
    annual = standard.calculate_standard_tax(gross_minor=gross_minor * multiplier,
        period=1, tax_class=4, children_half_units=children_half_units,
        additional_health_percent=additional_health_percent, saxony=saxony,
        childless_surcharge=childless_surcharge, care_child_discounts=care_child_discounts,
        church_member=True, allowance_minor=0, addition_minor=0)
    # MBERECH: both ST*f results are truncated to whole euros, independently.
    thousandths = int(factor[2:])
    annual_tax = (annual['LSTLZZ'] // 100 * thousandths // 1000) * 100
    assessment = (annual['BK'] // 100 * thousandths // 1000) * 100
    solidarity = 0
    if assessment > 2035000:
        # MSOLZ: full 5.5% versus 11.9% mitigation; each annual cent truncated.
        solidarity = min(assessment * 55 // 1000, (assessment - 2035000) * 119 // 1000)
    return dict(LSTLZZ=annual_tax // multiplier, SOLZLZZ=solidarity // multiplier,
                BK=assessment // multiplier if church_member else 0)
