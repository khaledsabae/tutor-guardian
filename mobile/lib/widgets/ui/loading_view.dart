/// Loading states that say something when the wait runs long (UX_UI_ROADMAP
/// E3, E4).
///
/// A bare centred spinner reads the same at one second and at fifty, and the
/// HTTP timeout is sixty. So: a skeleton shaped like the content for list and
/// card screens (a spinner only where no shape is known — media, sheets), and
/// under either, after [SlowNetworkHint.slowAfter] «الاتصال بطيء…» with a way
/// back, and after [SlowNetworkHint.retryAfter] a retry when the caller has one.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';
import 'skeleton.dart';

class LoadingView extends StatelessWidget {
  /// Card-shaped skeletons; the default for list and card screens.
  const LoadingView({
    super.key,
    this.count = 4,
    this.itemHeight = 110,
    this.onRetry,
  }) : _spinner = false,
       spinnerColor = null;

  /// A centred spinner, for content with no known shape (a player, a sheet).
  const LoadingView.spinner({super.key, this.onRetry, this.spinnerColor})
      : _spinner = true,
        count = 0,
        itemHeight = 0;

  final int count;
  final double itemHeight;
  final VoidCallback? onRetry;
  final Color? spinnerColor;
  final bool _spinner;

  @override
  Widget build(BuildContext context) {
    final hint = SlowNetworkHint(onRetry: onRetry);
    if (_spinner) {
      return Center(
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(color: spinnerColor),
              hint,
            ],
          ),
        ),
      );
    }
    return SingleChildScrollView(
      physics: const NeverScrollableScrollPhysics(),
      child: Column(
        children: [
          hint,
          SkeletonList(count: count, itemHeight: itemHeight),
        ],
      ),
    );
  }
}

/// Nothing for [slowAfter]; then a "slow connection" line (with Back when the
/// route can be left); after [retryAfter], a Retry button if [onRetry] is set.
class SlowNetworkHint extends StatefulWidget {
  const SlowNetworkHint({super.key, this.onRetry});

  static const slowAfter = Duration(seconds: 8);
  static const retryAfter = Duration(seconds: 20);

  final VoidCallback? onRetry;

  @override
  State<SlowNetworkHint> createState() => _SlowNetworkHintState();
}

class _SlowNetworkHintState extends State<SlowNetworkHint> {
  final List<Timer> _timers = [];
  bool _slow = false;
  bool _retry = false;

  @override
  void initState() {
    super.initState();
    _timers
      ..add(Timer(SlowNetworkHint.slowAfter, () {
        if (mounted) setState(() => _slow = true);
      }))
      ..add(Timer(SlowNetworkHint.retryAfter, () {
        if (mounted) setState(() => _retry = true);
      }));
  }

  @override
  void dispose() {
    for (final t in _timers) {
      t.cancel();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_slow) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final canLeave = ModalRoute.of(context)?.canPop ?? false;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              l10n.loadingSlow,
              textAlign: TextAlign.center,
              style: TextStyle(color: c.textSecondary, fontSize: 14),
            ),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 8,
              children: [
                if (_retry && widget.onRetry != null)
                  FilledButton.tonalIcon(
                    onPressed: widget.onRetry,
                    icon: const Icon(Icons.refresh),
                    label: Text(l10n.loadingRetry),
                  ),
                if (canLeave)
                  TextButton(
                    onPressed: () => Navigator.of(context).maybePop(),
                    child: Text(l10n.loadingCancel),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
