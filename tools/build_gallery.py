"""Builds the attack gallery (assets/gallery/) for the SEALBench website.

Synthetic images only (never real or manipulated MultiFakeVerse images).
Reads the research repo READ-ONLY; writes only into the website's assets/gallery/.

Entries
  * In-generation (Gaussian Shading, T2SMark on FLUX.1-dev): every attacked image is the
    evaluated file on disk under runs/2026-08-17_ingen-l14/attacked_wm.
  * Post-hoc (VideoSeal, synthetic FLUX.1-dev semantic arm): the post-hoc attacked pixels
    are archived off-disk, so C1 single perturbations and C3 chains are RE-RENDERED here
    with the benchmark's own seeded attack code (attacks/leveled_attacks.py apply_chain;
    stochastic stages are seeded per (stem, condition, stage, attack, severity)). The
    re-render was checked to be bit-identical to the on-disk in-gen attacked files for
    jpeg_50, gnoise_10, overlay_0.2, rotation_10, meme, messenger and social. C2/C4
    conditions need GPU-generated stages that are not on disk: file = null, metrics kept.

Per-condition values come from the per-image records (sources in SOURCES.md):
  asi       record "asi" (LPIPS to the pre-attack image)
  detected  post-hoc: max codeword match over the first 100 codebook identities > tau
            (tau = thresholds.csv, codebook mode, n_eval 100, far 0.01), as in
            post_hoc/evalaute_wm_metric.py; in-gen: record "score" > tau (eval_v2
            thresholds.csv, far 0.01).
  bit_acc   matches over the full gt_bits length (evaluate_semantic_metrics.py formula)
  decoded   semantic_encoding.decode_bits(dec_bits, packed5, 28)
  qsr       qsr_corrected = mean(correct) - mean(blank_correct) over the stored
            questions in qsr_qa.csv (Qwen2.5-7B-Instruct reader), plus per-question answers.

Run with a python that has cv2 (e.g. the auvire env):
    python -B tools/build_gallery.py
"""
import sys
sys.dont_write_bytecode = True
import csv, json, os, subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import cv2
from PIL import Image

import os
R = Path(os.environ.get("SEALBENCH_REPO", "../iclr_dataset"))
OUT = Path(__file__).resolve().parent.parent / "assets" / "gallery"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(R / "attacks"))
sys.path.insert(0, str(R / "post_hoc"))
sys.path.insert(0, str(R / "post_hoc" / "semantic"))
import leveled_attacks as LA                     # noqa: E402  (read-only import)
from semantic_encoding import decode_bits        # noqa: E402

WIDTH, QUALITY = 640, 82

INGEN = R / "runs/2026-08-17_ingen-l14"
SEM = R / "runs/2026-07-31_posthoc-semantic"
LEV = R / "runs/2026-08-02_leveled-eval"
CORPUS = json.loads((R / "post_hoc/semantic/semantic_corpus.json").read_text())
MSGS = {m["id"]: m for m in CORPUS["messages"]}

# (condition id, category, label, record attack, record severity, level dir)
CONDITIONS = [
    ("jpeg_50",        "C1", "JPEG, quality 50",                 "jpeg", "50", "level1"),
    ("crop_0.7",       "C1", "Crop, 0.7 of each side kept",      "crop", "0.7", "level1"),
    ("rotation_10",    "C1", "Rotation, 10 degrees",             "rotation", "10", "level1"),
    ("gnoise_10",      "C1", "Gaussian noise, sigma 10",         "gnoise", "10", "level1"),
    ("overlay_0.2",    "C1", "Overlay boxes, 0.2",               "overlay", "0.2", "level1"),
    ("gblur_7",        "C1", "Gaussian blur, kernel 7",          "gblur", "7", "level1"),
    ("edit_qwen",      "C2", "Prompt-based edit (Qwen-Image-Edit)", "edit", "qwen_image_edit_fast", "level1"),
    ("vae_q1",         "C2", "VAE regeneration, quality 1",      "vae", "q1", "level1"),
    ("diffusion_str0_2", "C2", "Diffusion regeneration, strength 0.2", "diffusion_modern", "str0_2", "level1"),
    ("unmarker",       "C2", "UnMarker",                         "unmarker", "default", "level1"),
    ("resize_jpeg_messenger", "C3", "messenger: resize 0.7, JPEG 70", "resize_jpeg_messenger", "chain", "level2"),
    ("crop_resize_jpeg_social", "C3", "social: crop 0.9, resize 0.7, JPEG 70", "crop_resize_jpeg_social", "chain", "level2"),
    ("overlay_resize_jpeg_meme", "C3", "meme: overlay 0.1, resize 0.7, JPEG 70", "overlay_resize_jpeg_meme", "chain", "level2"),
    ("edit_resize_jpeg_editshare_qwen", "C4", "editshare-qwen: edit (Qwen-Image-Edit), resize 0.7, JPEG 70",
     "edit_resize_jpeg_editshare_qwen", "chain", "level3"),
    ("diffusion_crop_jpeg_regenshare", "C4", "regenshare: diffusion regeneration, crop 0.9, JPEG 70",
     "diffusion_crop_jpeg_regenshare", "chain", "level3"),
    ("diffusion_gnoise_gblur_sharpen_jpeg_scrub", "C4",
     "scrub: diffusion regeneration, noise 2, blur 3, sharpen 1.0, JPEG 70",
     "diffusion_gnoise_gblur_sharpen_jpeg_scrub", "chain", "level3"),
]
SHORT = {"jpeg_50": "jpeg50", "crop_0.7": "crop07", "rotation_10": "rot10", "gnoise_10": "noise10",
         "overlay_0.2": "overlay02", "gblur_7": "blur7", "edit_qwen": "edit-qwen", "vae_q1": "vae-q1",
         "diffusion_str0_2": "diff02", "unmarker": "unmarker", "resize_jpeg_messenger": "messenger",
         "crop_resize_jpeg_social": "social", "overlay_resize_jpeg_meme": "meme",
         "edit_resize_jpeg_editshare_qwen": "editshare-qwen", "diffusion_crop_jpeg_regenshare": "regenshare",
         "diffusion_gnoise_gblur_sharpen_jpeg_scrub": "scrub"}
