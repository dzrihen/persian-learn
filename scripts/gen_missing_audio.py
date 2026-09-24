# -*- coding: utf-8 -*-
import asyncio, json, pathlib, sys
import edge_tts

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOBS = json.loads((ROOT / "scripts/_audio_jobs_missing.json").read_text(encoding="utf-8"))
VOICE = "fa-IR-DilaraNeural"
# fallback male if needed
VOICE_ALT = "fa-IR-FaridNeural"
CONCURRENCY = 4

async def one(sem, job, manifest):
    path = ROOT / job["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 200:
        manifest[job["hash"]] = job["path"]
        return "skip"
    async with sem:
        for voice in (VOICE, VOICE_ALT):
            try:
                comm = edge_tts.Communicate(job["text"], voice, rate="-5%")
                await comm.save(str(path))
                if path.exists() and path.stat().st_size > 200:
                    manifest[job["hash"]] = job["path"]
                    return "ok:" + voice
            except Exception as e:
                last = e
                continue
        return f"err:{last}"

async def main():
    # list voices briefly
    voices = [v["ShortName"] for v in await edge_tts.list_voices() if v["ShortName"].startswith("fa-")]
    print("fa voices", voices)
    sem = asyncio.Semaphore(CONCURRENCY)
    man_path = ROOT / "audio" / "manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    if not JOBS:
        print("nothing missing")
        return
    outs = await asyncio.gather(*[one(sem, j, manifest) for j in JOBS])
    print(outs)
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("manifest", len(manifest))

asyncio.run(main())
