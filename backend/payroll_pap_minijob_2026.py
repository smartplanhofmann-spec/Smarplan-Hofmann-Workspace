"""Individually taxed commercial minijob: narrow full-month PAP 2026 branch.

The actual health insurance remains statutory family insurance. PKV=1 is only
the technical instruction in BMF 14 August 2025, paragraph 16, excluding the
health/care precaution amount because this employment has no employee share.
No historical PAP implementation is changed or made less restrictive.
"""
from decimal import Decimal, localcontext
import hashlib
from pathlib import Path

from core import Problem, canonical
from payroll_pap_2026 import _down, _up, _tariff, _class_five_six

PAP_VERSION = 'bmf_2026_individual_minijob_month_v1'
XML_SHA256 = '63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4'
PAP_PROVENANCE = dict(version=PAP_VERSION, year=2026, xml_sha256=XML_SHA256,
    xml_origin='pinned_public_mirror_not_claimed_direct_bmf_download',
    primary_guidance='https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Lohnsteuer/2025-08-14-vorsorgepau-lohnsteuerabzugsverfahren.html',
    primary_guidance_paragraphs=[4, 10, 11, 16, 17, 20, 21, 22, 25, 28],
    historical_tariff_sha256=hashlib.sha256(Path(__file__).with_name('payroll_pap_2026.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
    actual_health_insurance='statutory_family', technical_pkv=1,
    supported_tax_classes=[1, 5], supported_monthly_gross_minor=[17500, 60300],
    official_software_approval=False, runtime_network=False,
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest())
PAP_SHA256 = hashlib.sha256(canonical(PAP_PROVENANCE).encode()).hexdigest()


def parameters(*, gross_minor, tax_class, pension_exempt):
    if (type(gross_minor) is not int or not 17500 <= gross_minor <= 60300
            or type(tax_class) is not int or tax_class not in (1, 5)
            or type(pension_exempt) is not bool):
        raise Problem(400, 'Individueller Minijob: belegten vollen Monat, Klasse I/V und 175 bis 603 EUR verwenden.')
    return dict(ALV=1, KRV=1 if pension_exempt else 0, PKV=1, PKPV=0,
                PKPVAGZ=0, KVZ='0', PVS=0, PVZ=0, PVA=0, LZZ=2,
                STKL=tax_class, RE4=gross_minor, ZKF=0, LZZFREIB=0,
                LZZHINZU=0, ALTER1=0, af=0, f='1')


def calculate_individual_minijob_tax(*, gross_minor, tax_class, pension_exempt):
    parameters(gross_minor=gross_minor, tax_class=tax_class, pension_exempt=pension_exempt)
    with localcontext() as context:
        context.prec = 50
        annual = _down(Decimal(gross_minor) * 12 / 100, 2)
        # Rz.10/11: the pension precaution amount follows this employment.
        # KRV=0 uses PAP's statutory 9.3%, not the reduced 3.6% cash deduction.
        pension = Decimal(0) if pension_exempt else _down(annual * Decimal('0.093'), 2)
        precaution = _up(pension)
        # PKV=1 with zero PKPV/PKPVAGZ and ALV=1 excludes KV/PV/ALV here.
        fixed = min(Decimal(1230), _up(annual)) + Decimal(36)
        taxable = max(Decimal(0), _down(annual - fixed - precaution))
        annual_tax = _tariff(taxable) if tax_class == 1 else _class_five_six(taxable)
        # The bounded income is always below the 2026 solidarity threshold.
        return dict(LSTLZZ=int(_down(annual_tax * 100 / 12)), SOLZLZZ=0, BK=0)