RERENDER = {**{f"{a}_{s}": [(a, s)] for a, ss in LA.LEVEL1_CORE.items() for s in ss}, **LA.LEVEL2_CHAINS}

ENTRIES = [
    dict(image_id="flux1_scenery_0616_gs", family="in-generation", method="gaussian_shading",
         method_label="Gaussian Shading", generator="flux1", stem="scenery_0616", category="scenery"),
    dict(image_id="flux1_object_0440_t2smark", family="in-generation", method="t2smark",
         method_label="T2SMark", generator="flux1", stem="object_0440", category="object"),
    dict(image_id="flux1_scenery_0616_videoseal", family="post-hoc", method="videoseal",
         method_label="VideoSeal", generator="flux1", stem="scenery_0616", category="scenery"),
    dict(image_id="flux1_object_0440_videoseal", family="post-hoc", method="videoseal",
         method_label="VideoSeal", generator="flux1", stem="object_0440", category="object"),
]
GEN_LABEL = {"flux1": "FLUX.1-dev", "sdxl": "SDXL", "sd21": "SD2.1"}
SUBCLASS_LABEL = {"landscape": "landscape", "food_drink": "food and drink", "portrait_single": "single person's portrait",
                  "people_group": "group of people", "sports_recreation": "sports scene", "indoor_scene": "indoor scene",
                  "vehicle": "vehicle", "object": "object"}


def grep_lines(path, needle):
    """Fast substring prefilter with grep -F, then JSON-parse."""
    p = subprocess.run(["grep", "-F", needle, str(path)], capture_output=True, text=True)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]


def save_webp(arr_bgr_or_pil, name):
    im = arr_bgr_or_pil if isinstance(arr_bgr_or_pil, Image.Image) else \
        Image.fromarray(cv2.cvtColor(arr_bgr_or_pil, cv2.COLOR_BGR2RGB))
    im = im.convert("RGB")
    h = round(im.height * WIDTH / im.width)
    im.resize((WIDTH, h), Image.LANCZOS).save(OUT / name, "WEBP", quality=QUALITY, method=6)
    return name


def bit_acc(gt, dc):
    gt, dc = gt or "", dc or ""
    if not gt:
        return None
    n = min(len(gt), len(dc))
    return round(sum(gt[i] == dc[i] for i in range(n)) / len(gt), 4)


def thresholds(path, method, mode, n_eval, far="0.01"):
    for r in csv.DictReader(open(path)):
        if r["method"] == method and r["mode"] == mode and r["n_eval"] == n_eval and r["far"] == far:
            return float(r["tau"])
    raise KeyError((path, method))


def qsr_rows(path, method, image):
    out = defaultdict(list)
    needle = f"{method},{image},"
    p = subprocess.run(["grep", "-F", needle, str(path)], capture_output=True, text=True)
    hdr = open(path).readline().strip().split(",")
    for row in csv.DictReader(p.stdout.splitlines(), fieldnames=hdr):
        if row["method"] != method or row["image"] != image:
            continue
        out[(row["stage"], row["attack"], row["severity"])].append(row)
    return out


