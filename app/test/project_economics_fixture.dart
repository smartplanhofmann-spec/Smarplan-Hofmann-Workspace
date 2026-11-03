import 'dart:convert';

import 'package:smartplan_office/api.dart';

const economicsProject = 'a1111111111111111111111111111111';
const economicsReceipt = 'b2222222222222222222222222222222';
Map<String, dynamic> ecCopy(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
Map<String, dynamic> economicsSource() => {
  'id': economicsReceipt,
  'project_id': economicsProject,
  'filename': 'Leistung.pdf',
  'media_type': 'application/pdf',
  'sha256': 'a' * 64,
  'status': 'reviewed',
  'revision': 1,
  'vendor': 'Synthetischer Service',
  'invoice_number': 'SYN-42',
  'issue_date': '2026-11-03',
  'net': '100.00',
  'tax': '19.00',
  'gross': '119.00',
  'currency': 'EUR',
  'note': '',
  'classification_revision': 0,
  'classification_status': 'unclassified',
  'latest_entry': null,
};
Map<String, dynamic> economicsProof() => {
  'receipt_id': economicsReceipt,
  'filename': 'Leistung.pdf',
  'vendor': 'Synthetischer Service',
  'invoice_number': 'SYN-42',
  'issue_date': '2026-11-03',
  'net': '100.00',
  'tax': '19.00',
  'gross': '119.00',
  'currency': 'EUR',
  'original_sha256': 'a' * 64,
  'review_sha256': 'b' * 64,
  'source_hash': 'c' * 64,
  'review_revision': 1,
  'review_status': 'reviewed',
  'source_path': '/finance/receipts/$economicsReceipt',
};
Map<String, dynamic> economicsBody() => {
  'project_id': economicsProject,
  'receipt_id': economicsReceipt,
  'source_revision': 1,
  'expected_revision': 0,
  'allocations': [
    {'category': 'external_service', 'amount_net': '100.00'},
  ],
  'reason': 'Geprüfte Fremdleistung',
  'preview_hash': 'd' * 64,
};
Map<String, dynamic> economicsEntry(Map<String, dynamic> body) => {
  'id': 'e' * 32,
  'project_id': body['project_id'],
  'receipt_id': body['receipt_id'],
  'revision': (body['expected_revision'] as int) + 1,
  'source_revision': body['source_revision'],
  'source': economicsProof(),
  'allocations': body['allocations'],
  'reason': body['reason'],
  'created_by': 'f' * 32,
  'created_at': '2026-11-03T10:00:00Z',
  'entry_hash': 'e' * 64,
};
Map<String, dynamic> economicsSummary() => {
  'project_id': economicsProject,
  'currency': 'EUR',
  'valuation_basis': 'document_net',
  'tax_result_available': false,
  'budget': {
    'revision': 1,
    'base_net': '300.00',
    'approved_changes_net': '10.00',
    'total_net': '310.00',
    'remaining_net': null,
  },
  'costs': {
    'material_net': '25.00',
    'labor_net': '17.50',
    'external_service_net': '0.00',
    'machine_net': '0.00',
    'other_net': '0.00',
    'total_net': '42.50',
  },
  'revenue': {
    'invoiced_net': '100.00',
    'credited_net': '0.00',
    'revenue_net': '100.00',
    'invoiced_gross': '119.00',
    'credited_gross': '0.00',
  },
  'payments': {
    'receipts_gross': '10.00',
    'refunds_gross': '0.00',
    'net_inflow_gross': '10.00',
    'open_gross': '109.00',
    'supplier_outflows_gross': null,
    'cash_balance_gross': null,
    'complete': false,
  },
  'result': {
    'document_net_contribution': null,
    'complete_for_recorded_sources': false,
    'scope': 'recorded_sources_only',
  },
  'issues': [
    {
      'code': 'receipt_unclassified',
      'message': 'Kosteneinordnung für den Eingangsbeleg fehlt.',
      'source_id': economicsReceipt,
    },
  ],
  'sources': {
    'material_movements': [],
    'approved_times': [],
    'receipt_allocations': [],
    'documents': [],
    'payment_allocations': [],
    'supplier_payments': [],
  },
};

class EconomicsApi extends OfficeApi {
  EconomicsApi() : super(apiVersion: 'v1') {
    token = 'synthetic-economics';
  }
  Set<String> rights = {
    'finance.read',
    'finance.write',
    'finance.approve',
    'accounting.read',
  };
  bool enabled = true,
      readonly = false,
      loseConfirm = false,
      wrongConfirm = false,
      denyConfirm = false;
  int generation = 1;
  final calls = <({String path, Map<String, dynamic>? body})>[];
  final entries = <Map<String, dynamic>>[];
  final results = <String, Map<String, dynamic>>{};
  Map<String, dynamic> source = economicsSource();
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : ecCopy(body)));
    final route = path.split('?').first;
    if (route == '/api/business/capabilities')
      return {
        'compatibility_mode': readonly ? 'legacy' : 'business',
        'readonly': readonly,
        'generation': generation,
        'capabilities': [
          'business_foundation',
          'business_finance',
          'business_operations',
          'business_project_economics',
          'business_inventory',
        ],
        'permissions': rights.toList(),
        'features': ['project_economics', 'organization_modules'],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final k in [
              'finance',
              'material',
              'documents',
              'planning',
              'personnel',
            ])
              k: {'visible': true, 'enabled': k == 'finance' ? enabled : true},
          },
        },
      };
    if (route == '/api/business/project-economics') return economicsSummary();
    if (route == '/api/business/project-economics/sources')
      return {
        'items': [ecCopy(source)],
      };
    if (route == '/api/business/project-economics/receipts/$economicsReceipt') {
      if (!rights.contains('finance.read'))
        throw const ApiException(403, 'Belegrechte entzogen');
      return {'items': entries.map(ecCopy).toList()};
    }
    if (route == '/api/business/project-economics/preview') {
      return {
        ...ecCopy(body!),
        'source': economicsProof(),
        'previous_entry_id': null,
        'preview_hash': 'd' * 64,
      };
    }
    if (route == '/api/business/project-economics/confirm') {
      if (denyConfirm)
        throw const ApiException(403, 'Einordnung nicht freigegeben');
      final result = results.putIfAbsent(body!['request_id'], () {
        final entry = economicsEntry(body);
        entries.add(ecCopy(entry));
        return entry;
      });
      if (loseConfirm) {
        loseConfirm = false;
        throw const ApiException(0, 'Antwort nach Speicherung verloren');
      }
      if (wrongConfirm) {
        wrongConfirm = false;
        return {...ecCopy(result), 'receipt_id': '9' * 32};
      }
      return ecCopy(result);
    }
    if (route == '/api/business/finance/receipts')
      return {
        'items': [ecCopy(source)],
      };
    if (route == '/api/business/finance/receipts/$economicsReceipt')
      return ecCopy(source);
    throw StateError('Unhandled fixture $path');
  }
}
