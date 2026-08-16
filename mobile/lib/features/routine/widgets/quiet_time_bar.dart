/// Time, shown to a child without a number.
///
/// Rule 7 of the constitution is a calm design, and rule 1.3d of the plan says
/// this specifically: a candle burning down or a bar shortening, never digits.
/// The reason is not aesthetic. A number is a thing to bargain with — "five
/// more minutes" is only a sentence you can say if you can read the five. A
/// shortening bar is felt rather than negotiated.
///
/// `remainingSeconds` has been in the state since sprint 1, written on every
/// heartbeat, and read in exactly one place: a timer inside the game shell.
/// Nothing drew it. This is that widget.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/child_mode_providers.dart';

class QuietTimeBar extends ConsumerStatefulWidget {
  const QuietTimeBar({super.key, this.showCandle = true});

  /// The candle glyph is the whole point on a mission or story card, but it
  /// competes with the artwork inside a game, where a bare bar reads better.
  final bool showCandle;

  @override
  ConsumerState<QuietTimeBar> createState() => _QuietTimeBarState();
}

class _QuietTimeBarState extends ConsumerState<QuietTimeBar> {
  /// The largest remaining value we have seen this session, which is what the
  /// bar is a fraction of.
  ///
  /// The server sends `allowed_seconds` at open and `remaining_seconds` on
  /// each heartbeat, and it never restates the total — so the client has to
  /// remember the first number to draw the second as a proportion. Taking the
  /// maximum rather than the first also survives a surface switch, where the
  /// new allowance can be larger than what was left of the old one.
  int _full = 0;

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(childModeProvider);
    final remaining = state.remainingSeconds;

    // No session, or a server with the surface switched off: draw nothing at
    // all rather than an empty bar, which would read as "your time is up".
    if (remaining == null || state.sessionId == null) {
      return const SizedBox.shrink();
    }
    if (remaining > _full) _full = remaining;
    if (_full <= 0) return const SizedBox.shrink();

    final fraction = (remaining / _full).clamp(0.0, 1.0);
    final theme = Theme.of(context);

    // Three states, no gradient of alarm: burning, winding down, out. The
    // exit-ritual colour is a warmer neutral, not a red — the last minute is
    // an invitation to finish, not a warning.
    final Color colour;
    if (remaining <= 0) {
      colour = theme.colorScheme.outlineVariant;
    } else if (state.exitRitual) {
      colour = theme.colorScheme.tertiary;
    } else {
      colour = theme.colorScheme.primary;
    }

    return Semantics(
      // Screen readers are the one place a number is the accessible answer,
      // and it is read to whoever asked for it rather than displayed.
      label: '${(fraction * 100).round()}%',
      child: Row(
        children: [
          if (widget.showCandle) ...[
            Text(
              remaining <= 0 ? '🕯️' : '🔥',
              style: TextStyle(
                fontSize: 18,
                color: remaining <= 0 ? theme.colorScheme.outline : null,
              ),
            ),
            const SizedBox(width: 8),
          ],
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              // Animated so the bar glides between heartbeats instead of
              // stepping every thirty seconds — a jump draws the eye, which is
              // the opposite of what a quiet clock should do.
              child: TweenAnimationBuilder<double>(
                // No `begin`: the builder holds the previous value and lerps
                // from it when `end` changes. Setting begin would restart the
                // animation from the same point on every rebuild.
                tween: Tween(end: fraction),
                duration: const Duration(milliseconds: 600),
                builder: (context, value, _) => LinearProgressIndicator(
                  value: value,
                  minHeight: 6,
                  backgroundColor: theme.colorScheme.surfaceContainerHighest,
                  valueColor: AlwaysStoppedAnimation<Color>(colour),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
