"""English lexical routing, priority, and boundary regressions; no providers.

A fast-path hit blocks the model classifier and the query rewrite, so these
rules trade recall for precision: when an English word is ambiguous the fast
path returns None and the model decides.
"""
import time

import pytest

from app.services.domain_classifier import (
    _keyword_fast_path, _weak_app_signal, fallback_domains,
)


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
        "anxiety", "depression", "tantrums", "a biting phase", "a hitting habit",
        "sleep problems", "fever", "nightmares", "asthma", "allergies", "seizures",
        "stuttering", "bedwetting", "panic attacks", "autism", "ADHD", "dyslexia")],
    *[(f"My child needs help with {term}.", ["development"]) for term in (
        "hearing aids", "crawling", "teething", "growth delay", "motor skills",
        "milestones", "breastfeeding", "weaning", "potty training", "eye contact")],
    ("My child has speech delay", ["medical", "development"]),
    ("My daughter cannot hear her name", ["development"]),
    ("My son hears the bell", ["development"]),
    ("My daughter heard the alarm", ["development"]),
    ("My son bites his brother", ["medical"]),
    ("My daughter hits herself", ["medical"]),
    ("My child cannot sleep", ["medical"]),
    ("How do I exit child mode?", ["app_help"]),
    ("How do I delete my account?", ["app_help"]),
    ("How do I delete my data?", ["app_help"]),
    ("My child has fever during fasting", ["fiqh", "medical"]),
    ("My child asks about angels during prayer", ["fiqh", "aqeedah"]),
    ("My child has sleep problems after video games", ["cyber", "medical"]),
    ("How do I teach my son prayer? Also how do I change the language in the app?",
     ["fiqh", "app_help"]),
    ("My child has FEVER", ["medical"]),
    ("My child needs PRAYER advice", ["fiqh"]),
    ("My child has fever and يلعب", ["medical", "development"]),
    ("My child asks about angels and الصلاة", ["fiqh", "aqeedah"]),
    ("Prayer, afterlife, my son's internet use, fever and crawling: change the language in the app",
     ["fiqh", "aqeedah", "cyber", "medical", "development", "app_help"]),
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
    "My son's hearing in court is next week",
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
    ("My baby can't hear", ["development"]),
    ("My baby can’t hear", ["development"]),
    ("My daughter can't hear in one ear", ["development"]),
    ("My child does not respond to sounds", ["development"]),
    ("My child is not talking yet", ["medical", "development"]),
    ("My child has delayed speech", ["medical", "development"]),
    ("My child has speech problems", ["medical", "development"]),
])
def test_child_auditory_and_speech_abilities(question, expected):
    assert _keyword_fast_path(question) == expected


# ── P1-a: «the app» + a verb is the weak signal, never a verdict on its own ──

@pytest.mark.parametrize("question", [
    "How do I change the language in the app?",
    "Where are the settings in the app?",
    "How do I add a child in this app?",
    "How do I add my second child to the app?",
    "How do I turn off notifications in the app?",
    "the app settings",
    "Is the app's subscription worth it?",
    "My son created an account in the app without my permission",
    "My internet is slow, the app won't load",
])
def test_app_weak_signal_alone_defers(question):
    assert _keyword_fast_path(question) is None
    assert _weak_app_signal(question)
    # The model's silence then reads as «about the app», as for Arabic.
    assert fallback_domains(question) == ["app_help"]


@pytest.mark.parametrize("question", [
    "The app told me to teach my son gratitude, how do I do it?",
    "I read in the app how to teach patience but my son refuses",
    "I like the app, how do I teach my son honesty?",
])
def test_the_app_with_teach_is_not_app_help(question):
    assert _keyword_fast_path(question) is None
    assert not _weak_app_signal(question)


def test_app_weak_signal_beside_a_parenting_domain_adds_app_help():
    assert _keyword_fast_path(
        "My daughter won't pray; how do I change the language in the app?") == ["fiqh", "app_help"]


@pytest.mark.parametrize("question,expected", [
    ("How do I enter child mode?", ["app_help"]),
    ("exit child mode", ["app_help"]),
    ("How do I delete my data from the app?", ["app_help"]),
    ("Delete my account", ["app_help"]),
    ("How do I delete my account on Roblox for my son?", ["cyber"]),
    ("My daughter wants me to delete my data from Instagram", ["cyber"]),
    ("delete my Snapchat account", None),
    ("delete my Facebook account", None),
    ("delete my TikTok account", None),
])
def test_strong_app_signals_and_third_party_platforms(question, expected):
    assert _keyword_fast_path(question) == expected


