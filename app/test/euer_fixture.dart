import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';

import 'project_economics_fixture.dart';

const euerEvent = 'a1234567890123456789012345678901';
Map<String, dynamic> euerSource() => {
  'kind': 'cash',
  'source_hash': 'b' * 64,
  'source_path': '/accounting/events/$euerEvent',
  'undocumented_amount': '0.00',
  'event': {
    'id': euerEvent,
    'cash_date': '2026-11-02',
    'amount': '119.00',
    'direction': 'in',
    'evidence_reference': 'SYNTHETIC-BANK-1',
    'source': {'kind': 'payment'},
    'account': {'id': 'c' * 32, 'code': 'SYNBANK', 'name': 'Synthetische Bank'},
  },
  'units': [
    {
      'unit_id': 'd' * 64,
      'version': 'c1',
      'net': '100.00',
      'tax': '19.00',
      'gross': '119.00',
      'tax_category': 'S',
      'rate': '19',
    },
  ],
};
Map<String, dynamic> euerPayload() => {
  'event_id': euerEvent,
  'source_hash': 'b' * 64,
  'euer_date': '2026-11-02',
  'year_rule': {'kind': 'cash'},
  'lines': [
    {
      'unit_id': 'd' * 64,
      'category': 'sales',
      'business_net': '100.00',
      'deductible_net': '0.00',
      'business_tax': '19.00',
      'deductible_input_tax': '0.00',
      'deductible_tax_cost': '0.00',
      'account': '4400',
      'vat_account': '3806',
    },
  ],
};
Map<String, dynamic> euerCommand() => {
  'operation': 'cash',
  'expected_revision': 0,
  'state_hash': 'a' * 64,
  'payload': euerPayload(),
  'reason': 'Geprüfter synthetischer Erlös',
  'evidence_reference': 'Synthetischer Kontoauszug',
};
Map<String, dynamic> euerProof(Map<String, dynamic> body) => {
  ...ecCopy(body),
  'profile': {
    'id': 'f' * 32,
    'profile': {
      'legal_form': 'sole_proprietorship',
      'accounting_method': 'euer',
      'vat_regime': 'regular',
      'vat_timing': 'cash',
      'vat_effective_from': '2026-01-01',
      'bookkeeping_start': '2026-01-01',
    },
  },
  'rule_version': 'de_euer_regular_cash_2026_v1',
  'target': 'cash:$euerEvent',
  'effect': {
    'operation': 'cash',
    'payload': body['operation'] == 'correct'
        ? body['payload']['payload']
        : body['payload'],
    'source': euerSource(),
    'target': 'cash:$euerEvent',
    'postings': [],
    'details': {'date': '2026-11-02'},
  },
  'reverses': body['operation'] == 'correct'
      ? body['payload']['entry_id']
      : null,
  'postings': [
    {
      'ledger': 'euer',
      'category': 'sales',
      'amount': '100.00',
      'date': '2026-11-02',
      'account': '4400',
      'source_key': 'cash:$euerEvent',
    },
    {
      'ledger': 'euer',
      'category': 'vat_collected',
      'amount': '19.00',
      'date': '2026-11-02',
      'account': '3806',
      'source_key': 'cash:$euerEvent',
    },
    {
      'ledger': 'vat',
      'category': 'output_vat',
      'amount': '19.00',
      'date': '2026-11-02',
      'account': '3806',
      'source_key': 'cash:$euerEvent',
    },
  ],
  'artifact': null,
  'control': null,
  'preview_hash': 'e' * 64,
};

