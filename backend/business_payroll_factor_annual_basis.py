"""Private explicit V2 planned annual originals for the bounded factor case."""
from core import Problem
from business_payroll_annual_basis import PayrollAnnualBasis
from payroll_factor_annual_basis_2026 import CONTRACT
import payroll_factor_claims_2026 as factor


class FactorAnnualBasis(PayrollAnnualBasis):
    @staticmethod
    def _operation(kind):
        return 'annual.factor_v2.saved:'+kind

    def sources(self,actor,query):
        from business_payroll_calculation_cases import PayrollCalculationCases
        from business_operations import transaction
        with transaction(self.office):
            result=super().sources(actor,query)
            result['calculation_cases']=[item for item in PayrollCalculationCases(self.office)._all(result['employee_id'],'calculation_case')
                if item['rule_version']==factor.RULE_VERSION and item['source_contract_version']==factor.SOURCE_CONTRACT_VERSION]
            result['annual_source_contract']=dict(CONTRACT)
            return result

    def _planned_calculation(self,employee,candidate,*,fresh):
        if candidate['rule_version']!=factor.RULE_VERSION or candidate['source_contract_version']!=factor.SOURCE_CONTRACT_VERSION:
            raise Problem(409,'Dieser V2-Jahresvertrag benötigt den eigenen ursprünglichen Faktor-/P4-Fall.')
        self._check_current_case(employee,candidate,fresh=fresh)
        return factor.calculate_source(candidate['sources'])

    def _snapshot(self,employee,kind,d,ids,*,fresh=True,current_one_off_id=None):
        if kind not in ('annual_basis','annual_tax_forecast'):
            raise Problem(400,'Der V2-Faktorvertrag umfasst nur Jahresbasis und Jahressteuerprognose.')
        result=super()._snapshot(employee,kind,d,ids,fresh=fresh,current_one_off_id=current_one_off_id)
        return dict(result,annual_source_contract=dict(CONTRACT))
