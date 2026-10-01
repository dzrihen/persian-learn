# -*- coding: utf-8 -*-
"""Guard rails for template-generated sentences (Persian).

Root cause of the «من اگر دارم.» = «יש לי אם.» class of bugs: the old
generators (vocab_bank.generate_lemma_sentences / natural_rows_for_lemma)
filled open slot templates («من X دارم», «این X است», «لطفاً X بدهید», …)
with *any* unused lemma from the bank — conjunctions, prepositions,
pronouns, verbs, people, cities and even synthetic placeholder lemmas
(«مفهوم خوراک ۱۹۰۱»).

This module is the single source of truth for:
  * SAFE_NOUNS     – the only words allowed into a slot (concrete, verified
                     Hebrew gloss + Hebrew gender for «זה/זאת/אלה»)
  * TEMPLATES      – the only slot templates still in use, each limited to
                     the noun categories that make sense in it
  * slot_ok()      – hard rejection rules (stopwords, POS, placeholders)
  * LEGACY_PATTERNS/classify_legacy() – detector for old generated items
"""
import re

ZWNJ = "\u200c"

# Function words / pronouns / adverbs that must never fill a noun slot.
STOPWORDS = set("""
و یا اما ولی اگر چون پس که برای با از به در روی زیر بدون بعد قبل تا نزدیک دور
هم همیشه هرگز هیچ‌وقت هنوز فقط خیلی اینجا آنجا حالا الان بعداً شاید باید
چه چرا چطور کجا کی چقدر چند کدام من تو او ما شما آنها آن‌ها این آن
بله نه آره لطفاً متشکرم ممنون ببخشید سلام خداحافظ هست است نیست دارم
پیش پشت جلو کنار بین مثل مانند همه هر چیزی کسی خوب بد
""".replace("‌", ZWNJ).split())
FUNC_POS = {"conj", "prep", "pron", "adv", "intj", "v", "adj", "num", "phrase"}
PLACEHOLDER_RE = re.compile(r"[0-9۰-۹٠-٩]|^(مفهوم|واژه|اصطلاح)\s")
HE_PLACEHOLDER_RE = re.compile(r"מונח|\d")

# Concrete nouns allowed in slots: lemma -> (hebrew, hebrew_gender m/f/p, category)
SAFE_NOUNS = {
    # food & drink
    "نان": ("לחם", "m", "food"), "چای": ("תה", "m", "food"), "قهوه": ("קפה", "m", "food"),
    "شیر": ("חלב", "m", "food"), "پنیر": ("גבינה", "f", "food"), "برنج": ("אורז", "m", "food"),
    "مرغ": ("עוף", "m", "food"), "ماهی": ("דג", "m", "food"), "سوپ": ("מרק", "m", "food"),
    "سالاد": ("סלט", "m", "food"), "آبمیوه": ("מיץ", "m", "food"), "کیک": ("עוגה", "f", "food"),
    "بستنی": ("גלידה", "f", "food"), "سیب": ("תפוח", "m", "food"), "موز": ("בננה", "f", "food"),
    "پرتقال": ("תפוז", "m", "food"), "خیار": ("מלפפון", "m", "food"), "شکر": ("סוכר", "m", "food"),
    "نمک": ("מלח", "m", "food"), "کره": ("חמאה", "f", "food"), "ماست": ("יוגורט", "m", "food"),
    "تخم" + ZWNJ + "مرغ": ("ביצה", "f", "food"), "سیب" + ZWNJ + "زمینی": ("תפוח אדמה", "m", "food"),
    # household / personal objects
    "کلید": ("מפתח", "m", "object"), "چتر": ("מטרייה", "f", "object"), "کیف": ("תיק", "m", "object"),
    "موبایل": ("טלפון נייד", "m", "object"), "شارژر": ("מטען", "m", "object"), "قاشق": ("כף", "f", "object"),
    "چنگال": ("מזלג", "m", "object"), "چاقو": ("סכין", "f", "object"), "بشقاب": ("צלחת", "f", "object"),
    "لیوان": ("כוס", "f", "object"), "فنجان": ("ספל", "m", "object"), "بالش": ("כרית", "f", "object"),
    "پتو": ("שמיכה", "f", "object"), "خودکار": ("עט", "m", "object"), "کتاب": ("ספר", "m", "object"),
    "دفترچه": ("מחברת", "f", "object"), "نقشه": ("מפה", "f", "object"), "بلیط": ("כרטיס", "m", "object"),
    "حوله": ("מגבת", "f", "object"), "صابون": ("סבון", "m", "object"), "عینک": ("משקפיים", "p", "object"),
}

