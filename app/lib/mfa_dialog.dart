import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'api.dart';

class MfaDialog extends StatefulWidget {
  const MfaDialog({
    super.key,
    required this.api,
    required this.challenge,
    this.enrollment,
  });
  final OfficeApi api;
  final String challenge;
  final Map<String, dynamic>? enrollment;

  @override
  State<MfaDialog> createState() => _MfaDialogState();
}

class _MfaDialogState extends State<MfaDialog> {
  final code = TextEditingController();
  bool busy = false;
  String? error;

  @override
  void dispose() {
    code.dispose();
    super.dispose();
  }

  Future<void> verify() async {
    if (busy || code.text.trim().isEmpty) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = Map<String, dynamic>.from(
        await widget.api.call('/api/login/verify', {
          'challenge': widget.challenge,
          'code': code.text.trim(),
        }),
      );
      if (mounted) Navigator.pop(context, result);
    } catch (failure) {
      if (mounted) setState(() => error = failure.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.enrollment == null
          ? 'Anmeldung bestätigen'
          : 'Authenticator einrichten',
    ),
    content: SizedBox(
      width: 440,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (widget.enrollment case final enrollment?) ...[
              const Text(
                'Füge in deiner Authenticator-App ein Konto hinzu und scanne diesen QR-Code. '
                'Den QR-Code und den Schlüssel nur für dich aufbewahren.',
              ),
              const SizedBox(height: 16),
              Center(
                child: QrImageView(
                  data: enrollment['uri'] as String,
                  size: 210,
                  backgroundColor: Colors.white,
                ),
              ),
              ExpansionTile(
                title: const Text('Manueller Schlüssel'),
                children: [
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: SelectableText(enrollment['secret'] as String),
                  ),
                ],
              ),
              const SizedBox(height: 12),
            ] else ...[
              const Text(
                'Gib den aktuellen sechsstelligen Code deiner Authenticator-App ein. '
                'Du kannst auch einen unbenutzten Wiederherstellungscode verwenden.',
              ),
              const SizedBox(height: 16),
            ],
            TextField(
              controller: code,
              enabled: !busy,
              autofocus: widget.enrollment == null,
              autocorrect: false,
              enableSuggestions: false,
              maxLength: 32,
              autofillHints: const [AutofillHints.oneTimeCode],
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => verify(),
              decoration: const InputDecoration(labelText: 'Bestätigungscode'),
            ),
            if (error != null)
              Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: busy ? null : verify,
        child: Text(busy ? 'Wird geprüft …' : 'Bestätigen'),
      ),
    ],
  );
}

class RecoveryCodesDialog extends StatelessWidget {
  const RecoveryCodesDialog({super.key, required this.codes});
  final List<String> codes;

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: false,
    child: AlertDialog(
      title: const Text('Wiederherstellungscodes sichern'),
      content: SizedBox(
        width: 460,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Diese Codes werden einmal angezeigt. Bewahre sie in deinem Passwortmanager '
                'oder ausgedruckt an einem sicheren Ort auf. Jeder Code kann einmal verwendet werden, '
                'wenn dein Authenticator nicht verfügbar ist.',
              ),
              const SizedBox(height: 20),
              SelectableText(
                codes.join('\n'),
                style: const TextStyle(fontFamily: 'monospace', height: 1.8),
              ),
            ],
          ),
        ),
      ),
      actions: [
        FilledButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Codes sicher aufbewahrt'),
        ),
      ],
    ),
  );
}
