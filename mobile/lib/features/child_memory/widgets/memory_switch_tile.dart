/// The memory switch — device-wide, for every child (MOBILE_API §9.2).
///
/// Switching OFF never needs a proof and is never paused: stopping must
/// always work, so this tile is on screen in every state the memory screen
/// can be in, including a pause and a failed proof. Switching ON needs a
/// proven session; the repository proves and retries once.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../data/memory_models.dart';
import '../providers/memory_providers.dart';
import 'memory_errors.dart';

class MemorySwitchTile extends ConsumerStatefulWidget {
  const MemorySwitchTile({super.key, this.fallback});

  /// The settings that came with the facts list, used until (or instead of)
  /// the settings read.
  final MemorySettings? fallback;

  @override
  ConsumerState<MemorySwitchTile> createState() => _MemorySwitchTileState();
}

class _MemorySwitchTileState extends ConsumerState<MemorySwitchTile> {
  /// The value being saved, shown at once so the switch does not snap back.
  bool? _pending;
  bool _saving = false;

  Future<void> _set(bool enabled) async {
    if (_saving) return;
    setState(() {
      _pending = enabled;
      _saving = true;
    });
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context);
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      await container.read(memoryRepositoryProvider).setEnabled(enabled);
      container
        ..invalidate(memorySettingsProvider)
        // The Today follow-up card follows the switch (hidden while off).
        ..invalidate(dueFollowupsProvider);
      // Switching on proved this session: the facts can load now. Switching
      // off must not reload anything that needs a proof — it would start a
      // challenge the parent did not ask for.
      if (enabled) container.invalidate(childMemoryProvider);
      if (mounted) setState(() => _saving = false);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _pending = null;
        _saving = false;
      });
      final text = describeActionFailure(context, e);
      messenger.showSnackBar(SnackBar(
        content: Text(text.isEmpty ? l10n.memorySwitchFailed : text),
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final read = ref.watch(memorySettingsProvider);
    final settings = read.valueOrNull ?? widget.fallback;
    final enabled = _pending ?? settings?.enabled;
    if (enabled == null) {
      // Nothing known yet (or no memory on this server): no switch to lie with.
      return read.isLoading
          ? const SizedBox(height: 72)
          : const SizedBox.shrink();
    }
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: BorderSide(color: colors.track),
    );
    // Its own Material, so the tile's ink is not painted under a coloured box.
    return Material(
      color: colors.surface,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: SwitchListTile(
        value: enabled,
        onChanged: _saving ? null : _set,
        contentPadding:
            const EdgeInsetsDirectional.fromSTEB(14, 4, 8, 4),
        shape: shape,
        title: Text(
          l10n.memorySwitchTitle,
          style: TextStyle(
              color: colors.ink, fontWeight: FontWeight.w700, fontSize: 15),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            enabled ? l10n.memorySwitchOn : l10n.memorySwitchOff,
            style: TextStyle(
                color: colors.textSecondary, fontSize: 12.5, height: 1.5),
          ),
        ),
      ),
    );
  }
}
