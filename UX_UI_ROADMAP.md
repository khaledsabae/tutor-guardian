# «المربّي» Mobile UI/UX Audit and Roadmap

**Date:** 2026-09-24
**Scope:** the Flutter app (`mobile/lib`, 58k LOC, Arabic-first RTL with English).
**Companion to:** [AUDIT_AND_ROADMAP.md](AUDIT_AND_ROADMAP.md).

**Method:**
- Read the theme, token and shared-widget layers, then walked the four primary journeys in code:
  - onboarding → home;
  - ask the assistant;
  - child profile, habits and challenges;
  - parent ↔ child mode.
- Measured what can be measured statically: contrast ratios, token adoption, state-widget adoption, haptic coverage.
- Every change shipped here passes `flutter analyze` (0 issues) and `flutter test` (520/520).

**Benchmarks:**
- Material 3 component and state guidance.
- WCAG 2.2 AA:
  - 1.4.3 text contrast;
  - 1.4.11 non-text contrast;
  - 2.5.8 target size;
  - 4.1.2 name/role/value.
- Apple HIG (feedback and haptics).
- The streaming conventions users now expect from AI chat products: immediate acknowledgement, follow-bottom, stop control.
- Habit-app patterns from children's learning products: streaks with forgiveness, and celebrating effort over punishing misses.

These are used as design principles, not as copies of any product.

---

## 1. Design system

### 1.1 What exists
| Layer | File | Notes |
|---|---|---|
| Palette | `theme/app_palette.dart` | Two palettes (light and dark "Islamic luxury": emerald + gold on cream or obsidian). Semantic warning, danger and tip colours. |
| Tokens | `theme/design_tokens.dart` (`Dt`) | Radii (card 24, button 18, sheet 28, pill), shadows, motion (200/350/600 ms), `pad=16`, per-domain gradients. |
| Theme | `theme/app_theme.dart` | M3 `ThemeData` from one builder; Cairo type ramp; button, input, card, nav-bar, snackbar themes. |
| Shared UI | `widgets/ui/*` | `EmptyState`, `ErrorRetryView`, `Skeleton`, `ProgressRing`, `AnimatedProgressBar`, `CelebrationOverlay`, `BouncyButton`, `StatChip`, … |

The identity is coherent, and the dark mode work (getters over a swappable palette) was a pragmatic and correct move.

