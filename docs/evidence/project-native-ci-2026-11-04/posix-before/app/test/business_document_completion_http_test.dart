import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'backend_integration_test.dart' show BackendHttp;
import 'import_backend_integration_test.dart' show fixture;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'Actual HTTP preserves adopted Decimal prices and revision-bound measurement quantities in drafts',
    () async {
      final backend = Directory('../backend').absolute;
      final python =
          Platform.environment['SMARTPLAN_TEST_PYTHON'] ??
          '${backend.path}/.venv/bin/python';
      final temporary = await Directory.systemTemp.createTemp(
        'smartplan-document-completion-',
      );
      Process? server;
      StreamIterator<String>? output;
      StreamSubscription<String>? errors;
      OfficeApi? api;
      BusinessSession? session;
      final diagnostics = StringBuffer();
      try {
        final seed = fixture.replaceFirst(
          'app = create_app(',
          '''from business_schema import ensure_schema
ensure_schema(office, activate=True)
app = create_app(''',
        );
        server = await Process.start(python, [
          '-u',
          '-c',
          seed,
          temporary.path,
        ], workingDirectory: backend.path);
        errors = server.stderr
            .transform(utf8.decoder)
            .listen(diagnostics.write);
        output = StreamIterator(
          server.stdout.transform(utf8.decoder).transform(const LineSplitter()),
        );
        expect(
          await output.moveNext().timeout(const Duration(seconds: 30)),
          true,
          reason: '$diagnostics',
        );
        final setup = jsonDecode(output.current) as Map<String, dynamic>;
        await HttpOverrides.runWithHttpOverrides(() async {
          api = OfficeApi(
            baseUrl: 'http://127.0.0.1:${setup['port']}',
            apiVersion: 'v1',
          )..token = setup['token'];
          final project = setup['project_id'];
          session = BusinessSession(api: api!, projectId: project);
          await session!.load();
          expect(
            session!.hasFeature('quote_pricing'),
            true,
            reason: session!.error,
          );
          expect(session!.hasFeature('measurement_transfer'), true);
          expect(session!.hasFeature('billing_contact'), true);
          final buyerSource = businessMap(
            await session!.read('/projects/$project/billing-contact'),
          );
          expect(buyerSource['buyer']['name'], 'Synthetic customer');
          expect(buyerSource['buyer']['postal_code'], '');
          expect(buyerSource['completeness']['ready_for_invoice'], false);

          final article = businessMap(
            await session!.command('article', '/articles', {
              'code': 'SYNTH-01',
              'name': 'Synthetischer Artikel',
              'kind': 'material',
              'unit': 'C62',
              'unit_price_net': '8.00',
              'cost_price_net': '5.00',
              'tax_rate': '19',
              'currency': 'EUR',
              'active': true,
            }),
          );
          final pricing = businessMap(
            await session!.command('preview', '/commercial/pricing/preview', {
              'project_id': project,
              'base_cost_net': '10.00',
              'labor_hours': '2',
              'hourly_cost_net': '20.00',
              'components': [
                {
                  'article_id': article['id'],
                  'article_revision': article['revision'],
                  'quantity': '2',
                },
              ],
              'overhead_percent': '10',
              'overhead_amount': '0',
              'markup_percent': '20',
              'markup_amount': '0',
              'surcharge_percent': '0',
              'surcharge_amount': '0',
              'tax_rate': '19',
              'quantity': '2',
              'unit': 'C62',
              'kind': 'service',
            }),
          );
          expect(pricing['unit_cost_net'], '66.00');
          expect(pricing['unit_price_net'], '79.20');
          final pricedPosition = <String, dynamic>{
            'description': 'Kalkulierte synthetische Montage',
            'quantity': '2',
            'unit': 'C62',
            'kind': 'service',
            'tax_rate': '19',
            'unit_price_net': pricing['unit_price_net'],
            'cost_price_net': pricing['unit_cost_net'],
            'pricing': pricing['inputs'],
            'pricing_hash': pricing['preview_hash'],
            'price_confirmation': true,
          };
          final pricedDraft = businessMap(
            await session!.command('priced-draft', '/documents', {
              'project_id': project,
              'kind': 'offer',
              'title': 'Synthetische Preiskalkulation',
              'issue_date': '2026-10-27',
              'buyer': buyerSource['buyer'],
              'positions': [pricedPosition],
            }),
          );
          expect(pricedDraft['status'], 'draft');
          expect(
            pricedDraft['positions'][0]['pricing_snapshot']['preview_hash'],
            pricing['preview_hash'],
          );
          final calculation = businessMap(
            await session!.command(
              'calculation',
              '/commercial/document-calculation',
              {
                'project_id': project,
                'positions': [pricedPosition],
              },
            ),
          );
          expect(calculation['cost_summary']['complete'], true);
          expect(calculation['cost_summary']['known_cost_net'], '132.00');
          expect(calculation['profit_net'], '26.40');

          final measured = businessMap(
            await session!.command('measurement', '/measurements', {
              'project_id': project,
              'title': 'Synthetische Wand',
              'lines': [
                {
                  'description': 'Wandfläche',
                  'unit': 'm2',
                  'formula': 'length * width',
                  'variables': {
                    'length': {'value': '3.10', 'unit': 'm'},
                    'width': {'value': '2.20', 'unit': 'm'},
                  },
                },
              ],
            }),
          );
          final measurementInputs = <String, dynamic>{
            'measurement_id': measured['id'],
            'measurement_revision': measured['revision'],
            'measurement_hash': measured['content_hash'],
            'lines': [
              {
                'line_index': 0,
                'unit_price_net': '25.50',
                'tax_rate': '19',
                'kind': 'service',
                'description': 'Gemessene Wandfläche',
              },
            ],
          };
          final measurementPreview = businessMap(
            await session!.command(
              'measurement-preview',
              '/commercial/measurement-preview',
              {'project_id': project, ...measurementInputs},
            ),
          );
          expect(measurementPreview['positions'][0]['quantity'], '6.8200');
          expect(measurementPreview['positions'][0]['unit'], 'MTK');
          final measuredDraft = businessMap(
            await session!.command('measured-draft', '/documents', {
              'project_id': project,
              'kind': 'offer',
              'title': 'Synthetische Aufmaßübernahme',
              'issue_date': '2026-10-27',
              'positions': [],
              'measurement_imports': [
                {
                  ...measurementInputs,
                  'preview_hash': measurementPreview['preview_hash'],
                  'quantity_confirmation': true,
                  'price_confirmation': true,
                },
              ],
            }),
          );
          expect(measuredDraft['status'], 'draft');
          expect(measuredDraft['positions'][0]['quantity'], '6.8200');
          expect(
            measuredDraft['positions'][0]['measurement_snapshot']['content_hash'],
            measured['content_hash'],
          );
          expect(measuredDraft['totals']['net'], '173.91');
          final reread = businessMap(
            await session!.read('/documents/${measuredDraft['id']}'),
          );
          expect(reread['positions'], measuredDraft['positions']);
        }, BackendHttp());
      } finally {
        session?.dispose();
        api?.dispose();
        await output?.cancel();
        await errors?.cancel();
        if (server != null) {
          server.kill();
          try {
            await server.exitCode.timeout(const Duration(seconds: 5));
          } on TimeoutException {
            server.kill(ProcessSignal.sigkill);
            await server.exitCode;
          }
        }
        await temporary.delete(recursive: true);
      }
    },
    skip: !Platform.isLinux,
    timeout: const Timeout(Duration(minutes: 2)),
  );
}
