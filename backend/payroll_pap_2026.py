"""Bounded offline implementation of BMF PAP 2026, Anlage 1, 12 Nov 2025.

Only ongoing pay, statutory health/pension/unemployment, no pension income,
age allowance, factor, one-off or foreign income. The calling workflow must
establish these preconditions. Decimal intermediate rounding follows PAP pages
14-15, 20-32 and 38. The full official general reference table is tested.
This is neither the BMF XML original nor an official software certification.
"""
from decimal import Decimal, ROUND_DOWN, ROUND_UP, localcontext
import hashlib
import json
import re

from core import Problem

PAP_VERSION = 'bmf_2026_2025_11_12_standard_v1'
PAP_PROVENANCE = dict(version=PAP_VERSION, official_publication='2025-11-12',
    official_document='PAP 2026 Anlage 1: maschinelle Berechnung',
    publication_url='https://www.bundesfinanzministerium.de/Content/DE/Downloads/Steuern/Steuerarten/Lohnsteuer/Programmablaufplan/2025-11-12-PAP-2026.html',
    reviewed_document_url='https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf',
    reviewed_pages='14-15,20-32,38-39', reference='general_machine_annual_table_page_39_258_values',
    official_xml_downloaded=False, runtime_network=False, official_software_approval=False)
PAP_SHA256 = hashlib.sha256(json.dumps(PAP_PROVENANCE, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
D = Decimal


def _down(value, places=0):
    return value.quantize(D(1).scaleb(-places), rounding=ROUND_DOWN)


def _up(value, places=0):
    return value.quantize(D(1).scaleb(-places), rounding=ROUND_UP)


def _tariff(x, splitting=1):
    # UPTAB26, page 38. X is an integer euro amount, not gross income.
    if x < 12349:
        result = D(0)
    elif x < 17800:
        y = _down((x-D(12348))/10000, 6)
        result = (D('914.51')*y+1400)*y
    elif x < 69879:
        y = _down((x-D(17799))/10000, 6)
        result = (D('173.1')*y+2397)*y+D('1034.87')
    elif x < 277826:
        result = x*D('0.42')-D('11135.63')
    else:
        result = x*D('0.45')-D('19470.38')
    return _down(result)*splitting


def _class_five_six(x):
    # MST5_6 and UP5_6, pages 29-30; each indicated euro truncation matters.
    def comparison(zx):
        difference = (_tariff(_down(zx*D('1.25')))-_tariff(_down(zx*D('0.75'))))*2
        return max(difference, _down(zx*D('0.14')))
    if x > 34939:
        result = comparison(D(34939))
        if x > 222260:
            result = _down(result+D(222260-34939)*D('0.42'))
            return _down(result+(x-222260)*D('0.45'))
        return _down(result+(x-34939)*D('0.42'))
    result = comparison(x)
    if x > 14071:
        result = min(result, _down(comparison(D(14071))+(x-14071)*D('0.42')))
    return result


def calculate_standard_tax(*, gross_minor, period, tax_class, children_half_units,
        additional_health_percent, saxony, childless_surcharge, care_child_discounts,
        church_member, allowance_minor, addition_minor):
    """Return BMF LSTLZZ/SOLZLZZ/BK in cents; annual/monthly period only.

    Church *assessment base* BK is not a computed church tax. All input fields
    must be supplied explicitly; the kernel never fetches employee tax data.
    """
    for value, low, high in ((gross_minor,0,10**12),(period,1,2),(tax_class,1,6),
            (children_half_units,0,20),(care_child_discounts,0,4),
            (allowance_minor,0,10**12),(addition_minor,0,10**12)):
        if type(value) is not int or not low <= value <= high:
            raise Problem(400,'Ungültiger ganzzahliger PAP-Eingabewert.')
    if any(type(value) is not bool for value in (saxony,childless_surcharge,church_member)):
        raise Problem(400,'PAP-Versicherungsmerkmale ausdrücklich bestätigen.')
    if (not isinstance(additional_health_percent,str)
            or not re.fullmatch(r'\d{1,2}(?:\.\d{1,2})?',additional_health_percent)
            or not 0 <= D(additional_health_percent) <= 20):
        raise Problem(400,'PAP-Kassenzusatzbeitrag mit höchstens zwei Nachkommastellen angeben.')
    if (tax_class >= 5 and children_half_units or tax_class == 6 and addition_minor
            or childless_surcharge and care_child_discounts):
        raise Problem(400,'Widersprüchliche PAP-Steuer-/Kindermerkmale.')
    with localcontext() as context:
        context.prec = 50
        multiplier = D(12 if period == 2 else 1)
        annual = _down(D(gross_minor)*multiplier/100,2)  # MRE4JL
        taxable_pay = max(D(0), _down(annual-D(allowance_minor)*multiplier/100+D(addition_minor)*multiplier/100,2))
        pension = _down(min(annual,D(101400))*D('0.093'),2)
        care_rate = D('0.023') if saxony else D('0.018')
        care_rate += D('0.006') if childless_surcharge else -D('0.0025')*care_child_discounts
        health_care = _down(min(annual,D(69750))*(D('0.07')+D(additional_health_percent)/200+care_rate),2)
        precaution = _up(pension+health_care)
        if tax_class != 6:
            unemployment = _down(min(annual,D(101400))*D('0.013'),2)
            precaution = max(precaution,_up(pension+min(D(1900),_down(unemployment+health_care,2))))
        employee_allowance = min(D(1230),_up(taxable_pay)) if tax_class < 6 else D(0)
        fixed = employee_allowance+(D(36) if tax_class < 6 else 0)+(D(4260) if tax_class == 2 else 0)
        splitting = 2 if tax_class == 3 else 1
        child_allowance = D(children_half_units)/2*(D(4878) if tax_class == 4 else D(9756)) if tax_class < 5 else D(0)
        def yearly_tax(deduction):
            income = taxable_pay-fixed-precaution-deduction
            x = D(0) if income < 1 else _down(income/splitting)
            return _tariff(x,splitting) if tax_class < 5 else _class_five_six(x)
        annual_tax = yearly_tax(D(0))
        assessment = yearly_tax(child_allowance) if children_half_units else annual_tax
        solidarity = D(0)
        threshold = D(20350)*splitting
        if assessment > threshold:
            solidarity = min(_down(assessment*D('0.055'),2),_down((assessment-threshold)*D('0.119'),2))
        return dict(LSTLZZ=int(_down(annual_tax*100/multiplier)),
            SOLZLZZ=int(_down(solidarity*100/multiplier)),
            BK=int(_down(assessment*100/multiplier)) if church_member else 0)
