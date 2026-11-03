"""Versioned daily wrapper around the unchanged 2026 standard annual PAP.

This file adds only the ordinary domestic daily/partial-period calculation.
The historical annual/monthly function and its provenance remain untouched.
Amounts supplied to the PAP are integer cents; actual earnings retain their
division remainder in the period proof and are never replaced by the daily pay.
"""
from decimal import Decimal, ROUND_CEILING, localcontext
import hashlib
import json

from core import Problem
from payroll_pap_2026 import calculate_standard_tax, PAP_SHA256, PAP_VERSION

DAILY_PAP_VERSION = 'bmf_2026_standard_daily_wrapper_v1'
DAILY_PAP_RULES = dict(version=DAILY_PAP_VERSION, annual_kernel_version=PAP_VERSION,
    annual_kernel_provenance_sha256=PAP_SHA256, annual_multiplier=360,
    gross_division='TRUNCATE_AT_INTEGER_CENT_INPUT_KEEP_ACTUAL_REMAINDER',
    daily_allowance='MONTHLY_FEATURE_DIVIDE_30_CEILING_TO_FIVE_CENTS',
    tax_distribution='TRUNCATE_DAILY_COMPONENT_THEN_MULTIPLY_ACTUAL_TAX_DAYS',
    sources=[
        'https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf',
        'https://www.gesetze-im-internet.de/estg/__39b.html',
        'https://gewsth.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-39a/inhalt.html',
        'https://ao.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-39b/r-39b-5.html'])
DAILY_PAP_SHA256 = hashlib.sha256(json.dumps(DAILY_PAP_RULES,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _integer(value, low=0, high=10**12):
    if type(value) is not int or not low <= value <= high:
        raise Problem(400,'Gültigen ganzzahligen Perioden-/Centwert angeben.')
    return value


def daily_tax_feature(monthly_minor):
    """R39b.5(3)/R39a.1(7): already rounded monthly feature -> five-cent day."""
    _integer(monthly_minor)
    with localcontext() as context:
        context.prec = 50
        return int((Decimal(monthly_minor)/Decimal(150)).to_integral_value(rounding=ROUND_CEILING))*5


def period_tax_inputs(gross_minor, *, lzz, tax_days, allowance_monthly_minor,
                      addition_monthly_minor):
    _integer(gross_minor)
    _integer(tax_days,1,31)
    _integer(allowance_monthly_minor)
    _integer(addition_monthly_minor)
    if lzz not in (2,4) or type(lzz) is not int:
        raise Problem(400,'Dieser Periodenzweig unterstützt Monat oder belegte einzelne Steuertage.')
    if lzz == 2:
        if tax_days != 30:
            raise Problem(400,'Der vollständige steuerliche Monat hat dreißig Steuertage.')
        return dict(lzz=2,tax_days=30,gross_minor=gross_minor,pap_gross_minor=gross_minor,
            gross_remainder_minor=0,gross_divisor=1,
            allowance_input_minor=allowance_monthly_minor,addition_input_minor=addition_monthly_minor)
    quotient,remainder = divmod(gross_minor,tax_days)
    return dict(lzz=4,tax_days=tax_days,gross_minor=gross_minor,pap_gross_minor=quotient,
        gross_remainder_minor=remainder,gross_divisor=tax_days,
        allowance_input_minor=daily_tax_feature(allowance_monthly_minor),
        addition_input_minor=daily_tax_feature(addition_monthly_minor))


def calculate_daily_tax(*, gross_minor, allowance_minor, addition_minor, **parameters):
    """Exactly one ordinary PAP day; no weekly or exceptional payment branch."""
    for value in (gross_minor,allowance_minor,addition_minor):
        _integer(value,0,10**12//360)
    annual = calculate_standard_tax(gross_minor=gross_minor*360,period=1,
        allowance_minor=allowance_minor*360,addition_minor=addition_minor*360,**parameters)
    return {key:value//360 for key,value in annual.items()}


def calculate_period_tax(*, gross_minor, lzz, tax_days, allowance_monthly_minor,
                         addition_monthly_minor, **parameters):
    inputs = period_tax_inputs(gross_minor,lzz=lzz,tax_days=tax_days,
        allowance_monthly_minor=allowance_monthly_minor,addition_monthly_minor=addition_monthly_minor)
    args = dict(gross_minor=inputs['pap_gross_minor'],allowance_minor=inputs['allowance_input_minor'],
        addition_minor=inputs['addition_input_minor'],**parameters)
    if lzz == 2:
        component = calculate_standard_tax(period=2,**args)
        total = dict(component)
    else:
        component = calculate_daily_tax(**args)
        total = {key:value*tax_days for key,value in component.items()}
    return dict(inputs=inputs,component=component,totals=total,
        version=DAILY_PAP_VERSION,provenance_sha256=DAILY_PAP_SHA256)