# ── P1-b: the fiqh vocabulary parents actually use ──────────────────────────

@pytest.mark.parametrize("question", [
    "Can I hit my child when he refuses to pray?",  # golden g-123
    "Should I hit my son if he doesn't pray at 10?",
    "My son prays five times a day, how do I encourage him?",
    "How do I teach my son to pray?",
    "My daughter won't pray",
    "My son is praying with his father",
    "My daughter prayed Fajr today",
    "My son misses salah at school",
    "How do I teach my son salat?",
    "My son wants to fast in Ramadan",
    "My son is noisy in the mosque",
    "My daughter refuses to wear the hijab",
    "Teach my son a dua before sleeping",
    "My son wants to go on Hajj with us",
    "My son started fasting this year",
])
def test_fiqh_terms(question):
    assert _keyword_fast_path(question) == ["fiqh"]


@pytest.mark.parametrize("question", [
    "My son loves Mo Salah",
    "My son's favorite player is Salah",
    "My daughter loves Dua Lipa songs",
    "I'm a member of the Hajj committee",
    "I prayed for my son",
    "My son drives a fast car",
    "My son eats too fast",
    "I do intermittent fasting at home",
])
def test_fiqh_lookalikes_defer(question):
    assert _keyword_fast_path(question) is None


@pytest.mark.parametrize("question,expected", [
    ("My son wants to fast in Ramadan but has a fever", ["fiqh", "medical"]),
    ("My daughter is praying less since she got a smartphone", ["fiqh", "cyber"]),
    ("My son prays but watches TikTok", ["fiqh", "cyber"]),
    ("My son reads the Quran on YouTube", ["fiqh", "cyber"]),
])
def test_fiqh_in_mixed_questions(question, expected):
    assert _keyword_fast_path(question) == expected


# ── P1-c: devices and platforms; «play» only in its developmental sense ─────

@pytest.mark.parametrize("question", [
    "My son is addicted to his phone",
    "My kid is on the iPad all day",
    "My daughter wants her own tablet",
    "My son spends hours on Roblox",
    "My son plays Fortnite all day",
    "My son plays on the iPad",
    "My daughter builds in Minecraft every night",
    "My son is gaming until midnight",
    "My son watches TikTok",
])
def test_cyber_devices_and_platforms(question):
    assert _keyword_fast_path(question) == ["cyber"]


@pytest.mark.parametrize("question", [
    "My phone won't charge",
    "Put my phone in sleep mode",
    "I found you on Facebook",
    "I heard about this app on Facebook",
    "The internet is down",
    "Did you hear about the TikTok ban?",
])
def test_cyber_terms_without_a_child_defer(question):
    assert _keyword_fast_path(question) is None


def test_a_medicine_tablet_is_not_a_device():
    assert _keyword_fast_path("My son takes a tablet for his allergy") == ["medical"]


@pytest.mark.parametrize("question", [
    "My son plays with toys alone all day",
    "My toddler doesn't play with other kids",
    "My daughter loves pretend play",
    "My son doesn't play",
])
def test_developmental_play(question):
    assert _keyword_fast_path(question) == ["development"]


@pytest.mark.parametrize("question", [
    "My son is playing football tomorrow",
    "My kids love to play outside",
    "My son plays the violin",
    "My son plays with his food",
    "I play with my son every day but he still cries",
    "My son wants me to play with him",
])
def test_everyday_play_defers(question):
    assert _keyword_fast_path(question) is None


def test_arabic_play_with_a_latin_platform_adds_cyber():
    assert _keyword_fast_path("ابني بيلعب Fortnite طول اليوم") == ["cyber", "development"]


# ── P2-a: hitting/biting needs a victim; idioms defer ───────────────────────

@pytest.mark.parametrize("question", [
    "My son keeps hitting his sister",
    "My toddler bites other kids at daycare",
    "My kid hit his teacher",
    "My child is hitting himself",
    "My son bites me when he is angry",
    "My daughter hits her friends",
])
def test_aggression_with_a_target(question):
    assert _keyword_fast_path(question) == ["medical"]


@pytest.mark.parametrize("question", [
    "My son hit puberty",
    "My son needs to hit the books",
    "My son keeps hitting snooze",
    "My son is a big hit at school",
    "The kids' song hits the charts",
    "Biting cold this morning, should my baby go out?",
    "My husband hits me",
    "My son said his teacher hits the students",
    "My child is not hitting anyone",
    "My son doesn't bite",
    "Is it ok to hit my kid?",
])
def test_hit_and_bite_idioms_defer(question):
    assert _keyword_fast_path(question) is None


