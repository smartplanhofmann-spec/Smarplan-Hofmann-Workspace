"""Bounded PAP 2026 MSONST, STSMIN and MSOLZSTS calculation.

The caller must establish the standard statutory-insurance scope, an actual
annual forecast, annual allowances and the receipt-month-end fund rate. This
pure module neither creates annual facts nor allocates social contributions.
Pension income, factor, age allowance, MBV and compensation inputs are outside
this explicitly bounded entry point; no existing PAP version is modified.
"""
import hashlib
import json
from pathlib import Path

from core import Problem
import payroll_pap_2026 as standard

ONEOFF_PAP_VERSION = 'bmf_2026_2025_11_12_standard_oneoff_v1'
ONEOFF_PAP_PROVENANCE = dict(
    version=ONEOFF_PAP_VERSION,
    source=standard.PAP_PROVENANCE['reviewed_document_url'],
    pages=[3,4,5,33,34,35,36,37,39],
    annual_primitive_version=standard.PAP_VERSION,
    annual_primitive_sha256=hashlib.sha256(Path(standard.__file__).read_bytes()).hexdigest(),
    module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    original_pdf_downloaded=False,official_xml_downloaded=False,
    official_software_approval=False,
    scope=dict(ALV=0,KRV=0,PKV=0,ALTER1=0,F=1,MBV=0,
               JRE4ENT=0,SONSTENT=0,JVBEZ=0,VBS=0))
ONEOFF_PAP_HASH = hashlib.sha256(json.dumps(ONEOFF_PAP_PROVENANCE,sort_keys=True,
    separators=(',',':')).encode()).hexdigest()


def calculate_standard_one_off_tax(*,annual_pay_before_minor,one_off_minor,
        tax_class,children_half_units,additional_health_percent,saxony,
        childless_surcharge,care_child_discounts,church_member,
        annual_allowance_minor,annual_addition_minor):
    """Return STS/SOLZS/BKS cents for one standard 2026 other payment.

    BKS is the church assessment, not church tax. The annual child-adjusted
    assessment is calculated even for non-members, since it governs SOLZS.
    """
    for amount in (annual_pay_before_minor,one_off_minor):
        if type(amount) is not int or not 0<=amount<=10**12:
            raise Problem(400,'Ganzzahliger Jahreslohn und sonstiger Bezug in Cent erforderlich.')
    if type(church_member) is not bool:
        raise Problem(400,'Kirchensteuermerkmal ausdrücklich bestätigen.')
    args=dict(period=1,tax_class=tax_class,children_half_units=children_half_units,
        additional_health_percent=additional_health_percent,saxony=saxony,
        childless_surcharge=childless_surcharge,care_child_discounts=care_child_discounts,
        church_member=True,allowance_minor=annual_allowance_minor,addition_minor=annual_addition_minor)
    before=standard.calculate_standard_tax(gross_minor=annual_pay_before_minor,**args)
    after=standard.calculate_standard_tax(gross_minor=annual_pay_before_minor+one_off_minor,**args)
    tax=max(0,after['LSTLZZ']-before['LSTLZZ'])
    threshold=2035000*(2 if tax_class==3 else 1)
    solidarity=tax*55//1000 if after['BK']>threshold else 0
    return dict(STS=tax,SOLZS=solidarity,BKS=tax if church_member else 0,
        annual_tax_before_minor=before['LSTLZZ'],annual_tax_after_minor=after['LSTLZZ'],
        annual_solidarity_assessment_minor=after['BK'],
        solidarity_threshold_minor=threshold,
        pap_version=ONEOFF_PAP_VERSION,pap_hash=ONEOFF_PAP_HASH)
