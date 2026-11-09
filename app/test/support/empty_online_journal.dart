import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/online_command_journal.dart';

// These legacy unit fixtures have no device snapshots by construction. The
// actual protected-file discovery is covered separately with real encryption,
// retained files and HTTP. Never turn a production storage error into absence.
class EmptyOnlineJournalDevice extends OfflineDevice {
  @override
  Future<OfflineVault?> openExisting(String server, String user) async => null;
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async =>
      throw StateError('An empty legacy fixture must not create a device key');
}

OnlineCommandJournal emptyOnlineJournal() =>
    OnlineCommandJournal(device: EmptyOnlineJournalDevice());
