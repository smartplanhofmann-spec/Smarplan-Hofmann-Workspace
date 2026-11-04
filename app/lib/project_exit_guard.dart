import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

/// Keeps unsaved child editors safe when the surrounding project route closes.
/// Each project owns its own guard; clean child routes do not intercept back.
class ProjectExitGuard extends ChangeNotifier {
  final _editors = <Object, _ProjectExitCheck>{};
  bool _disposed = false, _checking = false, _scheduled = false;
  bool _lastBlocked = false;
  String? _lastReason;

  bool get blocked => _editors.values.any((editor) => editor.isBlocked());
  String? get pendingReason {
    for (final editor in _editors.values) {
      final reason = editor.pendingReason();
      if (reason != null) return reason;
    }
    return null;
  }

  void register(
    Object owner, {
    required bool Function() isBlocked,
    required String? Function() pendingReason,
    required Future<bool> Function() confirmExit,
  }) {
    if (_disposed) return;
    _editors[owner] = _ProjectExitCheck(isBlocked, pendingReason, confirmExit);
    changed();
  }

  void unregister(Object owner) {
    if (_disposed) return;
    _editors.remove(owner);
    changed();
  }

  void changed() {
    if (_disposed) return;
    final nextBlocked = blocked, nextReason = pendingReason;
    if (_lastBlocked == nextBlocked && _lastReason == nextReason) return;
    _lastBlocked = nextBlocked;
    _lastReason = nextReason;
    // A nested editor may disappear while its parent's stack is rebuilding.
    // Never notify that parent synchronously from child mount/unmount.
    if (SchedulerBinding.instance.schedulerPhase ==
        SchedulerPhase.persistentCallbacks) {
      if (_scheduled) return;
      _scheduled = true;
      SchedulerBinding.instance.addPostFrameCallback((_) {
        _scheduled = false;
        if (!_disposed) notifyListeners();
      });
    } else {
      notifyListeners();
    }
  }

  Future<bool> confirmExit() async {
    if (_disposed || _checking) return false;
    _checking = true;
    final checks = Map<Object, _ProjectExitCheck>.from(_editors);
    try {
      for (final entry in checks.entries) {
        if (_editors[entry.key] != entry.value || !entry.value.isBlocked()) {
          continue;
        }
        if (!await entry.value.confirmExit()) return false;
        if (_disposed) return false;
      }
      // A different editor opened while a confirmation was pending has not
      // agreed to discard anything. Its current work must remain mounted.
      return !_disposed &&
          !_editors.entries.any(
            (entry) =>
                checks[entry.key] != entry.value && entry.value.isBlocked(),
          );
    } finally {
      _checking = false;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _editors.clear();
    super.dispose();
  }
}

class _ProjectExitCheck {
  const _ProjectExitCheck(this.isBlocked, this.pendingReason, this.confirmExit);
  final bool Function() isBlocked;
  final String? Function() pendingReason;
  final Future<bool> Function() confirmExit;
}
