# -*- coding: utf-8 -*-
"""Persian lemma tracker + natural sentence templates."""
from collections import defaultdict
import re, random

FA_TOKEN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+")

def build_all_lemmas():
    from vocab_all import load_bank
    return load_bank()

class LemmaTracker:
    @staticmethod
    def norm(s):
        s = (s or "").strip()
        # unify Arabic yeh/kaf to Persian forms
        s = s.replace("ي", "ی").replace("ك", "ک")
        return s

    def __init__(self, bank=None):
        self.bank = bank or build_all_lemmas()
        self.by_lemma = {self.norm(x["lemma"]): x for x in self.bank}
        self.usage = defaultdict(int)
        self.introduced = set()

    def mark_text(self, text):
        toks = FA_TOKEN.findall(text or "")
        for w in toks:
            low = self.norm(w)
            hit = None
            if low in self.by_lemma:
                hit = low
            else:
                # light stemming: strip common clitics / endings
                for end in ("های", "ها", "ان", "ات", "ین", "ون", "مان", "تان", "شان",
                            "م", "ت", "ش", "ید", "یم", "ند", "ی", "ه"):
                    if len(low) > len(end) + 1 and low.endswith(end):
                        stem = low[:-len(end)]
                        for cand in (stem, stem+"ن", stem+"دن", stem+" کردن", stem+"ه", stem+"ی"):
                            if cand in self.by_lemma:
                                hit = cand
                                break
                        if hit:
                            break
            if hit:
                self.usage[hit] += 1
                self.introduced.add(hit)

    def mark_lemma(self, lem):
        k = self.norm(lem)
        if k in self.by_lemma:
            self.usage[k] += 1
            self.introduced.add(k)

    def pick(self, n, cefr=None, theme=None):
        def ok(x):
            if cefr:
                c = cefr if isinstance(cefr, (list, tuple, set)) else (cefr,)
                if x.get("cefr") not in c:
                    return False
            if theme and x.get("theme") != theme:
                return False
            return True
        unused = [x for x in self.bank if self.norm(x["lemma"]) not in self.introduced and ok(x)]
        unused.sort(key=lambda x: self.usage[self.norm(x["lemma"])])
        return unused[:n]

    def sample_band(self, n, cefr=None):
        pool = self.pick(n * 3, cefr=cefr) or self.pick(n * 3)
        pool.sort(key=lambda x: (self.usage[self.norm(x["lemma"])], x["lemma"]))
        return pool[:n]

    def stats(self):
        return {"bank_size": len(self.bank), "introduced": len(self.introduced)}

def natural_rows_for_lemma(u, rng=None):
    rng = rng or random.Random(hash(u["lemma"]) % 10_000)
    lem, he, pos = u["lemma"], u["he"], u["pos"]
    rows = []
    if pos == "v":
        frames = [
            (f"من {lem}.", f"אני {he}."),
            (f"او می‌خواهد {lem}.", f"הוא/היא רוצה {he}."),
            (f"ما باید {lem}.", f"אנחנו צריכים {he}."),
            (f"لطفاً {lem}.", f"בבקשה {he}."),
        ]
    elif pos == "adj":
        frames = [
            (f"این {lem} است.", f"זה {he}."),
            (f"خیلی {lem} است.", f"זה מאוד {he}."),
            (f"او {lem} است.", f"הוא/היא {he}."),
            (f"خانه {lem} است.", f"הבית {he}."),
        ]
    elif pos == "phrase":
        frames = [(lem, he)]
    else:
        frames = [
            (f"این {lem} است.", f"זה {he}."),
            (f"من {lem} دارم.", f"יש לי {he}."),
            (f"کجا است {lem}؟", f"איפה ה{he}?"),
            (f"من به {lem} نیاز دارم.", f"אני צריך {he}."),
            (f"{lem} خوب است.", f"{he} טוב."),
        ]
    rng.shuffle(frames)
    for ru, h in frames[:3]:
        rows.append((ru, h))
    return rows

def generate_lemma_sentences(tracker, cefr=("a1",), theme=None, count=8):
    if isinstance(cefr, str):
        cefr = (cefr,)
    unused = tracker.pick(count * 2, cefr=cefr, theme=theme) or tracker.pick(count * 2, cefr=cefr) or tracker.pick(count * 2)
    rows = []
    used_local = set()
    nouns = [x for x in unused if x["pos"] in ("n", "phrase", "num")]
    verbs = [x for x in unused if x["pos"] == "v"]
    adjs = [x for x in unused if x["pos"] == "adj"]
    templates = [
        ("این {n} است.", "זה {n_he}."),
        ("من {n} می‌خواهم.", "אני רוצה {n_he}."),
        ("{n} {adj} است.", "{n_he} {adj_he}."),
        ("او {v}.", "הוא/היא {v_he}."),
        ("ما {n} داریم.", "יש לנו {n_he}."),
        ("لطفاً {n} بدهید.", "בבקשה תנו {n_he}."),
    ]
    rng = random.Random(42 + len(tracker.introduced))
    for _ in range(count * 3):
        if len(rows) >= count:
            break
        tmpl_ru, tmpl_he = rng.choice(templates)
        slots = {}
        if "{n}" in tmpl_ru:
            if not nouns:
                continue
            n = rng.choice(nouns)
            if n["lemma"] in used_local and len(nouns) > 1:
                n = rng.choice(nouns)
            slots["n"] = n["lemma"]; slots["n_he"] = n["he"]
            used_local.add(n["lemma"])
            tracker.mark_text(n["lemma"])
        if "{v}" in tmpl_ru:
            if not verbs:
                continue
            v = rng.choice(verbs)
            slots["v"] = v["lemma"]; slots["v_he"] = v["he"]
            used_local.add(v["lemma"])
            tracker.mark_text(v["lemma"])
        if "{adj}" in tmpl_ru:
            if not adjs:
                continue
            a = rng.choice(adjs)
            slots["adj"] = a["lemma"]; slots["adj_he"] = a["he"]
            used_local.add(a["lemma"])
            tracker.mark_text(a["lemma"])
        try:
            ru = tmpl_ru.format(**slots)
            he = tmpl_he.format(**slots)
        except KeyError:
            continue
        rows.append((ru, he))
        tracker.mark_text(ru)
    return rows
