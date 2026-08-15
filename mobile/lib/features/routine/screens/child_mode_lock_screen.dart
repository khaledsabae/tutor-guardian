import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../providers/child_mode_providers.dart';
import '../services/child_mode_secure_storage.dart';

/// Lock screen used to enter/exit child mode. PIN is verified locally.
class ChildModeLockScreen extends ConsumerStatefulWidget {
  const ChildModeLockScreen({
    super.key,
    required this.childId,
    required this.childName,
    this.isExit = false,
  });

  final int childId;
  final String childName;
  final bool isExit;

  @override
  ConsumerState<ChildModeLockScreen> createState() => _ChildModeLockScreenState();
}

String _localizedChildModeError(String? code, AppLocalizations l10n) {
  return switch (code) {
    kChildModeErrorPinRequired => l10n.childModePinRequired,
    kChildModeErrorPinIncorrect => l10n.childModePinIncorrect,
    kChildModeErrorSessionExpired => l10n.childModeSessionExpired,
    // Neither of these is a failure the child did anything to cause, and
    // neither should ever surface as a raw code — which is what the fallback
    // arm below would do.
    kChildModeBudgetSpent => l10n.childModeBudgetSpent,
    kChildModeOffline => l10n.childModeOffline,
    null => l10n.childModeEnterFailed,
    _ => code,
  };
}

class _ChildModeLockScreenState extends ConsumerState<ChildModeLockScreen> {
  final _pin = <String>[];
  String? _error;
  bool _firstSetup = false;
  String _confirmPin = '';

  @override
  void initState() {
    super.initState();
    _checkFirstSetup();
  }

  Future<void> _checkFirstSetup() async {
    final hasPin = await hasChildModePin();
    setState(() => _firstSetup = !hasPin);
  }

  void _onDigit(String d) {
    if (_pin.length >= 4) return;
    setState(() {
      _pin.add(d);
      _error = null;
    });
    if (_pin.length == 4) {
      final entered = _pin.join();
      if (_firstSetup && widget.isExit == false) {
        if (_confirmPin.isEmpty) {
          _confirmPin = entered;
          setState(_pin.clear);
        } else if (_confirmPin == entered) {
          _finish(entered);
        } else {
          _confirmPin = '';
          setState(() {
            _pin.clear();
            _error = AppLocalizations.of(context).childModePinMismatch;
          });
        }
      } else {
        _finish(entered);
      }
    }
  }

  Future<void> _finish(String pin) async {
    final l10n = AppLocalizations.of(context);
    final notifier = ref.read(childModeProvider.notifier);
    if (widget.isExit) {
      final ok = await notifier.exit(pin);
      if (mounted) {
        if (ok) {
          Navigator.of(context).pop(true);
        } else {
          setState(() {
            _pin.clear();
            _error = l10n.childModePinIncorrect;
          });
        }
      }
    } else {
      final ok = await notifier.enter(childId: widget.childId, pin: pin);
      if (mounted) {
        if (ok) {
          Navigator.of(context).pop(true);
        } else {
          setState(() {
            _pin.clear();
            _error = _localizedChildModeError(
                ref.read(childModeProvider).error, l10n);
          });
        }
      }
    }
  }

  void _backspace() => setState(() {
        if (_pin.isNotEmpty) _pin.removeLast();
        _error = null;
      });

  @override
  Widget build(BuildContext context) {
    final title = widget.isExit ? AppLocalizations.of(context).habitChildModeExitTitle : AppLocalizations.of(context).childMode;
    final subtitle = _firstSetup && !widget.isExit
        ? AppLocalizations.of(context).onbAgeGroup
        : AppLocalizations.of(context).chatOffline;

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(subtitle, textAlign: TextAlign.center),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  4,
                  (i) => Container(
                    margin: const EdgeInsets.symmetric(horizontal: 8),
                    width: 16,
                    height: 16,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: i < _pin.length
                          ? Theme.of(context).colorScheme.primary
                          : Colors.grey.shade300,
                    ),
                  ),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(
                  _error!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
              const SizedBox(height: 32),
              _buildKeypad(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildKeypad() {
    final keys = [
      ['1', '2', '3'],
      ['4', '5', '6'],
      ['7', '8', '9'],
      ['', '0', '⌫'],
    ];
    return Column(
      children: keys
          .map(
            (row) => Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: row
                  .map(
                    (k) => SizedBox(
                      width: 80,
                      height: 80,
                      child: k.isEmpty
                          ? const SizedBox()
                          : Padding(
                              padding: const EdgeInsets.all(6),
                              child: FilledButton.tonal(
                                onPressed: () =>
                                    k == '⌫' ? _backspace() : _onDigit(k),
                                child: Text(
                                  k,
                                  style: const TextStyle(fontSize: 22),
                                ),
                              ),
                            ),
                    ),
                  )
                  .toList(),
            ),
          )
          .toList(),
    );
  }
}