@pytest.mark.parametrize("question", [
    "My daughter hit a milestone", "My daughter hit 10 months and isn't crawling",
])
def test_hit_a_milestone_is_not_aggression(question):
    assert "medical" not in (_keyword_fast_path(question) or [])


# ── P2-b: lookalikes for sleep, fever, growth and motor milestones ──────────

@pytest.mark.parametrize("question", [
    "The match was at fever pitch",
    "My son's growth mindset at school",
    "My wife has a fever",
    "My daughter has no fever",
    "I can't sleep",
    "I have anxiety",
    "I'm teething my puppy",
    "My son wants a growth chart for the economy project",
    "My son is walking to school alone now, is that safe?",
    "My daughter is standing for class president",
    "My son is sitting his exams next week",
    "I'm walking my baby in the stroller",
    "My son was not standing up for himself",
    "My son can't stand broccoli",
])
def test_lookalikes_defer(question):
    assert _keyword_fast_path(question) is None


@pytest.mark.parametrize("question", [
    "My baby isn't walking at 18 months",
    "My baby isn't sitting up yet",
    "My baby can't sit up",
    "My baby can't stand yet",
    "My baby isn't standing at 12 months",
    "My baby isn't crawling",
])
def test_motor_delay(question):
    assert _keyword_fast_path(question) == ["development"]


@pytest.mark.parametrize("question", [
    "My son has a fever of 39",
    "My baby won't sleep through the night",
    "Sleep training my baby",
    "I need some sleep tips for my baby",
    "My son has trouble sleeping",
])
def test_child_sleep_and_fever(question):
    assert _keyword_fast_path(question) == ["medical"]


# ── P2-c / P2-d ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("question", ["My son hears voices", "My son hears things that aren't there"])
def test_hearing_voices_is_not_development(question):
    assert "development" not in (_keyword_fast_path(question) or [])


def test_arabic_prayer_with_a_latin_platform_keeps_fiqh_or_defers():
    result = _keyword_fast_path("بنتي بتصلي وبتشوف TikTok")
    assert result is None or "fiqh" in result


# ── P3-c: contractions, only for a child's ability to speak ────────────────

@pytest.mark.parametrize("question,expected", [
    ("My 2 year old isn't talking", ["medical", "development"]),
    ("My son can't talk yet at 3", ["medical", "development"]),
    ("My child doesn't speak", ["medical", "development"]),
    ("My son isn't talking to me", None),
    ("My son doesn't speak Arabic", None),
    ("My son won't talk", None),
])
def test_speech_contractions(question, expected):
    assert _keyword_fast_path(question) == expected


# ── Arabic text: the English layer changes only ADHD ───────────────────────

@pytest.mark.parametrize("question,expected", [
    ("ابني عمره 11 سنة، مش قادر يركز في المذاكرة، هل ده ممكن يكون ADHD؟", ["medical"]),
    ("بنتي عندها 10 سنين، نشيطة زيادة عن اللزوم، هل كده عندها ADHD؟", ["medical", "development"]),
])
def test_arabic_adhd_now_reaches_medical(question, expected):
    assert _keyword_fast_path(question) == expected


@pytest.mark.parametrize("question", [
    "كيف يمكنني استخدام تطبيق Milestone Tracker؟",
    "ابني عنده fever",
    "ابني has fever",
])
def test_arabic_text_does_not_take_an_english_verdict(question):
    assert _keyword_fast_path(question) is None


# ── P3-a: linear time on the longest inputs ────────────────────────────────

@pytest.mark.parametrize("text", [
    "a" * 50000,
    "my son " + "play " * 10000 + "court",
    "my son " + "hearing " * 6000 + "court",
    "my son " + "play about " * 4500,
    "son " * 12500,
    "my son " + "hear the " * 5500,
    "the app " * 6000,
    "delete my " * 5000,
    "my son " + " " * 50000 + "x",
    "son\n" * 12500,
    "my son " + "cannot " * 7000,
    "my son " + "hits " * 10000,
    "my son " + "not " * 12000,
    "ابني " + "play يلعب " * 4000,
])
def test_fast_path_is_linear_on_50k_characters(text):
    # CPU time, not wall time: a quadratic scan costs CPU, a busy machine
    # (parallel suites) only costs waiting. The old «court» lookahead took
    # ~1.5 s of CPU on these inputs; linear rules take ~0.1-0.3 s.
    start = time.process_time()
    _keyword_fast_path(text[:50000])
    assert time.process_time() - start < 1.0


@pytest.mark.parametrize("question", ["My son has tantrumz", "My son has anxietyx"])
def test_medical_terms_end_on_a_word_boundary(question):
    assert _keyword_fast_path(question) is None
