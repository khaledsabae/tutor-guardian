/// A MediaItem for every audio source in the app.
///
/// `JustAudioBackground.init()` is global: once it runs, *every* AudioSource
/// must carry a MediaItem tag or `setUrl`/`setAsset`/`setFilePath` throws.
/// Turning background playback on for the screen-off mode therefore broke
/// four players that had worked for months — Qur'an recitation, the podcast,
/// the bedtime ambience and the narration preview — none of which had ever
/// needed a tag before.
///
/// This is the shared shape so the next player added cannot forget one.
library;

import 'package:just_audio_background/just_audio_background.dart';

MediaItem audioTag({
  required String id,
  required String title,
  String artist = 'المربي',
}) =>
    MediaItem(id: id, title: title, artist: artist);
