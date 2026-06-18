/// «رحلة الطفل» — the current-challenge catalogue (Phase 3).
///
/// Keys MUST match the backend `CHALLENGE_TOPICS` (coach_service.py). The
/// active challenge feeds the proactive coach as a higher-priority signal
/// than the parent's last chat question.
library;

class ChallengeOption {
  final String key;
  final String label;
  final String emoji;

  const ChallengeOption({
    required this.key,
    required this.label,
    required this.emoji,
  });
}

const List<ChallengeOption> challengeOptions = [
  ChallengeOption(key: 'sleep', label: 'النوم', emoji: '😴'),
  ChallengeOption(key: 'lying', label: 'الكذب', emoji: '🤥'),
  ChallengeOption(key: 'screens', label: 'الشاشات', emoji: '📱'),
  ChallengeOption(key: 'tantrums', label: 'العناد والغضب', emoji: '😤'),
  ChallengeOption(key: 'eating', label: 'الأكل', emoji: '🍽️'),
  ChallengeOption(key: 'hitting', label: 'الضرب', emoji: '✋'),
  ChallengeOption(key: 'fear', label: 'الخوف', emoji: '😨'),
  ChallengeOption(key: 'study', label: 'المذاكرة', emoji: '📚'),
];

ChallengeOption? challengeByKey(String? key) {
  if (key == null) return null;
  for (final c in challengeOptions) {
    if (c.key == key) return c;
  }
  return null;
}