### 1.2 Deficiencies
| # | Finding | Impact | Status |
|---|---|---|---|
| DS1 | **No on-colour tokens.** Button themes hard-coded `Colors.white`: dark ElevatedButton 2.54:1, dark FilledButton **1.67:1**, light FilledButton 3.19:1 (AA needs 4.5:1) | Primary actions unreadable in dark mode | ✅ `onPrimary`/`onAccent` tokens + themes; guarded by `design_system_contrast_test.dart` |
| DS2 | **Inputs had no error state.** `border` uses `BorderSide.none` and there was no `errorBorder`, so invalid fields showed only small red text, and focused-invalid showed the *green* focus ring | Validation errors missed | ✅ error, focused-error and disabled borders + `errorStyle` |
| DS3 | No `chipTheme`, `dialogTheme`, `bottomSheetTheme`, `textButtonTheme`, `listTileTheme` or `dividerTheme`, so each screen hand-styles them, and un-styled ones fall back to M3 defaults (8 px chips next to pill chips) | Visual inconsistency | ✅ standard themes; explicit per-widget styles still win |
| DS4 | Only one spacing token; **410** literal `fontSize:`, **166** hard-coded `Color(0x…)`, **201** `Colors.white/black` outside `theme/` | Drift, and dark-mode leaks | ✅ spacing scale `Dt.s4…s32`, `minTouch 48`, `minTouchChild 56`; 📋 migration (UX-1) |
| DS5 | `AppPalette.current` is a **mutable global** set in `MaterialApp.builder`. Widgets that don't depend on `Theme` keep stale colours after a light/dark switch, until they rebuild for another reason | Flicker and stale colours on theme toggle | 📋 move to a `ThemeExtension<AppColors>` read via `context`; keep the `Dt.*` getters as a deprecated shim during migration |
| DS6 | Domain gradients put white text on low-luminance-contrast bases: "medical" amber **1.67:1**, "islamic_parenting" emerald 2.54:1, "cyber" 3.68:1 | Card titles unreadable | 📋 add `onBase` per `DomainStyle`, or darken the text-bearing stop |
| DS7 | `success` (#10B981) used as a *text* colour on white is 2.54:1 | Low-legibility confirmations | 📋 use `success` for icons and fills only; add `successText` (#047857, 5.5:1) |
| DS8 | Cairo and the Quran fonts are fetched at runtime by `google_fonts`, not bundled. An offline first launch renders fallback glyphs (different Arabic shaping and metrics, causing layout shift), and each launch contacts `fonts.gstatic.com` | Offline quality, privacy | 📋 bundle `Cairo-{Regular,Medium,SemiBold,Bold,ExtraBold}.ttf` + OFL licence under `assets/google_fonts/`; set `GoogleFonts.config.allowRuntimeFetching = false` |
| DS9 | Only 17 `Semantics` in 58k LOC, against 19 `GestureDetector`s used as buttons | Screen-reader users can't operate custom controls | ✅ chat send/stop; 📋 audit the rest (UX-1) |

### 1.3 Target system
**Colour roles** (both palettes define every role, and every *on* pair is ≥ 4.5:1, enforced by a test):

| Role | Light | Dark | On-colour (L / D) |
|---|---|---|---|
| primary (trust, guidance) | #0F766E emerald | #10B981 | #FFFFFF / #04211B |
| accent (reward, warmth) | #D97706 gold | #FBBF24 | #1F1300 / #1F1300 |
| background | #FAF8F5 cream | #0A1210 | ink |
| surface / surfaceAlt | #FFFFFF / #F3EFEA | #131F1C / #1C2D29 | ink |
| success (icons and fills) | #10B981 | #34D399 | n/a (text uses `successText`) |
| warning, danger (safety) | yellow and red families, meaning preserved in both | | fg/bg pairs |

Why this palette works for parenting and education:
- Emerald reads as calm and trustworthy (the guidance voice).
- Gold is reserved for *earned* moments (streaks, celebrations, coins), so it keeps its signal value.
- Warm cream in light mode lowers glare for long reading.
- Red and yellow are reserved for safety content, never for decoration or for a child's "missed" state.

**Type ramp** (Cairo, tuned for long Arabic guidance):

| Style | Size / line height | Use |
|---|---|---|
| body | 16 / 1.7 | Assistant answers (currently 15 / 1.6; raise it, as Arabic diacritics need the leading) |
| bodySmall | 14 / 1.6 | Secondary text |
| title | 18–20 / 1.4, w700 | Card and section titles |
| label | 13–14, w700 | Buttons and chips |
| **measure** | ≤ 70 characters | Answer bubbles already cap at 78% width; keep that on tablets with a max width of about 640 dp |

**Spacing:** 4-pt scale (`Dt.s4…s32`). **Radii:** card 24 · button 18 · sheet 28 · chip pill. **Elevation:** tinted soft shadows (`Dt.cardShadow`), with no M3 surface tint. **Motion:** 200/350/600 ms with ease-out-cubic. Honour `MediaQuery.disableAnimations` (reduce motion); today the flutter_animate entrances ignore it.

**Core component specs** (to become shared widgets in `widgets/ui/`):
- **Buttons:** primary (filled, `onPrimary`), reward (gold, `onAccent`, used sparingly), secondary (outlined), and tertiary (text, minimum 48×48). One `AppButton` with `loading` and `icon` slots replaces the ad-hoc `ElevatedButton.styleFrom` calls.
- **Inputs:** filled surface, 18 radius, visible error outline, helper and error text in `errorStyle`, character counters where the backend limits length.
- **Cards:** surface, radius 24, `cardShadow`; content padding 16; the optional header row always pairs an icon with a title.
- **Dialogs and sheets:** radius 28; a sheet has a drag handle and is preferred over a dialog for choices; a dialog is for confirmations only.
- **State widgets:** `Skeleton` (loading), `EmptyState` (empty), `ErrorRetryView` (error), `OfflineBanner` (connectivity). See §4.

---

## 2. Conversational and AI interaction UX

### 2.1 Findings (`screens/chat_screen.dart`, `widgets/message_bubble.dart`, `state/chat_notifier.dart`)
| # | Finding | Status |
|---|---|---|
| C1 | **Streaming output ran below the fold.** Auto-scroll fired only when the *count* of messages changed, so tokens growing the last bubble were not followed | ✅ follows the stream when the reader is within 120 px of the bottom; scrolling up to reread is never interrupted |
| C2 | The send/stop control was a bare `GestureDetector`, with no accessible name, role or tooltip | ✅ `Semantics(button)` + `Tooltip` ("Send" / "Stop reply", new `chatStop` string) |
| C3 | An empty streaming bubble showed a Markdown "…" **and** the typing dots | ✅ dots only |
| C4 | Each token copies the whole message list and re-parses the full Markdown, which is O(n²) on long answers and janky on low-end Android | 📋 batch deltas every ~60 ms in the notifier; render the in-progress bubble as plain text and switch to Markdown on `done` |
| C5 | Errors are shown twice (inline under the bubble **and** as a top banner) | 📋 keep the inline error with a retry chip; the banner is only for session-level failures |
| C6 | The permanent "behaviour type (optional)" field sits above the conversation and takes about 64 dp, which matters with the keyboard up | 📋 fold it into a "context" chip in the composer |
| C7 | Suggested prompts only in the empty state; no follow-ups after an answer | 📋 see 2.3 |
| C8 | Metadata chips show internal jargon (`mode: retrieval_only/llm_generated`) to parents | 📋 replace with a "Sources" disclosure (see 2.2) |
| C9 | `notifier.setOnline(...)` is called **during build** (a side effect in build) | 📋 move to `ref.listen` |
| C10 | No "jump to latest" affordance once scrolled up | 📋 floating chip "↓ new reply" while streaming off-screen |
| C11 | Sending gave no tactile acknowledgement | ✅ `Haptics.selection()` on send |

### 2.2 Target response lifecycle
```
idle → sending (≤300 ms: user bubble appears, composer clears, selection haptic)
     → thinking (typing dots; after 3 s add reassurance copy: «أراجع المصادر…»)
     → streaming (text grows at ~60 ms cadence, follow-bottom, Stop visible)
     → done  (safety banner if any → answer → Sources ▸ → 👍/👎 → follow-up chips)
     ↘ stopped (partial kept, "Reply stopped" + Continue chip)
     ↘ error   (inline, one Retry chip, reason from describeFailure)
     ↘ offline (composer disabled, queued-question hint, OfflineBanner)
```
- **Loading indicator:** keep the three-dot typing indicator for the thinking phase. It is the convention parents recognise from messaging apps and it does not imply a known duration. A spinner or progress bar would falsely imply progress. Replace the dots with the text itself the moment the first token arrives.
- **Safety first:** safety banners already render *above* the answer, which is correct. Keep them visually distinct (danger or warning tokens with an icon) and never collapsible.
- **Sources:** a collapsed "Sources (n)" row listing `reference_info` titles builds trust for religious and medical guidance without cluttering the answer.

### 2.3 Follow-up action chips
- **Backend:** add an optional `follow_ups: list[str]` (≤ 3, generated with the answer or chosen from topic templates) to `AssistantReply`. Older clients ignore it.
- **Client:** show them under the last answer only. One tap sends the question, the same flow as the empty-state chips. Hide them while streaming.
- **Defaults when absent:** «أعطني مثالاً عملياً» (give me a practical example), «كيف أطبّقها مع عمر {age}» (how do I apply this at age {age}), «باختصار» (in short).

---

## 3. Parent dashboard and child growth tracking

### 3.1 Findings
| # | Finding | Status |
|---|---|---|
| G1 | Progress is shown as rings and bars only. There is no *trend* view for habits: parents cannot see "better than last week" | 📋 |
| G2 | Child habit card: hard-coded `Colors.green/orange/red` with white text (2.1–3.5:1), a **red ✗ for "missed" shown to the child**, three labelled buttons in a `Row` that overflows at large text or with English labels, no success feedback, and a white-on-primary "logged" chip that fails in dark mode | ✅ tokens + on-colours, neutral "missed", `Wrap`, 56 dp targets, success/warning haptics |
| G3 | A confirmation dialog on **every** child check-in | 📋 optimistic tap + 5 s "Undo" snackbar (fewer taps, same safety) |
| G4 | Celebrations exist only on lesson completion and in games; nothing on habit streak milestones | 📋 |
| G5 | Monthly-report streak and partial counts were wrong for multi-child families (server bug) | ✅ fixed on the backend (AUDIT H9) |

### 3.2 Recommended visualisations
| Question a parent asks | Visual | Notes |
|---|---|---|
| "Is this week better than last?" | **7-day habit strip** (a mini heatmap row per habit, filled / half / empty) | Glanceable on the Home card; no chart library needed (a `Row` of containers) |
| "Which habits are sticking?" | **Horizontal bar per habit**, % of days completed in the last 4 weeks | Sort by improvement, not by raw score |
| "How far along is the path?" | **Milestone path** (existing `ProgressRing` + lesson dots) | Already present; add the next milestone's label |
| "What happened this month?" | Monthly report card | Now correct per child |

If charting grows beyond these, adopt `fl_chart` (maintained, RTL-capable, no platform code) rather than more `CustomPainter`s. There are 7 already.

### 3.3 Gamification guardrails (aligned with the app's Islamic values)
- **Celebrate effort, don't punish misses.** "Missed" is neutral; streaks allow **one grace day a week** ("streak shield") so one bad day doesn't erase a month.
- **No loss-aversion dark patterns** (no "you'll lose your streak!" pushes to children). Reminders go to the parent.
- **Celebrations are capped:** confetti at milestones (3, 7, 30 days, a completed path), a light haptic for routine logs. Anything more becomes noise.
- **Intrinsic framing:** copy links a habit to its value («الصدق», «بر الوالدين») rather than to coins alone.

---

## 4. Edge states and micro-interactions

### 4.1 Findings
| # | Finding | Status |
|---|---|---|
| E1 | **10 error surfaces printed raw exceptions** (`TgApiError(500): …`, `SocketException: Failed host lookup`) inside Arabic sentences: add/edit child, delete/switch child, lesson marking, onboarding, story, routine QR, journey, children list | ✅ `describeFailure()` maps errors to the three existing explanations (offline / our side / try again) and passes through server-written 4xx messages |
| E2 | Offline is only signalled in chat (`connectivityProvider` has 2 users). The curriculum has an offline cache, but the UI never says "showing saved copy" | 📋 an app-level `OfflineBanner` in the shell, plus a "Saved copy · updated {time}" caption on cached screens |
| E3 | 49 bare `CircularProgressIndicator`s across 35 files, against 9 `Skeleton` users | 📋 skeletons for list and card screens; spinners only for sub-second button actions |
| E4 | No slow-network handling between "loading" and "timeout" (60 s HTTP, 5 min SSE) | 📋 after 8 s show «الاتصال بطيء…» with Cancel; after 20 s offer a retry |
| E5 | Haptics: 10 calls in 6 files, none on the daily actions | ✅ `core/haptics.dart` (semantic `selection` / `success` / `warning`) wired into chat send and child habit logging; 📋 lesson complete, challenge set, mission confirm; a "reduce haptics" setting |
| E6 | Parent ↔ child mode: PIN to enter and no PIN to exit (correct), but the child surface looks like the parent app, with no persistent "child mode" cue and parent-size targets | 📋 see 4.3 |
| E7 | Inline validation had no visible error state | ✅ DS2 |

### 4.2 Haptic map
| Event | Haptic |
|---|---|
| Tab or chip select, message send | `selection` |
| Habit logged, lesson completed, mission confirmed | `success` (light impact) |
| Action failed, PIN wrong | `warning` (medium impact) |
| Milestone celebration | `success` + confetti (once) |
| Never | on scroll, on every keystroke, on streaming tokens |

### 4.3 Child and teen surfaces
- **A distinct child theme** (`AppTheme.child()`): the same brand hues with larger type (+2 sp), 56 dp targets (`Dt.minTouchChild`), rounder cards and a playful accent. A persistent top bar reads «وضع الطفل» ("child mode") with the timer and an exit button (the parent PIN stays on *entry* only).
- **Transitions:** a full-screen fade-through (300 ms) with the child's avatar when entering, so the handoff is unmistakable; the reverse on exit.
- **Teen web (QR):** already visually distinct (dark slate). Align its tokens with the app palette, and keep the fixed XSS (AUDIT H8) covered by a test.

---

## 5. Accessibility baseline (applies to every phase)
- Text contrast ≥ 4.5:1 and non-text (borders, icons that carry meaning) ≥ 3:1. The token pairs are now tested.
- Every tappable is ≥ 48 dp (56 dp on child surfaces) and has a semantic label.
- Layouts survive text scale 200% (use `Wrap` or `Flexible`, never fixed-height text rows). Verify with a golden or widget test per key screen at `textScaler: 2.0`.
- RTL: use `EdgeInsetsDirectional` and `AlignmentDirectional` everywhere, and mirror directional icons (already the case for send).
- Reduce motion: gate flutter_animate entrances on `MediaQuery.disableAnimationsOf(context)`.

---

## 6. Phased rollout
| Phase | Scope | Exit criteria / metrics |
|---|---|---|
| **UX-0 (this PR)** | On-colour tokens; input error states; standard component themes; spacing and target tokens; chat follow-stream, accessible send/stop, no double placeholder; `describeFailure` in 10 places; child habit card (contrast, neutral miss, wrap, 56 dp, haptics); `Haptics` helper | `flutter analyze` 0 issues; 520/520 tests; contrast test green |
| **UX-1/UX-2 partial (v1.0.61, done)** | `onPrimary`/`onAccent`/`successText` tokens; WCAG-safe domain gradients (DS6, DS7); insights cards and metric tiles on semantic tokens (dark-mode leak fixed); home/children/lesson literals → tokens; thinking state with 3 s reassurance; 60 ms token batching (C4); inline retry as the single error surface (C5); follow-up chips + `follow_ups` model field (C7, 2.3); `mode` chip removed (C8); `setOnline` out of build (C9); jump-to-latest (C10); answer body 16/1.7 | 532/532 Flutter tests; contrast test covers domains + successText |
| **UX-1: foundations (2–3 wks)** | `ThemeExtension` migration (DS5); bundled fonts (DS8); domain on-colours (DS6, DS7); replace literal colours and sizes on the 10 most-used screens; Semantics pass on the 19 `GestureDetector` buttons; reduce-motion; 200% text-scale tests | 0 contrast failures in the token test; font requests at launch = 0; TalkBack walkthrough of the 4 key journeys passes |
| **UX-2: conversation (2 wks)** | Lifecycle states (2.2); token batching (C4); single error surface (C5); context chip (C6); follow-up chips + backend `follow_ups` (2.3); Sources disclosure (C8); jump-to-latest (C10) | Time-to-first-visible-token unchanged or better; follow-up chip CTR; "stopped" rate falls |
| **UX-3: growth and engagement (3 wks)** | 7-day habit strip and bars (3.2); optimistic check-in with undo (G3); streak shield and milestone celebrations (3.3); app-level offline banner and cached captions (E2); skeletons (E3); slow-network UX (E4) | D7 habit-logging retention; logs per active child per week; crash-free sessions |
| **UX-4: child surface (2 wks)** | `AppTheme.child()`, persistent child-mode bar, transitions (4.3); teen web token alignment | Child-mode session completion; accidental exits |

Each phase ships behind the existing force-update floor, so no feature needs a flag. Track the metrics through the existing `core/analytics.dart` events.
