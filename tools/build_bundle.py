#!/usr/bin/env python3
"""Bundle the site data into js/data.js (window.SEAL = {...}).

Reads the JSON files written by tools/build_data.py (data/*.json) and keeps only
what the page draws. Loading the data as a script (not fetch) lets the page work
from file:// and from any static host. Run after build_data.py:

    python3 tools/build_bundle.py
"""
import json
import os

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(SITE, "data")


def load(name):
    with open(os.path.join(D, name)) as f:
        return json.load(f)


def r3(x, nd=4):
    return None if x is None else round(float(x), nd)


lb = load("leaderboards.json")
heat = load("heatmap.json")
curves = load("curves.json")
scatter = load("scatter.json")
attacks = load("attacks.json")
methods = load("methods.json")

# ---- method links: verified 2026-10-14 (arXiv abs titles == bib titles; GitHub API 200) ----
LINKS = {
    "cin": ("https://arxiv.org/abs/2212.12678", "https://github.com/rmpku/CIN", "ACM MM 2022"),
    "pimog": ("https://doi.org/10.1145/3503161.3548049",
              "https://github.com/FangHanNUS/PIMoG-An-Effective-Screen-shooting-Noise-Layer-Simulation-for-Deep-Learning-Based-Watermarking-Netw",
              "ACM MM 2022"),
    "wam": ("https://arxiv.org/abs/2411.07231", "https://github.com/facebookresearch/watermark-anything", "ICLR 2025"),
    "trustmark": ("https://arxiv.org/abs/2311.18297", "https://github.com/adobe/trustmark", "arXiv 2023"),
    "editguard": ("https://arxiv.org/abs/2312.08883", "https://github.com/xuanyuzhang21/EditGuard", "CVPR 2024"),
    "vine": ("https://arxiv.org/abs/2410.18775", "https://github.com/Shilin-LU/VINE", "ICLR 2025"),
    "invismark": ("https://arxiv.org/abs/2411.07795", "https://github.com/microsoft/InvisMark", "WACV 2025"),
    "omniguard": ("https://arxiv.org/abs/2412.01615", "https://github.com/xuanyuzhang21/OmniGuard", "CVPR 2025"),
    "mbrs": ("https://arxiv.org/abs/2108.08211", "https://github.com/jzyustc/MBRS", "ACM MM 2021"),
    "videoseal": ("https://arxiv.org/abs/2412.09492", "https://github.com/facebookresearch/videoseal", "arXiv 2024"),
    "pixelseal": ("https://arxiv.org/abs/2512.16874", "https://github.com/facebookresearch/videoseal", "arXiv 2025"),
    "ring_id": ("https://arxiv.org/abs/2404.14055", "https://github.com/showlab/RingID", "ECCV 2024"),
    "gaussian_shading": ("https://arxiv.org/abs/2404.04956", "https://github.com/bsmhmmlf/Gaussian-Shading", "CVPR 2024"),
    "t2smark": ("https://doi.org/10.52202/085713-3958", "https://github.com/0xD009/T2SMark", "NeurIPS 2025"),
    "prc": ("https://arxiv.org/abs/2410.07369", "https://github.com/XuandongZhao/PRC-Watermark", "ICLR 2025"),
}

out_methods = []
for m in methods["methods"]:
    paper, code, venue = LINKS[m["key"]]
    out_methods.append({
        "key": m["key"], "name": m["name"], "family": m["family"],
        "bits": m.get("payload_bits"), "payload": m.get("payload_text"),
        "message": m.get("message_type"), "cls": m.get("message_class"),
        "generators": m.get("generators"), "paper": paper, "code": code, "venue": venue,
    })

# ---- tables: keep text cells, numeric values, bold flags ----
KEEP = ["tab_crossfamily", "tab_tier3_main", "tab_tier3_rest", "tab_main3", "tab_ingen", "tab_levels",
        "tab_comparison", "tab_attackgrid", "tab_chains", "tab_readers_method", "tab_generator"]
def fix_caption(tid, cap):
    for old, new in CAPTION_FIX.get(tid, []):
        cap = cap.replace(old, new)
    assert "sentence-carrying" not in cap and "tier3rest" not in cap, tid
    return cap


