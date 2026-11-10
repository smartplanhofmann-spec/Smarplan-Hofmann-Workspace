"""Explicit V15 private case, preserving shared immutable bonus ownership."""
from business_operations import transaction
from business_payroll_oneoff_cases import PayrollOneoffCases
from business_payroll_factor_annual_basis import FactorAnnualBasis
from payroll_factor_oneoff_composition_2026 import RULE_VERSION,SOURCE_CONTRACT_VERSION,calculate_source
import payroll_factor_claims_2026 as factor


class FactorOneoffCases(PayrollOneoffCases):
    rule_version=RULE_VERSION
    source_contract_version=SOURCE_CONTRACT_VERSION
    running_rule=factor.RULE_VERSION
    running_contract=factor.SOURCE_CONTRACT_VERSION

    @staticmethod
    def _plan(snapshot):
        return calculate_source(snapshot['calculation_source'],rule_version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION)

    def sources(self,actor,query):
        from business_personnel_workflow import _shape
        from payroll_de_2026 import month_range
        from business_payroll_oneoff_cases import validate_case_sources
        _shape(query,('employee_id','month'),('employee_id','month'));month_range(query['month'])
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id'])
            result=FactorAnnualBasis(self.office,clock=self.hr.clock).sources(fresh,dict(employee_id=employee['id']))
            result['calculation_cases']=[item for item in result['calculation_cases'] if item['details']['month']==query['month']]
            items=[item for item in self._all(employee['id']) if item['rule_version']==RULE_VERSION and item['details']['month']==query['month']]
            for item in items:validate_case_sources(self.office,item)
            result.update(month=query['month'],one_off_cases=items)
            return result