class EuerApi extends EconomicsApi {
  EuerApi() {
    rights.addAll({'accounting.prepare', 'accounting.admin'});
  }
  final euerEntries = <Map<String, dynamic>>[],
      euerResults = <String, Map<String, dynamic>>{};
  ApiException? nextFailure;
  bool lose = false, wrong = false, unreviewed = false, paymentEvidence = false;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    final route = path.split('?').first;
    if (route == '/api/business/capabilities') {
      final caps = Map<String, dynamic>.from(await super.call(path, body));
      (caps['features'] as List).addAll(<String>[
        'accounting_prejournal',
        'accounting_euer',
        'accounting_preparation_profile',
      ]);
      (caps['capabilities'] as List).addAll(<String>[
        'business_accounting',
        'business_accounting_euer',
        'business_accounting_profile',
      ]);
      return caps;
    }
    if (route.startsWith('/api/business/accounting')) {
      calls.add((path: path, body: body == null ? null : ecCopy(body)));
      if (route == '/api/business/accounting/euer')
        return {
          'revision': euerEntries.length,
          'state_hash': 'a' * 64,
          'writes_allowed': enabled,
          'profile_ready': true,
          'official_tax_return': false,
          'account_frame': 'SKR04',
          'periods': [],
        };
      if (route == '/api/business/accounting/euer/sources')
        return {
          'items': [
            if (paymentEvidence)
              {
                'kind': 'receipt',
                'id': economicsReceipt,
                'date': '2026-11-03',
                'source_role': 'payment_evidence',
                'current': null,
                'external_cash': null,
                'asset': null,
                'source': {
                  'kind': 'receipt',
                  'source_hash': 'b' * 64,
                  'source_path': '/finance/receipts/$economicsReceipt',
                  'receipt': {
                    'receipt_id': economicsReceipt,
                    'vendor': 'Synthetic tax office',
                    'invoice_number': 'SYN-TAX',
                    'filename': 'tax.pdf',
                    'net': '9.50',
                    'tax': '0.00',
                    'gross': '9.50',
                  },
                },
                'reasons': ['external_cash_classification_missing'],
              }
            else if (unreviewed)
              {
                'kind': 'receipt_review',
                'id': economicsReceipt,
                'date': '2026-11-02',
                'source_path': '/finance/receipts/$economicsReceipt',
                'reasons': ['original_review_missing'],
              }
            else
              {
                'kind': 'cash',
                'id': euerEvent,
                'date': '2026-11-02',
                'source': euerSource(),
                'current': euerEntries.isEmpty ? null : euerEntries.last,
                'reasons': euerEntries.isEmpty
                    ? ['cash_classification_missing']
                    : [],
              },
          ],
          'issues': [],
          'account_movements': [],
        };
      if (route == '/api/business/accounting/euer/journal')
        return {
          'items': euerEntries.reversed.map(ecCopy).toList(),
          'next_offset': null,
          'total': euerEntries.length,
        };
      if (route == '/api/business/accounting/euer/report')
        return {
          'year': int.parse(Uri.parse(path).queryParameters['year']!),
          'currency': 'EUR',
          'scope': 'recorded_sources',
          'official_tax_return': false,
          'complete_for_recorded_sources': false,
          'totals': {
            'confirmed_income': '119.00',
            'confirmed_expenses': '0.00',
            'confirmed_surplus': '119.00',
            'euer_surplus': null,
            'confirmed_output_vat': '19.00',
            'confirmed_input_vat': '0.00',
            'vat_balance': null,
          },
          'issues': [],
          'periods': [],
          'assets': [],
        };
      if (route == '/api/business/accounting/accounts') return {'items': []};
      if (route == '/api/business/accounting/euer/preview')
        return euerProof(body!);
      if (route == '/api/business/accounting/euer/confirm') {
        if (nextFailure != null) {
          final e = nextFailure!;
          nextFailure = null;
          throw e;
        }
        final result = euerResults.putIfAbsent(body!['request_id'], () {
          final proof = euerProof({
            for (final k in [
              'operation',
              'expected_revision',
              'state_hash',
              'payload',
              'reason',
              'evidence_reference',
            ])
              k: body[k],
          });
          final entry =
              {
                  ...proof,
                  'id': (euerEntries.length + 1)
                      .toRadixString(16)
                      .padLeft(32, '0'),
                  'sequence': body['expected_revision'] + 1,
                  'previous_hash': body['state_hash'],
                  'created_by': 'f' * 32,
                  'created_at': '2026-11-03T11:00:00Z',
                  'entry_hash': 'f' * 64,
                }
                ..remove('expected_revision')
                ..remove('state_hash');
          euerEntries.add(ecCopy(entry));
          return entry;
        });
        if (lose) {
          lose = false;
          throw const ApiException(
            0,
            'Antwort nach tatsächlicher Buchung verloren',
          );
        }
        if (wrong) {
          wrong = false;
          return {...ecCopy(result), 'postings': []};
        }
        return ecCopy(result);
      }
      throw StateError('Unhandled euer route $path');
    }
    return super.call(path, body);
  }
}

Future<BusinessSession> euerSession(EuerApi api) async {
  final session = BusinessSession(
    api: api,
    projects: [
      {'id': economicsProject, 'name': 'Synthetisches Projekt'},
    ],
  );
  await api.call('/api/business/capabilities');
  await session.load();
  if (session.error != null) throw StateError(session.error!);
  return session;
}
