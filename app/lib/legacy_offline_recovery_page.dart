import 'package:flutter/material.dart';

import 'legacy_offline_recovery.dart';

class LegacyOfflineRecoveryPage extends StatefulWidget {
  const LegacyOfflineRecoveryPage({super.key, required this.recovery});
  final LegacyOfflineRecovery recovery;
  @override
  State<LegacyOfflineRecoveryPage> createState() =>
      _LegacyOfflineRecoveryPageState();
}

class _LegacyOfflineRecoveryPageState extends State<LegacyOfflineRecoveryPage>
    with WidgetsBindingObserver {
  String? error;
  String confirmedTime(LegacyTimeCheck row) {
    final value = row.confirmation!, at = value.occurredAt.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    const actions = {
      'start': 'Beginn',
      'pause': 'Pause',
      'resume': 'Fortsetzung',
      'stop': 'Ende',
    };
    return '${actions[value.action]} · ${two(at.day)}.${two(at.month)}.${at.year} ${two(at.hour)}:${two(at.minute)}:${two(at.second)} (Gerätezeit)';
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed &&
        !(state == AppLifecycleState.inactive && widget.recovery.unlocking))
      widget.recovery.clear();
  }

  Future<void> run(Future<void> Function() action) async {
    setState(() => error = null);
    try {
      await action();
    } catch (_) {
      if (mounted)
        setState(
          () => error = 'Abgleich nicht abgeschlossen. Der alte Gerätebestand bleibt erhalten. Erneut mit der ursprünglichen Firma und Verbindung prüfen.',
        );
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.recovery.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Alte Offline-Aufträge prüfen')),
    body: ListenableBuilder(
      listenable: widget.recovery,
      builder: (context, _) {
        final recovery = widget.recovery;
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text(
              'Erhaltenen Gerätebestand lesend abgleichen',
              style: TextStyle(fontSize: 21, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            const Text(
              'Alte Plan-, Zeit- und Protokollaufträge können bereits beim ursprünglichen Server angekommen sein. Der Abgleich überträgt ausschließlich Kennungen und Originalhashes. Erst nach passender Serverbestätigung erscheint das dort geprüfte Original.',
            ),
            const SizedBox(height: 12),
            const Text(
              'Der Gerätebestand bleibt unverändert. Ein fehlender Treffer bestätigt keine Nichtannahme. Ungeklärte Aufträge und andere alte Änderungen werden dadurch nicht zum erneuten Senden freigegeben.',
            ),
            const SizedBox(height: 16),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton.icon(
                onPressed: recovery.busy ? null : () => run(recovery.inspect),
                icon: const Icon(Icons.lock_open_outlined),
                label: const Text('Gerätebestand prüfen'),
              ),
            ),
            if (recovery.busy) const LinearProgressIndicator(),
            if (error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (recovery.inspected && !recovery.found)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  'Kein alter Gerätebestand für diese Serveradresse und dieses Konto gefunden.',
                ),
              ),
            if (recovery.found) ...[
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  '${recovery.plans.length} alte Planaufträge · ${recovery.times.length} Zeitaufträge${recovery.reports.isEmpty ? '' : ' · ${recovery.reports.length} Protokollaufträge'} · ${recovery.otherPending} weitere erhaltene Aufträge',
                ),
              ),
              for (final row in recovery.plans)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Planauftrag ${row.number}',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        Text(row.label),
                        if (row.serverTitle != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              'Bestätigtes Serveroriginal: ${row.serverTitle}',
                            ),
                          ),
                        const SizedBox(height: 8),
                        if (row.canCheck)
                          OutlinedButton(
                            onPressed: recovery.busy
                                ? null
                                : () =>
                                      run(() => recovery.check(row.number - 1)),
                            child: const Text('Ursprüngliche Annahme prüfen'),
                          ),
                      ],
                    ),
                  ),
                ),
              for (final row in recovery.reports)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Protokollauftrag ${row.number}',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        Text(row.label),
                        if (row.confirmation != null)
                          const Padding(
                            padding: EdgeInsets.only(top: 8),
                            child: Text(
                              'Passende unterschriebene Archivfassung und PDF im aktuell angemeldeten Unternehmen bestätigt. Der alte Gerätebestand bleibt unverändert.',
                            ),
                          ),
                        const SizedBox(height: 8),
                        if (row.canCheck)
                          OutlinedButton(
                            onPressed: recovery.busy
                                ? null
                                : () => run(
                                    () => recovery.checkReport(row.number - 1),
                                  ),
                            child: const Text(
                              'Ursprüngliches Protokoll prüfen',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              for (final row in recovery.times)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Zeitauftrag ${row.number}',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        Text(row.label),
                        if (row.confirmation != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(confirmedTime(row)),
                          ),
                        const SizedBox(height: 8),
                        if (row.canCheck)
                          OutlinedButton(
                            onPressed: recovery.busy
                                ? null
                                : () => run(
                                    () => recovery.checkTime(row.number - 1),
                                  ),
                            child: const Text(
                              'Ursprüngliches Zeitereignis prüfen',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  'Eine bestätigte Originalannahme gilt nur für diesen einzelnen Auftrag. Weitere unbewiesene Eingaben, Zeiten, Fotos und Berichte benötigen einen gesonderten Abgleich.',
                ),
              ),
            ],
          ],
        );
      },
    ),
  );
}
