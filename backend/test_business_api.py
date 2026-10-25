"""Business router contracts, additive to the unchanged Gmail endpoints."""
import types
import unittest
from unittest.mock import patch
from core import Problem


class BusinessRouterTests(unittest.TestCase):
    def test_method_inventory_never_turns_arbitrary_business_paths_into_crud(self):
        import business_api
        self.assertIsNone(business_api.methods('/projects'))
        self.assertIsNone(business_api.methods('/business/not-a-module'))
        self.assertEqual(business_api.methods('/business/capabilities'), 'GET')

    def test_dispatch_does_not_swallow_an_internal_provider_import_failure(self):
        import business_api
        with patch.object(business_api.importlib, 'import_module', side_effect=ModuleNotFoundError("broken dependency", name='secret_missing_dependency')):
            with self.assertRaises(ModuleNotFoundError):
                business_api.methods('/business/documents')

    def test_internal_module_receives_relative_path_and_method_without_outer_transaction(self):
        import business_api
        calls=[]
        module=types.SimpleNamespace(
            __name__='business_sample', methods=lambda p:'GET' if p=='/sample' else None,
            dispatch=lambda *args: (calls.append(args) or ({'items':[]},200,'application/json')))
        with patch.object(business_api, '_modules', return_value=[module]), patch('business_schema.state', return_value={'capabilities':['business_sample']}):
            self.assertEqual(business_api.methods('/business/sample'),'GET')
            result=business_api.dispatch(object(),{'id':'owner'},'/business/sample','GET',{'_query':{'project_id':'x'}})
        self.assertEqual(result,({'items':[]},200,'application/json'))
        self.assertEqual(calls[0][2:],('/sample','GET',{'_query':{'project_id':'x'}}))

    def test_module_method_sets_are_normalized_for_both_http_servers(self):
        import business_api
        module=types.SimpleNamespace(methods=lambda p:{'POST','GET'} if p=='/documents' else None)
        with patch.object(business_api, '_modules', return_value=[module]):
            self.assertEqual(business_api.methods('/business/documents'), 'GET, POST')

    def test_query_parser_rejects_duplicate_and_excessive_filters(self):
        import business_api
        self.assertEqual(business_api.query_data([('project_id','abc')]),{'_query':{'project_id':'abc'}})
        for values in [[('x','a'),('x','b')], [('x','a'*5000)]]:
            with self.assertRaises(Problem):business_api.query_data(values)

    def test_offline_scope_is_explicit_and_cannot_be_used_for_finance_or_privacy(self):
        import business_api
        self.assertTrue(business_api.offline_path('/business/time/events','POST'))
        self.assertTrue(business_api.offline_path('/business/capabilities','GET'))
        for path,method in [('/business/time/entries','GET'),('/business/documents','GET'),('/business/payments','POST'),('/business/contacts/a/erase','POST'),('/business/time/events','GET')]:
            self.assertFalse(business_api.offline_path(path,method))

if __name__=='__main__':unittest.main()
