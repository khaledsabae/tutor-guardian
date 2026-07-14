# Bedtime Routine Flow Implementation Plan (Step 2)

This plan outlines the design and implementation of the integrated Bedtime Routine Flow. Instead of opening a bedtime story directly, the mobile application will guide children through interactive bedtime adhkar (أذكار النوم), reward them with 5 coins, and then launch the story reader.

## Proposed Changes

### 1. Coins System Extension
#### [MODIFY] [coins_service.dart](file:///home/khalednew/projects/tutor-guardian/mobile/lib/features/coins/coins_service.dart)
- Add an `earn(int amount)` method to `CoinsService` to credit coins on-device:
  ```dart
  Future<int> earn(int amount) async {
    final p = await SharedPreferences.getInstance();
    final balance = (p.getInt(_kBalance) ?? 0) + amount;
    await p.setInt(_kBalance, balance);
    return balance;
  }
  ```

#### [MODIFY] [coins_providers.dart](file:///home/khalednew/projects/tutor-guardian/mobile/lib/features/coins/coins_providers.dart)
- Expose the `earn` method inside `CoinsNotifier`:
  ```dart
  Future<void> earn(int amount) async {
    await CoinsService.instance.earn(amount);
    state = await CoinsService.instance.read();
  }
  ```

---

### 2. Bedtime Routine Screen
#### [NEW] [bedtime_routine_screen.dart](file:///home/khalednew/projects/tutor-guardian/mobile/lib/features/program/screens/bedtime_routine_screen.dart)
- Create a beautiful stateful widget `BedtimeRoutineScreen`:
  - Uses the dark bedtime gradient theme and twinkly stars background.
  - Plays the gentle ambient background sound (`BedtimeAudioService`).
  - Implements a list of 3 children's bedtime adhkar:
    1. **«بِاسْمِكَ رَبِّي وَضَعْتُ جَنْبِي، وَبِكَ أَرْفَعُهُ»** (مرة واحدة)
    2. **«اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ»** (3 مرات)
    3. **«بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا»** (مرة واحدة)
  - Interactively tracks the counter for each dhikr (tapping the card decrements the count).
  - Triggers a rising star particle animation on each tap.
  - Shows a reward completion card when finished: "لقد قرأت أذكار النوم. حصلت على 5 🪙!"
  - Credits the coins using `ref.read(coinsProvider.notifier).earn(5)`.
  - Provides a primary button to launch the story reader screen using `Navigator.pushReplacement` (so back button goes to bookshelf).

---

### 3. Bookshelf Integration
#### [MODIFY] [story_bookshelf_screen.dart](file:///home/khalednew/projects/tutor-guardian/mobile/lib/features/program/screens/story_bookshelf_screen.dart)
- Update `_openStory` to push the new `BedtimeRoutineScreen` instead of `StoryReaderScreen` directly.

## Verification Plan

### Automated Tests
- Run `flutter analyze` to verify syntax.
- Run `flutter test` to check test suite.

### Manual Verification
- Tap a book cover on the bookshelf.
- Verify that `BedtimeRoutineScreen` loads.
- Complete the 3 adhkar and verify that the coin balance increases by 5 🪙.
- Tap "Start Story" and verify that `StoryReaderScreen` opens.