def qsr_summary(rows, msg):
    if not rows:
        return None
    qtext = {q["qid"]: q["q"] for q in msg["qa"]}
    c = [int(r["correct"]) for r in rows]
    b = [int(r["blank_correct"]) for r in rows]
    return dict(qsr_corrected=round(float(np.mean(c)) - float(np.mean(b)), 4),
                n_questions=len(rows),
                answers=[dict(qid=r["qid"], type=r["type"], question=qtext.get(r["qid"]),
                              gold=r["gold"], pred=r["pred"], correct=bool(int(r["correct"])))
                         for r in rows])


def edit_instruction(canonical):
    p = INGEN / "external/edit_manifest_qwen_image_edit_fast_pass1.jsonl"
    for r in grep_lines(p, f'"canonical": "{canonical}"'):
        return dict(op=r["op"], entity=r["entity"], prompt=r["prompt"], vlm=r["vlm"], editor=r["model_repo"])
    return None


master = {}
for r in csv.DictReader(open(INGEN / "metadata/ingen_master_index.csv")):
    master[r["image_id"]] = r
prompts = {}
for e in ENTRIES:
    cid = f"{e['generator']}_{e['stem']}"
    if cid not in prompts:
        rows = grep_lines(INGEN / "metadata/ingen_master.jsonl", f'"image_id": "{cid}"')
        prompts[cid] = rows[0]

gallery = dict(
    note=("Synthetic images only. In-generation attacked images are the evaluated files; post-hoc C1/C3 "
          "attacked images are re-rendered with the benchmark's seeded attack code (bit-identical check passed); "
          "post-hoc C2/C4 images are not on disk (file null) but their per-image metrics are real. "
          "Unwatermarked = same prompt and seed without a watermark; for in-generation methods it is a "
          "different sample, so no residual is given."),
    width=WIDTH, images=[])

