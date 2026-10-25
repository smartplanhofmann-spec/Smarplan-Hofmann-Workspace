import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';

void main() {
  test('Only exact approved long-running business POSTs use a longer response-header deadline', () {
    final id = 'a' * 32;
    for (final prefix in ['/api/business', '/api/v1/business']) {
      for (final path in [
        '$prefix/documents/$id/finalize',
        '$prefix/documents/$id/email',
        '$prefix/finance/outbox/$id/deliver',
      ]) {
        expect(
          officeRequestHeaderTimeout(path, method: 'POST'),
          const Duration(seconds: 240),
        );
        expect(
          officeRequestHeaderTimeout(path, method: 'GET'),
          const Duration(seconds: 40),
        );
        expect(
          officeRequestHeaderTimeout(path, method: 'PUT'),
          const Duration(seconds: 40),
        );
      }
    }
    for (final path in [
      '/api/business/documents/$id',
      '/api/business/documents/$id/pdf',
      '/api/business/documents/$id/convert',
      '/api/business/documents/$id/finalize?other=true',
      '/api/business/documents/$id/finalize/',
      '/api/business/documents/not-an-id/finalize',
      '/api/business/finance/outbox/$id/reconcile',
      '/api/reports/$id/sign',
      '/api/login',
    ]) {
      expect(
        officeRequestHeaderTimeout(path, method: 'POST'),
        const Duration(seconds: 40),
        reason: path,
      );
    }
  });
}
