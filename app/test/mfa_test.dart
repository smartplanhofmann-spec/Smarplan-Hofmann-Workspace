import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';
import 'package:smartplan_office/mfa_dialog.dart';

import 'workflow_test.dart' show TestApi;

class MfaApi extends TestApi {
  MfaApi({this.enroll = false});
  final bool enroll;
  bool verified = false;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/login') {
      return {
        'mfa_required': true,
        'challenge': 'test-challenge',
        if (enroll)
          'enrollment': {
            'secret': 'JBSWY3DPEHPK3PXP',
            'uri': 'otpauth://totp/Smartplan:test?secret=JBSWY3DPEHPK3PXP&issuer=Smartplan',
          },
      };
    }
    if (path == '/api/login/verify') {
      if (body?['code'] != '123456')
        throw const ApiException(401, 'Code ungültig');
      verified = true;
      return {
        'token': 'mfa-session',
        if (enroll) 'recovery_codes': ['test-recovery-1', 'test-recovery-2'],
      };
    }
    if (path == '/api/me' && !verified)
      throw StateError('Session used before MFA');
    return super.call(path, body);
  }
}

void main() {
  Future<void> begin(WidgetTester tester, MfaApi api) async {
    tester.view.physicalSize = const Size(1200, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(OfficeApp(api: api));
    await tester.enterText(
      find.byType(TextFormField).at(0),
      'owner@example.test',
    );
    await tester.enterText(
      find.byType(TextFormField).at(1),
      'Owner-password-123',
    );
    await tester.tap(find.text('Anmelden'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(api.token, isNull);
  }

  testWidgets(
    'Wrong MFA code stays in challenge; correct retry opens workspace',
    (tester) async {
      final api = MfaApi();
      await begin(tester, api);
      expect(find.text('Anmeldung bestätigen'), findsOneWidget);
      await tester.enterText(find.byType(TextField).last, 'wrong');
      await tester.tap(find.text('Bestätigen'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.text('Code ungültig'), findsOneWidget);
      expect(api.token, isNull);
      await tester.enterText(find.byType(TextField).last, '123456');
      await tester.tap(find.text('Bestätigen'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      expect(api.token, 'mfa-session');
      expect(find.text('Baustelle'), findsWidgets);
    },
  );

  testWidgets('Enrollment shows QR and requires acknowledging recovery codes', (
    tester,
  ) async {
    final api = MfaApi(enroll: true);
    await begin(tester, api);
    expect(find.text('Authenticator einrichten'), findsOneWidget);
    await tester.enterText(find.byType(TextField).last, '123456');
    await tester.tap(find.text('Bestätigen'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.byType(RecoveryCodesDialog), findsOneWidget);
    expect(api.token, isNull);
    await tester.tap(find.text('Codes sicher aufbewahrt'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(api.token, 'mfa-session');
  });

  testWidgets('Cancel challenge returns to login without a session', (
    tester,
  ) async {
    final api = MfaApi();
    await begin(tester, api);
    await tester.tap(find.text('Abbrechen'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(api.token, isNull);
    expect(find.text('Anmelden'), findsOneWidget);
    expect(find.byType(MfaDialog), findsNothing);
  });
}