for e in ENTRIES:
    cid = f"{e['generator']}_{e['stem']}"
    meta = prompts[cid]
    m, stem, gen, cat = e["method"], e["stem"], e["generator"], e["category"]
    clean_path = R / meta["clean_file"]["path"]
    ent = dict(image_id=e["image_id"], cohort_id=cid, family=e["family"], method=m,
               method_label=e["method_label"], generator=GEN_LABEL[gen],
               subclass=SUBCLASS_LABEL.get(meta["class"], meta["class"]), prompt=meta["prompt"], seed=meta["seed"])
    conds = []

    if e["family"] == "in-generation":
        wm_path = R / meta["methods"][m]["file"]["path"]
        img_key = f"{gen}/{stem}.png"
        recs = [r for r in grep_lines(INGEN / "metrics/records_ingen_v2.jsonl", f'"image": "{img_key}"')
                if r["method"] == m]
        srecs = [r for r in grep_lines(INGEN / "metrics/records_semantic_ingen.jsonl", f'"image": "{img_key}"')
                 if r["method"] == m]
        tau = thresholds(INGEN / "metrics/eval_v2/thresholds.csv", m, "score", "")
        cb = json.loads((INGEN / "metrics/codebook_semantic_ingen.json").read_text())["semantic"]
        msg_id = cb["methods"][m]["messages"][f"{gen}/{stem}"]
        chars = cb["methods"][m]["chars"]
        qsr = qsr_rows(INGEN / "metrics/qsr_out/qsr_qa.csv", m, img_key)
        score_of = {(r["stage"], r["attack"] or "", str(r["severity"] or "")): r for r in recs}
        sem_of = {(r["stage"], r["attack"] or "", str(r["severity"] or "")): r for r in srecs}

        def metrics(stage, attack, sev):
            k = (stage, attack, sev)
            s, sr = score_of.get(k), sem_of.get(k)
            d = dict(asi=(s or sr or {}).get("asi"),
                     score=None if s is None else s.get("score"), tau=tau,
                     detected=None if s is None or s.get("score") is None else bool(s["score"] > tau))
            if sr is not None:
                d["bit_acc"] = bit_acc(sr.get("gt_bits"), sr.get("dec_bits"))
                d["decoded_text"] = decode_bits(sr["dec_bits"], "packed5", chars) if sr.get("dec_bits") else ""
            else:
                d["bit_acc"], d["decoded_text"] = None, None
            d["qsr"] = qsr_summary(qsr.get((stage, attack, sev), []), MSGS[msg_id])
            return d
    else:
        wm_path = SEM / "out_img_flux1_eval999" / m / f"{stem}.png"
        img_key = f"{stem}.png"
        recs = [r for r in grep_lines(SEM / "out_img_flux1/results/records.jsonl", f'"image": "{img_key}"')
                if r["method"] == m]
        cbj = json.loads((SEM / "out_img_flux1/results/codebook.json").read_text())
        C = np.stack([np.array([int(c) for c in cbj["codebooks"][m][str(i)]], np.float32) for i in range(100)])
        tau = thresholds(LEV / "metrics_syn_flux1_semantic/thresholds.csv", m, "codebook", "100")
        sem = cbj["semantic"]["methods"][m]
        chars = sem["chars"]
        qsr = qsr_rows(LEV / "qsr_syn_flux1_semantic/qsr_qa.csv", m, img_key)
        rec_of = {(r["stage"], r["attack"] or "", str(r["severity"] or "")): r for r in recs}
        ident = next(r["identity"] for r in recs if r["stage"] == "watermarked")
        msg_id = sem["messages"][str(ident)]

        def metrics(stage, attack, sev):
            r = rec_of.get((stage, attack, sev))
            if r is None:
                return dict(asi=None, score=None, tau=tau, detected=None, bit_acc=None, decoded_text=None,
                            qsr=None, identity_pred=None)
            dc = r.get("dec_bits") or ""
            D = np.zeros(C.shape[1], np.float32); V = np.zeros(C.shape[1], np.float32)
            n = min(len(dc), C.shape[1])
            D[:n] = [int(c) for c in dc[:n]]; V[:n] = 1.0
            S = (C @ D + (1 - C) @ ((1 - D) * V)) / C.shape[1]
            s1, pred = float(S.max()), int(S.argmax())
            return dict(asi=r.get("asi"), score=round(s1, 6), tau=tau, detected=bool(s1 > tau),
                        identity_correct=bool(pred == ident),
                        bit_acc=bit_acc(r.get("gt_bits"), dc),
                        decoded_text=decode_bits(dc, "packed5", chars) if dc else "",
                        qsr=qsr_summary(qsr.get((stage, attack, sev), []), MSGS[msg_id]))

    ent["payload_text"] = MSGS[msg_id]["text"]
    ent["msg_id"] = msg_id
    ent["payload_bits"] = 256
    # base images
    clean = cv2.imread(str(clean_path), cv2.IMREAD_COLOR)
    wm = cv2.imread(str(wm_path), cv2.IMREAD_COLOR)
    base = e["image_id"]
    ent["unwatermarked"] = save_webp(clean, f"{base}_unwatermarked.webp")
    ent["watermarked"] = save_webp(wm, f"{base}_watermarked.webp")
    ent["source_paths"] = dict(unwatermarked=str(clean_path), watermarked=str(wm_path))
    if e["family"] == "post-hoc" and clean.shape == wm.shape:
        diff = np.abs(wm.astype(np.int16) - clean.astype(np.int16)).astype(np.float32)
        ent["psnr_db"] = round(float(10 * np.log10(255.0 ** 2 / np.mean(diff ** 2))), 2)
        amp = np.clip(diff * 10, 0, 255).astype(np.uint8)
        ent["residual"] = save_webp(amp, f"{base}_residual.webp")
    else:
        ent["residual"] = None
    wmm = metrics("watermarked", "", "")
    ent["watermarked_metrics"] = wmm
    ed = edit_instruction(cid)

    for cid_, catg, label, att, sev, lvl in CONDITIONS:
        d = metrics("attacked", att, sev)
        fname, origin = None, None
        if e["family"] == "in-generation":
            p = INGEN / "attacked_wm" / lvl / cid_ / "in_generation" / gen / m / f"{stem}.png"
            if p.exists():
                fname = save_webp(cv2.imread(str(p), cv2.IMREAD_COLOR), f"{base}_{SHORT[cid_]}.webp")
                origin = dict(kind="evaluated file", path=str(p))
        elif cid_ in RERENDER:
            img = LA.apply_chain(wm, stem, cid_, RERENDER[cid_])
            fname = save_webp(img, f"{base}_{SHORT[cid_]}.webp")
            origin = dict(kind="re-rendered with attacks/leveled_attacks.py apply_chain (seeded, bit-identical check)",
                          chain=[list(s) for s in RERENDER[cid_]])
        else:
            origin = dict(kind="not on disk (archived); metrics only")
        c = dict(id=cid_, category=catg, label=label, file=fname, **d, image_origin=origin)
        if cid_ in ("edit_qwen", "edit_resize_jpeg_editshare_qwen") and ed:
            c["edit_instruction"] = ed
        conds.append(c)
    ent["conditions"] = conds
    gallery["images"].append(ent)
    print(base, "done:", sum(1 for c in conds if c["file"]), "images,",
          sum(1 for c in conds if c["asi"] is not None), "with asi")

(OUT / "gallery.json").write_text(json.dumps(gallery, indent=1))
print("wrote", OUT / "gallery.json")
