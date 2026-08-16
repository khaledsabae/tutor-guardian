/// Why this app has no background audio, and must not gain it casually.
///
/// On 2026-08-16 I added `just_audio_background` so the screen-off listening
/// mode would keep playing with the display dark. It broke Qur'an recitation
/// for every user, and the podcast, and the bedtime ambience, and the
/// narration preview — with an error string that told them to check their
/// internet connection.
///
/// The first fix was wrong: I tagged every AudioSource with a MediaItem,
/// which is what the package's assertion asks for. Recitation still did not
/// play. The actual constraint is the first sentence of the package's own
/// README:
///
///   "It supports the simple use case where an app has a single AudioPlayer
///    instance. If your app has more complex requirements, it is recommended
///    that you instead use the audio_service package directly ... while also
///    allowing you to use multiple audio player instances."
///
/// This app has five AudioPlayer instances: recitation, podcast, bedtime
/// ambience, narration preview, screen-off. `just_audio_background` keeps one
/// (`_player ??= _JustAudioPlayer(...)`), so the other four are wired to a
/// background handler that is not theirs. Tags cannot fix that; it is the
/// wrong package for this app.
///
/// So it is reverted, and the screen-off mode goes back to stopping when
/// Android backgrounds the app. That is a real gap in a mode built around a
/// dark screen — but a gap in a new feature is worth less than recitation,
/// which thousands of families use every day.
///
/// **If background playback is picked up again, it is `audio_service`
/// directly, and it is its own piece of work** — one handler, every player
/// routed through it, and tested on a device before it goes anywhere near a
/// release. Not a line added to main() on the way to something else.
library;
