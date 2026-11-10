"""Additive PAP 2026 class-IV-factor tax on one other payment.

Pure bounded component, not a payroll dispatcher or source authority. The
caller must establish actual annual forecasts, receipt-month rates, ELStAM,
standard statutory insurance, no age/pension/compensation and no allowances.
Existing standard, factor, one-off and contribution kernels are untouched.
"""
import hashlib
import json
from pathlib import Path
import re

from core import Problem
import payroll_pap_2026 as standard

FACTOR_ONEOFF_PAP_VERSION='bmf_2026_2025_11_12_factor_oneoff_v1'
FACTOR_ONEOFF_PAP_PROVENANCE=dict(version=FACTOR_ONEOFF_PAP_VERSION,
    annual_primitive_version=standard.PAP_VERSION,
    annual_primitive_sha256=hashlib.sha256(Path(standard.__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    module_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
    reviewed_xml_sha256='63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4',
    official_xml_url='https://www.bmf-steuerrechner.de/javax.faces.resource/daten/xmls/Lohnsteuer2026.xml.xhtml',
    reviewed_mirror_url='https://raw.githubusercontent.com/manuelbusch/paprun/cdf564daec7f617d54181eb8b14232e48a59dd7a/tests/data/Lohnsteuer2026.xml',
    statute='https://www.gesetze-im-internet.de/estg/__39b.html',
    methods=['MOSONST','MSONST','STSMIN','MSOLZSTS'],
    scope=dict(STKL=4,af=1,KRV=0,PKV=0,ALV=0,ALTER1=0,MBV=0,JRE4ENT=0,SONSTENT=0,JVBEZ=0,VBS=0,JFREIB=0,JHINZU=0),
    factor_format='EXPLICIT_ASCII_THREE_DECIMALS_ZERO_INCLUSIVE_ONE_EXCLUSIVE',
    rounding='FACTOR_ON_UNSCALED_ANNUAL_TAX_DIFFERENCE_THEN_WHOLE_EURO;SEPARATE_FACTORED_CHILD_ASSESSMENT_FOR_SOLZS',
    direct_official_xml_download=False,official_software_approval=False,runtime_network=False)
FACTOR_ONEOFF_PAP_HASH=hashlib.sha256(json.dumps(FACTOR_ONEOFF_PAP_PROVENANCE,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def calculate_factor_one_off_tax(*,annual_pay_before_minor,one_off_minor,
        tax_class,factor,children_half_units,additional_health_percent,saxony,
        childless_surcharge,care_child_discounts,church_member,
        annual_allowance_minor,annual_addition_minor):
    """Exact STS/SOLZS/BKS cents, without deriving or guessing a household factor.

    Factor applies to the unscaled annual tax difference, before whole-euro
    truncation. Subtracting two separately factored annual taxes is incorrect.
    BKS is the church assessment, not the state-specific church tax amount.
    """
    if (type(tax_class) is not int or tax_class!=4 or not isinstance(factor,str)
            or not re.fullmatch(r'0\.[0-9]{3}',factor)):
        raise Problem(400,'Belegten Faktor mit genau drei Nachkommastellen für Steuerklasse IV angeben.')
    for value in (annual_pay_before_minor,one_off_minor):
        if type(value) is not int or not 0<=value<=10**12:
            raise Problem(400,'Ganzzahligen Jahreslohn und sonstigen Bezug innerhalb der belegten Centgrenze angeben.')
    if annual_pay_before_minor+one_off_minor>10**12:
        raise Problem(400,'Die unterstützte Jahreslohngrenze einschließlich Einmalzahlung ist überschritten.')
    if any(type(value) is not int or value!=0 for value in (annual_allowance_minor,annual_addition_minor)):
        raise Problem(400,'Der begrenzte Faktor-Einmalbezug unterstützt keine zusätzlichen Jahresfrei- oder Hinzurechnungsbeträge.')
    if type(church_member) is not bool:
        raise Problem(400,'Kirchensteuermerkmal ausdrücklich angeben.')
    args=dict(period=1,tax_class=4,children_half_units=children_half_units,
        additional_health_percent=additional_health_percent,saxony=saxony,
        childless_surcharge=childless_surcharge,care_child_discounts=care_child_discounts,
        church_member=True,allowance_minor=0,addition_minor=0)
    before=standard.calculate_standard_tax(gross_minor=annual_pay_before_minor,**args)
    after=standard.calculate_standard_tax(gross_minor=annual_pay_before_minor+one_off_minor,**args)
    thousandths=int(factor[2:])
    delta=after['LSTLZZ']-before['LSTLZZ']
    sts=max(0,delta)*thousandths//100000*100
    assessment=after['BK']*thousandths//100000*100
    threshold=2035000
    solzs=sts*55//1000 if assessment>threshold else 0
    return dict(STS=sts,SOLZS=solzs,BKS=sts if church_member else 0,
        annual_tax_before_minor=before['LSTLZZ'],annual_tax_after_minor=after['LSTLZZ'],
        unscaled_tax_difference_minor=delta,
        annual_solidarity_assessment_minor=assessment,solidarity_threshold_minor=threshold,
        pap_version=FACTOR_ONEOFF_PAP_VERSION,pap_hash=FACTOR_ONEOFF_PAP_HASH)