# caption corrections shown on the site (the paper text is unchanged)
CAPTION_FIX = {
    "tab_levels": [("TPR@1%FPR is reported for both watermark families, post-hoc methods in identity mode and in-generation methods on their sentence-carrying images; ",
                    "TPR@1%FPR is reported for both watermark families, post-hoc methods in identity mode and all four in-generation methods; ")],
    "tab_tier3_main": [(" Table~\\ref{tab:tier3rest}.", ""), (" Table~\\ref{tab:tier3rest}", "")],
}
tables = {}
for t in lb["tables"]:
    if t["id"] not in KEEP:
        continue
    rows = []
    for r in t["rows"]:
        rows.append({
            "g": r.get("group"), "label": r.get("label"), "method": r.get("method_key"),
            "family": r.get("family"),
            "cells": [c["text"] for c in r["cells"]],
            "vals": [c.get("value") for c in r["cells"]],
            "bold": [bool(c.get("bold")) for c in r["cells"]],
        })
    tables[t["id"]] = {
        "num": t.get("paper_table_number"), "part": t.get("part"),
        "caption": fix_caption(t["id"], t.get("caption_site") or t.get("caption")),
        "columns": [{"label": c.get("label"), "kind": c.get("kind"), "unit": c.get("unit")} for c in t["columns"]],
        "colgroups": t.get("column_groups", []),
        "groups": [g.get("label") for g in t["row_groups"]],
        "rows": rows,
    }

# ---- heat map ----
hm = {
    "conditions": heat["conditions"],
    "methods": heat["methods"],
    "names": heat["method_names"],
    "categories": heat["category_names"],
    "grids": {},
    "asi": {k: [r3(v) for v in vals] for k, vals in heat["mean_asi"]["values"].items()},
    "fig": heat["paper_figure"].get("number"),
}
for cat, g in heat["grids"].items():
    hm["grids"][cat] = {
        "post_hoc": {m: [r3(v, 2) for v in vals] for m, vals in g["post_hoc"].items()},
        "in_generation": {m: [r3(v, 2) for v in vals] for m, vals in g.get("in_generation", {}).items()},
    }

# ---- curves (single attack types only; chains are not drawn as curves) ----
cv = {"types": curves["attack_types"], "budget": curves["asi_budget"], "sets": [],
      "fig": curves["paper_figure"].get("number")}
WANT = ["manipulated_post_hoc", "real_post_hoc", "synthetic_post_hoc_matched", "synthetic_in_generation"]
for s in curves["sets"]:
    if s["id"] not in WANT:
        continue
    cv["sets"].append({
        "id": s["id"], "label": s["label"], "family": s["family"], "category": s["category"],
        "methods": s["methods"], "in_paper": s.get("in_paper", False),
        "curves": {m: {fam: [[r3(p[0]), r3(p[1], 2), p[2]] for p in pts] for fam, pts in c.items()}
                   for m, c in s["curves"].items()},
    })
cv["sets"].sort(key=lambda s: WANT.index(s["id"]))

# ---- scatter ----
sc = {"region": scatter["shaded_region"], "fig": scatter["paper_figure"].get("number"), "panels": []}
for p in scatter["panels"]:
    sc["panels"].append({
        "id": p["id"], "label": p["label"], "family": p["family"], "methods": p["methods"],
        "n": p["n_points"], "n_region": p["n_in_shaded_region"],
        "pts": [[pt["method"], pt["condition"], pt["category"], r3(pt["asi"]), r3(pt["bit_acc"]), r3(pt["qsr"]),
                 r3(pt.get("msg_rec"))] for pt in p["points"]],
    })

# ---- attacks ----
at = {"categories": attacks["categories"], "conditions": attacks["conditions"]}

# ---- attack gallery (assets/gallery/gallery.json; source paths dropped) ----
gal = []
gpath = os.path.join(SITE, "assets", "gallery", "gallery.json")
if os.path.exists(gpath):
    with open(gpath) as f:
        g = json.load(f)
    for e in (g if isinstance(g, list) else g.get("images", [])):
        if e.get("family") != "in-generation":
            continue  # post-hoc entries left out: their C2/C4 attacked images are not available
        e = {k: v for k, v in e.items() if k not in ("source_paths",)}
        for c in e.get("conditions", []):
            c.pop("source", None); c.pop("source_path", None); c.pop("image_source", None); c.pop("image_origin", None)
        gal.append(e)

bundle = {"gallery": gal, "methods": out_methods, "tables": tables, "heatmap": hm, "curves": cv, "scatter": sc,
          "attacks": at, "encoding": methods["message_encoding"],
          "built_from": {"paper_commit": lb["_meta"]["paper"]["commit"][:7]}}

js = "/* generated by tools/build_bundle.py from data/*.json; do not edit */\nwindow.SEAL = " + \
     json.dumps(bundle, separators=(",", ":"), ensure_ascii=False) + ";\n"
os.makedirs(os.path.join(SITE, "js"), exist_ok=True)
with open(os.path.join(SITE, "js", "data.js"), "w") as f:
    f.write(js)
print("js/data.js", len(js) // 1024, "KB; tables:", sorted(tables), "; curve sets:", [s["id"] for s in cv["sets"]])
