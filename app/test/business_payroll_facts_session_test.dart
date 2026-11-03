import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'business_session_test.dart' show BusinessTestApi;

class FactsSessionApi extends BusinessTestApi {
  final employeeId = 'a' * 32;
  bool active = true, authorized = true, sourceAuthorized = true;
  String? sourceEmployee;

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final result = await super.call(path, body);
    if (path.split('?').first == '/api/business/capabilities') {
      return {
        ...businessMap(result),
        'capabilities': ['business_payroll_facts'],
        'features': ['payroll_period_facts', 'organization_modules'],
        'permissions': [
          'personnel.read',
          if (authorized) ...['personnel.write', 'personnel.approve'],
        ],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final name in BusinessSession.organizationSections)
              name: {'visible': true, 'enabled': name != 'personnel' || active},
          },
        },
      };
    }
    if (path.startsWith('/api/business/payroll/facts/sources?')) {
      return {
        'employee_id': sourceEmployee ?? employeeId,
        'employee': {'id': sourceEmployee ?? employeeId, 'revision': 99},
        'can_write': sourceAuthorized,
        'can_approve': sourceAuthorized,
        'writes_enabled': active,
      };
    }
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  for (final kind in ['employment_terms', 'period_case']) {
    test(
      'exact $kind retry survives module pause and later source revisions',
      () async {
        final api = FactsSessionApi();
        final session = BusinessSession(api: api);
        addTearDown(session.dispose);
        addTearDown(api.dispose);
        await session.load();
        final key = 'payroll-facts-${api.employeeId}';
        api.loseAck = true;
        await expectLater(
          session.command(key, '/payroll/facts', {
            'employee_id': api.employeeId,
            'employee_revision': 1,
            'kind': kind,
            'details': {'reason': 'Original synthetic evidence'},
          }),
          throwsA(isA<ApiException>()),
        );
        final original = api.calls.last.body;
        api.active = false;
        await session.repeatPayrollFactsCommand(api.employeeId);
        expect(api.calls.last.body, original);
        expect(session.pending(key), isFalse);
        expect(session.sectionEnabled('personnel'), isFalse);
      },
    );
  }

  test(
    'fresh authority and exact employee identity gate every retry',
    () async {
      final api = FactsSessionApi();
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      final key = 'payroll-facts-${api.employeeId}';
      api.loseAck = true;
      await expectLater(
        session.command(key, '/payroll/facts', {
          'employee_id': api.employeeId,
          'kind': 'period_case',
        }),
        throwsA(isA<ApiException>()),
      );
      int writes() => api.calls.where((call) => call.body != null).length;
      final originalWrites = writes();
      api.authorized = false;
      await expectLater(
        session.repeatPayrollFactsCommand(api.employeeId),
        throwsA(isA<ApiException>().having((e) => e.status, 'rights', 403)),
      );
      api.authorized = true;
      api.sourceAuthorized = false;
      await expectLater(
        session.repeatPayrollFactsCommand(api.employeeId),
        throwsA(
          isA<ApiException>().having((e) => e.status, 'source rights', 403),
        ),
      );
      api.sourceAuthorized = true;
      api.sourceEmployee = 'b' * 32;
      await expectLater(
        session.repeatPayrollFactsCommand(api.employeeId),
        throwsA(
          isA<ApiException>().having((e) => e.status, 'source identity', 502),
        ),
      );
      expect(writes(), originalWrites);
      expect(session.pending(key), isTrue);
      api.sourceEmployee = null;
      await session.repeatPayrollFactsCommand(api.employeeId);
      expect(writes(), originalWrites + 1);
      expect(session.pending(key), isFalse);
    },
  );
}
