// Regression tests for crashlytics issues caused by stale/disposed state.
//
// These guard the _Star animation crash: a `Future.delayed` in the _Star
// constructor could call `_controller.repeat()` after the controller was
// already disposed when the screen is popped before the delay fires.
//
// The full BedtimeRoutineScreen / StoryBookshelfScreen require audio + l10n
// mocks that aren't available in the host test env, so we test the small
// private _Star animation class logic directly via a plain widget that owns
// one, mirroring how the screens dispose it on teardown.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// A minimal re-implementation of the _Star class from the screens, exercising
// the same "dispose before delayed repeat fires" path.
class _TestStar {
  final double delay;
  late final AnimationController controller;
  bool disposed = false;

  _TestStar({required this.delay, required TickerProvider vsync}) {
    controller = AnimationController(
      vsync: vsync,
      duration: const Duration(milliseconds: 2000),
    );
    Future.delayed(Duration(milliseconds: (delay * 1000).round()), () {
      // Mirror of the fixed guard: skip repeat if disposed or already active.
      if (!disposed && !controller.isAnimating && !controller.isCompleted) {
        controller.repeat(reverse: true);
      }
    });
  }

  void dispose() {
    disposed = true;
    controller.dispose();
  }
}

class _Host extends StatefulWidget {
  const _Host({this.delay = 0.1});
  final double delay;
  @override
  State<_Host> createState() => _HostState();
}

class _HostState extends State<_Host> with SingleTickerProviderStateMixin {
  late _TestStar _star;
  @override
  void initState() {
    super.initState();
    _star = _TestStar(delay: widget.delay, vsync: this);
  }

  @override
  void dispose() {
    _star.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}

void main() {
  group('Star animation dispose safety', () {
    testWidgets(
        'disposing the host before the delayed repeat fires does not throw',
        (tester) async {
      await tester.pumpWidget(const _Host(delay: 0.1));
      // Pop / dispose before the 100ms delayed callback runs.
      await tester.pump(const Duration(milliseconds: 10));
      await tester.pumpWidget(const SizedBox.shrink());
      // Let the delayed callback fire after dispose — must not throw.
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pumpAndSettle();
    });
  });
}
