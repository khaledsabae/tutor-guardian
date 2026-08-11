/// Where «المربّي الذكي» publishes, as links a parent can open.
///
/// The URLs are taken from the accounts actually connected to the publishing
/// pipeline — the same three channels every reel is posted to — rather than
/// typed from memory, so a page linked here is a page that has content on it.
///
/// Facebook is addressed by its numeric page id. Vanity names can be changed by
/// their owner and then belong to someone else; the id cannot.
library;

import 'package:flutter/material.dart';

@immutable
class SocialLink {
  const SocialLink({
    required this.name,
    required this.url,
    required this.colour,
  });

  /// Brand names are proper nouns and stay in Latin in both locales — that is
  /// how the platforms write themselves, and Cairo carries the glyphs.
  final String name;
  final String url;
  final Color colour;
}

const kSocialLinks = <SocialLink>[
  // First, deliberately: it is the one channel a parent can subscribe to and
  // then keep receiving from without an algorithm deciding whether they see it.
  SocialLink(
    name: 'Telegram',
    // The public @username, not the invite link the autoposter's numeric chat
    // id would suggest — an invite link can be revoked and then leads nowhere,
    // while a shipped app keeps pointing at it.
    url: 'https://t.me/almorabii',
    colour: Color(0xFF229ED9),
  ),
  SocialLink(
    name: 'Facebook',
    url: 'https://www.facebook.com/1162484030288659',
    colour: Color(0xFF1877F2),
  ),
  SocialLink(
    name: 'Instagram',
    url: 'https://www.instagram.com/kh_abdalwahed/',
    colour: Color(0xFFE4405F),
  ),
  SocialLink(
    name: 'TikTok',
    url: 'https://www.tiktok.com/@khaled.sabae',
    colour: Color(0xFF111827),
  ),
];
