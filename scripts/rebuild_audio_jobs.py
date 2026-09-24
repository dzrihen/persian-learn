# -*- coding: utf-8 -*-
"""Rebuild priority audio jobs (dialogues, top lemmas, A1 listen) + normalize aliases."""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def djb2(s: str) -> str:
    h = 5381
    for ch in s:
        h = ((h << 5) + h) ^ ord(ch)
        h &= 0xFFFFFFFF
    return format(h, "x")

def normalize_fa(text: str) -> str:
    s = str(text or "")
    # NFC
    s = s.replace("\u064a", "\u06cc").replace("\u0649", "\u06cc").replace("\u0643", "\u06a9")
    for a in ("\u0622", "\u0623", "\u0625", "\u0671"):
        s = s.replace(a, "\u0627")
    s = s.replace("\u0629", "\u0647")
    s = re.sub(r"[\u064b-\u065f\u0670]", "", s)
    s = re.sub(r"[\u200c\u200b\u200d\ufeff\u0640]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def text_hash(text: str) -> str:
    return djb2(normalize_fa(text))

def legacy_hash(text: str) -> str:
    return djb2(str(text or "").strip())

def decode_js_str(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "n":
                out.append("\n"); i += 2
            elif n == "t":
                out.append("\t"); i += 2
            elif n == "r":
                out.append("\r"); i += 2
            elif n in "\"'\\/":
                out.append(n); i += 2
            elif n == "u" and i + 5 < len(s):
                out.append(chr(int(s[i + 2 : i + 6], 16))); i += 6
            else:
                out.append(n); i += 2
        else:
            out.append(s[i]); i += 1
    return "".join(out)

def extract_listen_rus(*paths):
    texts = set()
    for p in paths:
        raw = pathlib.Path(p).read_text(encoding="utf-8")
        for m in re.finditer(
            r'"type"\s*:\s*"listen_(?:choice|order)"[\s\S]*?"ru"\s*:\s*"((?:\\.|[^"\\])*)"',
            raw,
        ):
            texts.add(decode_js_str(m.group(1)))
        # also dialogue turns in A1
        for m in re.finditer(
            r'"type"\s*:\s*"dialogue"[\s\S]*?"turns"\s*:\s*\[([\s\S]*?)\]',
            raw,
        ):
            block = m.group(1)
            for m2 in re.finditer(r'"ru"\s*:\s*"((?:\\.|[^"\\])*)"', block):
                texts.add(decode_js_str(m2.group(1)))
    return texts

def main():
    # Load sources
    dlg = json.loads((ROOT / "scripts/_dialogue_lines.json").read_text(encoding="utf-8"))
    top = json.loads((ROOT / "scripts/_top_lemmas.json").read_text(encoding="utf-8"))
    if top and isinstance(top[0], dict):
        top_texts = [x.get("text") or x.get("lemma") or x.get("ru") for x in top]
    else:
        top_texts = list(top)

    a1_listen = extract_listen_rus(ROOT / "data/a1-part1.js", ROOT / "data/a1-part2.js")

    # conversations ru too (dialogue-adjacent)
    conv_raw = (ROOT / "data/conversations.js").read_text(encoding="utf-8")
    conv_rus = {decode_js_str(m.group(1)) for m in re.finditer(r'"ru"\s*:\s*"((?:\\.|[^"\\])*)"', conv_raw)}

    existing = json.loads((ROOT / "scripts/_audio_jobs.json").read_text(encoding="utf-8"))
    by_legacy = {j["hash"]: j for j in existing}
    # also index by path
    by_norm_text = {}
    for j in existing:
        by_norm_text[normalize_fa(j["text"])] = j

    jobs = {j["hash"]: dict(j) for j in existing}  # keep all existing

    def ensure_job(text, folder):
        text = str(text or "").strip()
        if not text:
            return None
        norm = normalize_fa(text)
        h = text_hash(text)  # normalized
        h_legacy = legacy_hash(text)
        # Prefer existing file path if we already have this phrase
        prev = by_norm_text.get(norm) or by_legacy.get(h_legacy) or by_legacy.get(h)
        if prev:
            path = prev["path"]
        else:
            path = f"audio/{folder}/{h}.mp3"
        job = {"hash": h, "text": text if "\u200c" in text else norm, "path": path, "legacy_hash": h_legacy}
        # Keep original text for TTS (with ZWNJ is fine for speech)
        job["text"] = text
        jobs[h] = {"hash": h, "text": text, "path": path}
        if h_legacy != h:
            # alias entry not needed in jobs file; handled in manifest
            pass
        return job

    for t in dlg:
        ensure_job(t, "dialogue")
    for t in top_texts:
        ensure_job(t, "lemmas")
    for t in a1_listen:
        ensure_job(t, "listen")
    for t in conv_rus:
        ensure_job(t, "dialogue")

    # Write jobs (unique by hash)
    out_jobs = sorted(jobs.values(), key=lambda j: (j["path"], j["hash"]))
    (ROOT / "scripts/_audio_jobs.json").write_text(
        json.dumps(out_jobs, ensure_ascii=False, indent=0) + "\n", encoding="utf-8"
    )
    print("jobs", len(out_jobs))

    # Rebuild manifest: keep existing paths, add normalized + legacy aliases
    man_path = ROOT / "audio" / "manifest.json"
    manifest = {}
    if man_path.exists():
        manifest = json.loads(man_path.read_text(encoding="utf-8"))

    # Map existing files
    missing = []
    for j in out_jobs:
        p = ROOT / j["path"]
        h = j["hash"]
        hl = legacy_hash(j["text"])
        hn = text_hash(j["text"])
        if p.exists() and p.stat().st_size > 200:
            manifest[h] = j["path"]
            manifest[hn] = j["path"]
            manifest[hl] = j["path"]
        else:
            # maybe file exists under legacy filename
            alt = ROOT / f"audio/{pathlib.Path(j['path']).parent.name}/{hl}.mp3"
            if alt.exists() and alt.stat().st_size > 200:
                rel = str(alt.relative_to(ROOT)).replace("\\", "/")
                j["path"] = rel
                jobs[h]["path"] = rel
                manifest[h] = rel
                manifest[hn] = rel
                manifest[hl] = rel
            else:
                missing.append(j)

    # Also alias every existing manifest entry's file by scanning jobs text
    for j in existing:
        p = j["path"]
        full = ROOT / p
        if full.exists() and full.stat().st_size > 200:
            manifest[j["hash"]] = p
            manifest[legacy_hash(j["text"])] = p
            manifest[text_hash(j["text"])] = p

    man_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # rewrite jobs with updated paths
    out_jobs = sorted(jobs.values(), key=lambda j: (j["path"], j["hash"]))
    (ROOT / "scripts/_audio_jobs.json").write_text(
        json.dumps(out_jobs, ensure_ascii=False, indent=0) + "\n", encoding="utf-8"
    )

    # Write only-missing jobs for gen
    miss_path = ROOT / "scripts/_audio_jobs_missing.json"
    miss_path.write_text(json.dumps(missing, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print("manifest keys", len(manifest))
    print("missing to generate", len(missing))
    for j in missing[:20]:
        print(" MISS", j["hash"], j["path"], repr(j["text"][:60]))

if __name__ == "__main__":
    main()
