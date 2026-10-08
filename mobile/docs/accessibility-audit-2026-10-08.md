# Accessibility audit — 8 October 2026

Scope: targeted static audit of `mobile/lib` at main `6be7311d`, with widget
Semantics regressions in Arabic and English. No emulator, local APK/AAB build,
or physical-device TalkBack session was used. Static sizing risks below are
not claims of observed device failures.

## Fixes in this PR

- Assistant send/stop: give the named semantic button its own tap action and
  enabled state; excluding the visual child previously removed the action.
- Today ask entry: expose a separately addressable named button while retaining
  its explanatory text. Child selector: localized action/name, decorative emoji
  exclusion and 48dp minimum; remove toolbar padding that squeezed its target.
- Child mode: describe Exit as exiting child mode, exclude redundant avatar
  emoji, and use directional padding in the persistent bar.
- Empty-state artwork/emoji and the Noor mascot: exclude decorative semantics;
  retain the meaningful localized text and actions beside them.
- Lesson favorite: explicit localized action semantics and a 48dp minimum.
- Hosted E2E selectors use the new localized send/exit labels; the exit
  confirmation dialog retains its existing localized text.
- Bilingual widget coverage for Today, lesson favorite state/target, assistant
  send and child-mode exit, plus decorative-image regressions.

## Follow-up findings

| Priority | Location | Remaining work |
| --- | --- | --- |
| P2 | `features/program/screens/story_reader_screen.dart`, `bedtime_routine_screen.dart` | Label icon-only round controls and raise 44dp targets to at least 48dp. |
| P2 | `features/coins/covenant_screen.dart`, `features/routine/screens/daily_routine_screen.dart`, `features/routine/screens/parenting_insights_screen.dart`, `features/onboarding/screens/avatar_picker_sheet.dart`, `features/games/shared/edu_game_ui.dart`, `edu_game_shell.dart`, `features/program/screens/podcast_player_screen.dart` | Add missing action tooltips; seek labels must state the actual −15/+30 seconds. |
| P2 | `features/home/widgets/home_shortcuts_grid.dart`, `today_rituals_row.dart`, `features/child_memory/widgets/personalised_chip.dart`, `features/program/screens/story_bookshelf_screen.dart` | Measure custom targets on-device; add minimum constraints, button roles and decorative emoji exclusion. |
| P2 | `features/program/screens/infographic_screen.dart`, `story_reader_screen.dart` | Provide infographic text equivalents and content-backed illustration descriptions. A generic image label would not describe the content. |
| P2 | `widgets/ui/celebration_overlay.dart`, `main.dart` | Exclude decorative artwork and redundant logo semantics. |
| P2 | `features/routine/screens/child_mode_lock_screen.dart` | Announce PIN progress/backspace without revealing digits; make the fixed keypad and subtitle/error reflow at large text/landscape. |
| P2 | `features/program/screens/lesson_screen.dart`, `search_screen.dart` | Verify/reflow the lesson badge row and fixed-height search field at 200% text on narrow devices. |
| P3 | `features/program/screens/quiz_game_screen.dart`, `story_bookshelf_screen.dart`, `screens/chat_screen.dart` | Replace physical positioning/padding where it represents start/end; verify reading order with Arabic content. |

Existing protections: many Material IconButtons already use ARB tooltips;
child-theme Material targets are 56dp; Today compose already reflows using
`textScalerOf`; global text scaling and locale Directionality are inherited.
The only explicit text-scaling suppression found is the fixed export image in
`features/programs/widgets/ramadan_recap_card.dart`, documented for export.

## Real-device TalkBack checklist (still required)

- [ ] Arabic and English: focus every Today action, lesson favorite, composer,
  send/stop and child-mode Exit; hear one useful label and role per action.
- [ ] Activate send and stop through TalkBack double-tap; verify disabled state
  and streaming transitions, focus retention, and no duplicate announcements.
- [ ] Navigate child selection, change children and confirm full spoken names.
- [ ] Confirm decorative graphics are skipped and informative images have usable
  descriptions/text equivalents when the follow-up work lands.
- [ ] Check actual touch areas, 200% text and landscape on a small phone;
  inspect child PIN, lesson badges, search and secondary story controls.
- [ ] Check RTL focus/read order, start/end spacing, mixed Arabic/English and
  mirrored directional icons. Check contrast and system font settings.

Widget tests inspect Flutter's semantics tree and target geometry; they cannot
establish Android TalkBack focus behavior, spoken output or device usability.