# Slot templates still allowed: (id, target, hebrew, allowed categories)
TEMPLATES = [
    ("want",  "{n} می" + ZWNJ + "خواهم.",   "אני רוצה {he}.",        {"food", "object"}),
    ("give",  "لطفاً {n} بدهید.",            "תנו לי {he}, בבקשה.",   {"food"}),
    ("have",  "در خانه {n} داریم.",          "יש לנו {he} בבית.",     {"food", "object"}),
    ("this",  "این {n} است.",                "{this} {he}.",          {"food", "object"}),
    ("where", "{n} کجاست؟",                  "איפה ה{he}?",           {"object"}),
]
HE_THIS = {"m": "זה", "f": "זאת", "p": "אלה"}


def norm(s):
    return (s or "").strip().replace("ي", "ی").replace("ك", "ک")


def slot_ok(entry, tmpl_id=None):
    """True only if a bank entry may fill a slot of template tmpl_id."""
    lem = norm(entry.get("lemma"))
    if not lem or lem in STOPWORDS or PLACEHOLDER_RE.search(lem):
        return False
    if entry.get("pos") in FUNC_POS:
        return False
    if HE_PLACEHOLDER_RE.search(entry.get("he") or ""):
        return False
    safe = SAFE_NOUNS.get(lem)
    if not safe:
        return False
    if tmpl_id:
        for tid, _, _, cats in TEMPLATES:
            if tid == tmpl_id:
                return safe[2] in cats
    return True


def render(tmpl_id, lemma):
    lem = norm(lemma)
    he, g, cat = SAFE_NOUNS[lem]
    for tid, t_ru, t_he, cats in TEMPLATES:
        if tid == tmpl_id and cat in cats:
            return t_ru.format(n=lem), t_he.format(he=he, this=HE_THIS[g])
    return None


# ---- detector for items produced by the OLD generator -------------------
MI = "می" + ZWNJ
LEGACY_PATTERNS = [
    ("have_i", re.compile(r"^من (?P<s>.+) دارم\.$")),
    ("have_we", re.compile(r"^ما (?P<s>.+) داریم\.$")),
    ("need", re.compile(r"^من به (?P<s>.+) نیاز دارم\.$")),
    ("want", re.compile(r"^من (?P<s>.+) " + MI + r"خواهم\.$")),
    ("give", re.compile(r"^لطفاً (?P<s>.+) بدهید\.$")),
    ("where_bad_order", re.compile(r"^کجا است (?P<s>.+)؟$")),
    ("this", re.compile(r"^این (?P<s>.+) است\.$")),
    ("good", re.compile(r"^(?P<s>.+) خوب است\.$")),
    ("very", re.compile(r"^خیلی (?P<s>.+) است\.$")),
    ("he_verb", re.compile(r"^او (?P<s>[^ ]+(?:ن|دن|تن))\.$")),
    ("he_wants", re.compile(r"^او " + MI + r"خواهد (?P<s>.+)\.$")),
    ("we_must", re.compile(r"^ما باید (?P<s>.+)\.$")),
]
OBJECT_TEMPLATES = {"have_i", "have_we", "need", "want", "give", "good"}
PEOPLE_THEMES = {"people", "professions"}
PLACE_THEMES = {"places", "city", "travel", "placesuf"}
PROPER = set(("ایران اصفهان شیراز تهران تبریز مشهد اورشلیم تل" + ZWNJ + "آویو اسرائیل").split())
HE_BROKEN_RE = re.compile(
    r"^(יש (לי|לנו)|זה|אני צריך|אני רוצה|בבקשה תנו|איפה ה?)\s*"
    r"(אם|או|בלי|לפני|אחרי|עם|ו|אבל|כי|למה|איך|תחת|על|עבור|ש|אז|מה|מי|כמה|עד|מ|ל|ב)[\.\?]$"
)


def classify_legacy(ru, he, bank_by_lemma):
    """Return (template_id, reason) for an old generated row, or None."""
    for tid, rx in LEGACY_PATTERNS:
        m = rx.match(ru or "")
        if not m:
            continue
        s = norm(m.group("s"))
        e = bank_by_lemma.get(s) or {}
        pos, theme = e.get("pos"), e.get("theme")
        if PLACEHOLDER_RE.search(s) or HE_PLACEHOLDER_RE.search(he or ""):
            return tid, "placeholder lemma"
        if tid in ("where_bad_order", "he_verb", "he_wants", "we_must"):
            return tid, "ungrammatical frame"
        if s in STOPWORDS or pos in {"conj", "prep", "pron", "adv", "intj"}:
            return tid, "function word in slot"
        if pos in {"v", "adj"}:
            return tid, "verb/adjective in noun slot"
        if tid in OBJECT_TEMPLATES and (theme in PEOPLE_THEMES):
            return tid, "person in object slot"
        if tid in OBJECT_TEMPLATES and (theme in PLACE_THEMES or s in PROPER):
            return tid, "place/proper noun in object slot"
        if s in PROPER:
            return tid, "place/proper noun in object slot"
        return tid, "retired template (off-topic filler)"
    return None
