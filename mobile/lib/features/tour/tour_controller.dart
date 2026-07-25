/// Cursor state for the guided tour.
///
/// Deliberately tiny: which step is showing, and whether the tour is up at
/// all. The step *content* lives with the overlay — this notifier never needs
/// a `BuildContext`, so it stays testable.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

class TourState {
  const TourState({this.active = false, this.index = 0, this.total = 0});

  final bool active;
  final int index;
  final int total;

  /// True when [index] is the last spotlight — the button reads «تمام», and
  /// advancing finishes rather than moves on.
  bool get isLast => total > 0 && index >= total - 1;

  TourState copyWith({bool? active, int? index, int? total}) => TourState(
        active: active ?? this.active,
        index: index ?? this.index,
        total: total ?? this.total,
      );
}

class TourController extends StateNotifier<TourState> {
  TourController() : super(const TourState());

  void start(int total) {
    if (total <= 0) return;
    state = TourState(active: true, index: 0, total: total);
  }

  /// Advance one spotlight. Returns `true` when that ended the tour, so the
  /// caller knows whether to report completion.
  bool next() {
    if (!state.active) return false;
    if (state.isLast) {
      stop();
      return true;
    }
    state = state.copyWith(index: state.index + 1);
    return false;
  }

  void stop() => state = const TourState();
}

final tourControllerProvider =
    StateNotifierProvider<TourController, TourState>((ref) => TourController());
