"""English lexical routing, priority, and boundary regressions; no providers."""
import pytest

from app.services.domain_classifier import _keyword_fast_path


@pytest.mark.parametrize("question,expected", [
    *[(f"How do I teach my child {term}?", ["fiqh"]) for term in (
        "prayer", "salah", "fasting", "zakat", "hajj", "umrah", "Quran",
        "hadith", "dua", "wudu", "halal", "haram", "repentance", "Islamic manners")],
    *[(question, ["aqeedah"]) for question in (
        "My child asks who is Allah?", "Where is God?", "Who created God?",
        "Why did Allah create us?", "What happens after death?", "Explain the afterlife",
        "My child asks about death", "How do I explain heaven and hell?",
        "Teach the pillars of faith", "My child asks about angels")],
    *[(f"My child needs guidance about {term}.", ["cyber"]) for term in (
        "screen time", "YouTube", "TikTok", "Instagram", "Facebook", "WhatsApp",
        "Snapchat", "online safety", "cyberbullying", "social media", "video games",
        "internet", "smartphone", "digital privacy")],
    *[(f"My child has {term}.", ["medical"]) for term in (
        "anxiety", "depression", "tantrums", "biting", "hitting", "sleep problems",
        "fever", "nightmares", "asthma", "allergies", "seizures", "stuttering",
        "bedwetting", "panic attacks", "autism", "ADHD", "dyslexia")],
    *[(f"My child needs help with {term}.", ["development"]) for term in (
        "hearing", "hearing aids", "walking", "crawling", "teething", "growth",
        "motor skills", "milestones", "breastfeeding", "weaning", "potty training",
        "playing", "play", "sitting", "standing", "eye contact")],
    ("My child has speech delay", ["medical", "development"]),
    ("My daughter cannot hear her name", ["development"]),
    ("My son hears the bell", ["development"]),
    ("My daughter heard the alarm", ["development"]),
    ("My son bites his brother", ["medical"]),
    ("My daughter hits herself", ["medical"]),
    ("My child cannot sleep", ["medical"]),
    ("How do I add a child in this app?", ["app_help"]),
    ("How do I change the language in the app?", ["app_help"]),
    ("How do I exit child mode?", ["app_help"]),
    ("How do I delete my account?", ["app_help"]),
    ("How do I delete my data?", ["app_help"]),
    ("My child has fever during fasting", ["fiqh", "medical"]),
    ("My child asks about angels during prayer", ["fiqh", "aqeedah"]),
    ("My child has sleep problems after video games", ["cyber", "medical"]),
    ("How do I teach prayer and walking in this app?", ["fiqh", "development", "app_help"]),
    ("My child has FEVER", ["medical"]),
    ("My child needs PRAYER advice", ["fiqh"]),
    ("My child has fever and يلعب", ["medical", "development"]),
    ("My child asks about angels and الصلاة", ["fiqh", "aqeedah"]),
    ("Prayer, afterlife, internet, fever, crawling: change the language in the app", ["fiqh", "aqeedah", "cyber", "medical", "development", "app_help"]),
])
def test_english_keywords(question, expected):
    assert _keyword_fast_path(question) == expected


@pytest.mark.parametrize("question", [
    "We heard about a new policy", "I heard about this yesterday",
    "My child heard about a new policy", "My daughter hears that a trip is planned",
    "We hear from a friend", "My son heard from his teacher that class is cancelled",
    "A hearing about the budget", "The court hearing is tomorrow",
    "The speech was reported in a newspaper", "Explain reported speech",
    "The member remembers November", "The player won the playoff",
    "Display a replay", "A feverish debate", "A prayerful poem",
    "A biting critique of the policy", "The song is a hitting success",
    "The play store has a new listing", "The Play Store member heard about an update",
    "God willing we will travel", "Thank God for today", "The angelic painting is lovely",
    "A sleepless server", "My daughter heard that tomorrow is a holiday",
    "My child asks for a playground", "The development branch has been merged",
])
def test_english_adversarial_keywords_defer(question):
    assert _keyword_fast_path(question) is None


@pytest.mark.parametrize("question", [
    "My son heard the teacher explain the homework",
    "My child heard a speech by the mayor",
    "My child attended a court hearing",
    "My child likes the play store",
])
def test_reported_speech_and_non_auditory_hearings_defer(question):
    assert _keyword_fast_path(question) is None


@pytest.mark.parametrize("question", [
    "How do I explain angels to my child?",
    "How do I explain heaven to my child?",
    "How do I explain hell to my child?",
])
def test_explaining_belief_topics(question):
    assert _keyword_fast_path(question) == ["aqeedah"]


@pytest.mark.parametrize("question,expected", [
    ("My baby cannot hear", ["development"]),
    ("My child does not respond to sounds", ["development"]),
    ("My child is not talking yet", ["medical", "development"]),
    ("My child has delayed speech", ["medical", "development"]),
    ("My child has speech problems", ["medical", "development"]),
])
def test_child_auditory_and_speech_abilities(question, expected):
    assert _keyword_fast_path(question) == expected
