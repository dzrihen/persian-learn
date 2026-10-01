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

import template_guard as G

# NOTE: open slot templates used to be filled with *any* unused bank lemma
# (conjunctions, pronouns, verbs, people, cities, placeholders), producing
# nonsense such as a "have" template filled with "if" / "or" (Hebrew: «יש לי אם»).
# Slots are now restricted to template_guard.SAFE_NOUNS (concrete nouns with
# verified Hebrew glosses) and each template only accepts the categories that
# make sense in it.  Everything else becomes a plain vocab row (word = gloss)
# or is skipped (placeholder lemmas).


def _plain_row_ok(u):
    lem, he = u.get("lemma") or "", u.get("he") or ""
    return bool(lem) and not G.PLACEHOLDER_RE.search(lem) and not G.HE_PLACEHOLDER_RE.search(he)


def natural_rows_for_lemma(u, rng=None):
    rng = rng or random.Random(hash(u["lemma"]) % 10_000)
    lem, he = u["lemma"], u["he"]
    if G.slot_ok(u):
        tids = [t[0] for t in G.TEMPLATES if G.slot_ok(u, t[0])]
        rng.shuffle(tids)
        rows = [G.render(t, lem) for t in tids[:3]]
        return [r for r in rows if r]
    return [(lem, he)] if _plain_row_ok(u) else []


def generate_lemma_sentences(tracker, cefr=("a1",), theme=None, count=8):
    """Template sentences ONLY for whitelisted concrete nouns (see template_guard)."""
    if isinstance(cefr, str):
        cefr = (cefr,)
    unused = tracker.pick(count * 6, cefr=cefr, theme=theme) or tracker.pick(count * 6, cefr=cefr) or tracker.pick(count * 6)
    nouns = [x for x in unused if G.slot_ok(x)]
    rng = random.Random(42 + len(tracker.introduced))
    rows = []
    for n in nouns:
        if len(rows) >= count:
            break
        tids = [t[0] for t in G.TEMPLATES if G.slot_ok(n, t[0])]
        if not tids:
            continue
        row = G.render(rng.choice(tids), n["lemma"])
        if not row:
            continue
        rows.append(row)
        tracker.mark_text(row[0])
    return rows
