"""Explicit continuation of evidenced unchanged linear movable assets.

The software cutover is not a new purchase or depreciation start. Historical
amounts must match the expressly selected documented rounding convention.
Unmodelled prior changes are rejected instead of being converted to new costs.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata

from core import Problem
from business_operations import iso_date
from business_accounting_openings import cents, money, shape, line

RULE_VERSION='de_historical_linear_assets_v1'
ROUNDING=('cumulative_months_half_up','annual_half_up','monthly_half_up')
FIELDS={'inventory_number','description','asset_kind','business_use','method','rounding',
        'acquired_on','use_start','life_months','acquisition_gross','deductible_input_tax',
        'cost_basis','depreciation_before_start_year','depreciation_in_start_year',
        'opening_book_value','account','unchanged_linear_history_confirmed'}


def asset_key(value):
    line(value,'Inventarnummer',100)
    normalized=unicodedata.normalize('NFKC',value).strip().casefold()
    if not normalized or any(ord(c)<32 or ord(c)==127 for c in normalized):
        raise Problem(400,'Eindeutige betriebliche Inventarnummer erforderlich.')
    if len(normalized)>100:
        raise Problem(400,'Die Inventarnummer darf auch nach Unicode-Zuordnung höchstens 100 Zeichen enthalten.')
    return normalized


def _positive(value,allow_zero=False):
    result=cents(value)
    if result<0 or not allow_zero and result==0:
        raise Problem(400,'Nichtnegative belegte Anlagenwerte und positive Kostenbasis erforderlich.')
    return result


def _rounded(numerator,denominator):
    return int((Decimal(numerator)/Decimal(denominator)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def original_schedule(asset):
    """Full original schedule, independent of the software cutover date."""
    start=date.fromisoformat(asset['use_start']);life=asset['life_months'];basis=cents(asset['cost_basis'])
    final_month=start.year*12+start.month-1+life-1;final_year=final_month//12
    result=[];used=0
    for year in range(start.year,final_year+1):
        before=min(life,max(0,(year-start.year)*12+1-start.month))
        after=min(life,max(0,(year-start.year)*12+13-start.month))
        if asset['rounding']=='cumulative_months_half_up':
            amount=_rounded(basis*after,life)-_rounded(basis*before,life)
        elif asset['rounding']=='annual_half_up':
            amount=_rounded(basis*(after-before),life)
        else:
            amount=_rounded(basis,life)*(after-before)
        # The documented final residual does not create additional cost basis.
        amount=basis-used if year==final_year else min(amount,basis-used)
        result.append(dict(year=year,months=after-before,amount=money(amount),
                           opening_book_value=money(basis-used),closing_book_value=money(basis-used-amount)))
        used+=amount
    return result


def normalize_asset(value,opening_date):
    shape(value,FIELDS);iso_date(opening_date);opening=date.fromisoformat(opening_date)
    asset_key(value['inventory_number']);line(value['description'],'Anlagenbeschreibung',300)
    if (value['asset_kind']!='movable' or value['business_use']!='exclusive_business'
            or value['method']!='linear' or value['rounding'] not in ROUNDING
            or value['unchanged_linear_history_confirmed'] is not True):
        raise Problem(400,'Nur belegte unveränderte lineare bewegliche, vollständig betriebliche Altanlagen sind in diesem Vertrag unterstützt.')
    acquired=iso_date(value['acquired_on']);started=iso_date(value['use_start'])
    if not '1900-01-01'<=acquired<=started<opening_date or opening.year>2200:
        raise Problem(400,'Ursprüngliche Anschaffung und Nutzung müssen vor dem bestätigten Übernahmestichtag liegen.')
    if acquired[:7]!=started[:7]:
        raise Problem(409,'Ein abweichender Anschaffungs-/AfA-Beginn benötigt eine eigene belegte Prüfung; diese lineare Fallklasse beginnt im Anschaffungsmonat.')
    life=value['life_months']
    if type(life) is not int or not 12<=life<=1200 or life%12:
        raise Problem(400,'Belegte ursprüngliche Nutzungsdauer von 1 bis 100 ganzen Jahren erforderlich.')
    if not isinstance(value['account'],str) or not re.fullmatch(r'[0-9]{4}',value['account']):
        raise Problem(400,'Ausdrücklich geprüfte vierstellige SKR04-Anlagenzuordnung erforderlich.')
    gross=_positive(value['acquisition_gross']);tax=_positive(value['deductible_input_tax'],True)
    basis=_positive(value['cost_basis']);past=_positive(value['depreciation_before_start_year'],True)
    current=_positive(value['depreciation_in_start_year'],True);book=_positive(value['opening_book_value'],True)
    if tax>gross or basis!=gross-tax or past+current+book!=basis:
        raise Problem(400,'Kosten ohne abziehbare Vorsteuer, belegte bisherige AfA und Restbuchwert müssen centgenau zusammenpassen.')
    schedule=original_schedule(value)
    expected_past=sum(cents(row['amount']) for row in schedule if row['year']<opening.year)
    quota=next((cents(row['amount']) for row in schedule if row['year']==opening.year),0)
    if past!=expected_past:
        raise Problem(409,'Belegte Vorjahres-AfA passt nicht zum ausdrücklich gewählten unveränderten linearen Altverfahren; keine automatische Nachholung oder Neubewertung.')
    if current>quota or opening.month==1 and opening.day==1 and current:
        raise Problem(409,'Bereits im Startjahr verbuchte AfA überschreitet den belegten Jahresrahmen oder liegt vor dessen Beginn.')
    return dict(value)


def continuation(asset,opening_date,year):
    if type(year) is not int or not int(opening_date[:4])<=year<=2200:
        raise Problem(400,'Abschreibungsjahr ab dem belegten Übernahmejahr erforderlich.')
    normalize_asset(asset,opening_date)
    start_year=int(opening_date[:4]);remaining=cents(asset['opening_book_value']);result=[]
    for row in original_schedule(asset):
        if row['year']<start_year:continue
        imported=cents(asset['depreciation_in_start_year']) if row['year']==start_year else 0
        amount=cents(row['amount'])-imported
        if amount<0 or amount>remaining:
            raise Problem(409,'Die belegte lineare Fortschreibung überschreitet den übernommenen Restbuchwert.')
        result.append(dict(year=row['year'],months=row['months'],original_annual_depreciation=row['amount'],
                           imported_current_year_depreciation=money(imported),amount=money(amount),
                           opening_book_value=money(remaining),closing_book_value=money(remaining-amount)))
        remaining-=amount
    selected=next((row for row in result if row['year']==year),None)
    if selected is None:
        selected=dict(year=year,months=0,original_annual_depreciation='0.00',imported_current_year_depreciation='0.00',
                      amount='0.00',opening_book_value='0.00',closing_book_value='0.00')
    return dict(selected,rule_version=RULE_VERSION,prior_required_years=[row['year'] for row in result if row['year']<year and cents(row['amount'])>0])
