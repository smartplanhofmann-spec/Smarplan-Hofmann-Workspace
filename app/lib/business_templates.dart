import 'package:flutter/material.dart';

import 'business_session.dart';
import 'business_widgets.dart';
import 'business_documents.dart';

class BusinessTemplatesPage extends StatelessWidget {
  const BusinessTemplatesPage({super.key, required this.session});
  final BusinessSession session;
  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 2,
    child: Scaffold(
      appBar: AppBar(
        title: const Text('Vorlagen'),
        bottom: const TabBar(
          tabs: [
            Tab(text: 'Dokumentvorlagen'),
            Tab(text: 'Textbausteine'),
          ],
        ),
      ),
      body: TabBarView(
        children: [
          BusinessCollection(
            session: session,
            path: '/templates',
            title: 'Eigene Dokumentvorlagen',
            readPermission: 'finance.read',
            writePermission: 'settings.manage',
            createLabel: 'Vorlage erstellen',
            fields: const [],
            titleOf: (r) => '${r['name']}',
            subtitleOf: (r) =>
                '${businessDocumentKinds[r['kind']] ?? r['kind']} · Version ${r['revision']}',
            onCreate: () async {
              await Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) => BusinessDocumentEditor(
                    session: session,
                    templateMode: true,
                  ),
                ),
              );
            },
            onOpen: (r) async {
              if (session.canWrite('settings.manage')) {
                await Navigator.push<void>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => BusinessDocumentEditor(
                      session: session,
                      templateMode: true,
                      document: r,
                    ),
                  ),
                );
              } else {
                await showDialog<void>(
                  context: context,
                  builder: (_) => AlertDialog(
                    title: Text('${r['name']}'),
                    content: SingleChildScrollView(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${r['intro'] ?? ''}'),
                          for (final p in (r['positions'] as List? ?? []).map(
                            businessMap,
                          ))
                            ListTile(
                              title: Text('${p['description']}'),
                              subtitle: Text(
                                '${p['quantity']} ${p['unit']} · ${businessMoney(p['unit_price_net'])}',
                              ),
                            ),
                        ],
                      ),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Schließen'),
                      ),
                    ],
                  ),
                );
              }
            },
          ),
          BusinessCollection(
            session: session,
            path: '/text-blocks',
            title: 'Wiederverwendbare Texte',
            readPermission: 'finance.read',
            writePermission: 'settings.manage',
            createLabel: 'Textbaustein erstellen',
            fields: const [
              BusinessField('name', 'Bezeichnung', required: true),
              BusinessField(
                'text',
                'Text',
                type: BusinessInput.multiline,
                required: true,
              ),
            ],
            titleOf: (r) => '${r['name']}',
            subtitleOf: (r) => '${r['text']}',
          ),
        ],
      ),
    ),
  );
}
