import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('product_inventory', Path(__file__).with_name('product-inventory.py'))
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class ProductInventoryTests(unittest.TestCase):
    def test_current_locks_include_native_record_and_remain_reproducible(self):
        value = module.inventory()
        self.assertEqual(value, module.inventory())
        packages = {row['purl']: row for row in value['components']}
        self.assertIn('pkg:pub/record@7.1.2', packages)
        self.assertIn('pkg:pypi/cryptography@50.0.0', packages)
        self.assertIn('pkg:npm/playwright@1.62.1', packages)
        self.assertEqual(len(packages['pkg:pub/record@7.1.2']['hashes'][0]['content']), 64)
        self.assertNotIn('pkg:pub/flutter@0.0.0', packages)
        self.assertEqual(value['metadata']['properties'][2]['value'], 'not_performed_by_this_script')

    def test_unpinned_python_and_non_registry_dart_never_claim_complete_inventory(self):
        for line in ('Flask>=3', 'https://example.invalid/code.whl', '-e .', 'package==*'):
            with self.assertRaises(ValueError): module.python_packages(line)
        with self.assertRaises(ValueError):
            module.dart_packages('packages:\n  local_code:\n    source: path\n    version: "1.0.0"\n')


if __name__ == '__main__': unittest.main()
