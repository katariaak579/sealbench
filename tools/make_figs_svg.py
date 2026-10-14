"""Paper figures from the CURRENT metric CSVs (docs/20 s4). Outputs PDF to iclr_draft/iclr2027/fig/."""
# ADAPTED COPY of iclr_draft/scripts/make_figs.py for the website: writes SVG into assets/fig/svg (never run the original in place).
import csv, os, collections
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import os
ROOT = os.environ.get("SEALBENCH_REPO", "../iclr_dataset")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/fig/svg")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({"font.family": "sans-serif", "font.size": 7, "axes.labelsize": 7,
    "axes.titlesize": 7.5, "xtick.labelsize": 6, "ytick.labelsize": 6, "legend.fontsize": 6.5,
    "axes.edgecolor": "#c3c2b7", "axes.linewidth": 0.6, "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.labelcolor": "#0b0b0b", "grid.color": "#e1e0d9", "grid.linewidth": 0.5, "pdf.fonttype": 42})

# fixed method order (by payload bits, as in every table) and fixed colours
METHODS = ["cin", "pimog", "wam", "trustmark", "editguard", "vine", "invismark", "omniguard", "mbrs", "videoseal", "pixelseal"]
NAME = {"cin": "CIN", "pimog": "PIMoG", "wam": "WAM", "trustmark": "TrustMark", "editguard": "EditGuard", "vine": "VINE",
        "invismark": "InvisMark", "omniguard": "OmniGuard", "mbrs": "MBRS", "videoseal": "VideoSeal", "pixelseal": "PixelSeal",
        "ring_id": "RingID", "gaussian_shading": "Gauss. Shading", "t2smark": "T2SMark", "prc": "PRC"}
INGEN = ["ring_id", "gaussian_shading", "t2smark", "prc"]   # Stable Signature removed from the paper (2026-09-23)
# 8 validated categorical hues (palette.md), then 3 extra hues; secondary encoding = line style by capacity class
HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948", "#0891b2", "#7c3aed", "#a16207"]
COLOR = dict(zip(METHODS, HUES))
STYLE = {m: (":" if m in ("cin", "pimog", "wam", "trustmark") else "--" if m in ("editguard", "vine", "invismark", "omniguard") else "-") for m in METHODS}

FAM_ORDER = [("brightness", "brightness"), ("contrast", "contrast"), ("hue", "hue"), ("overlay", "overlay"), ("gnoise", "noise"),
             ("gblur", "blur"), ("resize", "resize"), ("jpeg", "JPEG"), ("crop", "crop"), ("rotation", "rotation"),
             ("edit", "edit"), ("vae", "VAE regen."), ("diffusion_modern", "diffusion regen."), ("unmarker", "UnMarker")]

# ---------------- Figure 2: accuracy vs ASI per family, fake category ----------------
# TPR@1%FPR against ASI (the curve AURSC integrates): x from robust_curves (ASI is a property of the image), y from detection.csv
_fk = f"{ROOT}/runs/2026-08-02_leveled-eval/metrics_fake_identity"
rc = list(csv.DictReader(open(f"{_fk}/robust_curves.csv")))
_det = [r for r in csv.DictReader(open(f"{_fk}/detection.csv")) if r["far"] == "0.01" and r["n_eval"] == "100"]
_tpr = {(r["method"], r["attack"], r["severity"] or ""): float(r["tpr"]) for r in _det}
_anchor = {r["method"]: float(r["tpr"]) for r in _det if r["attack"] == "none"}
fig, axes = plt.subplots(2, 7, figsize=(7.0, 2.75), sharey=True)
for ax, (fam, title) in zip(axes.flat, FAM_ORDER):
    for m in METHODS:
        seen = {}
        for r in rc:
            if r["method"] == m and r["attack"] == fam and r["is_chain"] == "False" and r["severity"] != "clean":
                seen.setdefault(r["severity"], float(r["x"]))
        pts = [(0.0, _anchor[m])] + [(x, _tpr[(m, fam, sv)]) for sv, x in seen.items() if (m, fam, sv) in _tpr]
        pts.sort()
        if not pts:
            continue
        xs, ys = zip(*pts)
        ax.plot(xs, [100 * y for y in ys], STYLE[m], color=COLOR[m], lw=1.0, marker="o", ms=1.8, mew=0)
    ax.axvline(0.2, color="#898781", lw=0.6, ls="-", alpha=0.7)
    ax.set_title(title, pad=2)
    ax.set_xlim(0, 0.72); ax.set_ylim(-3, 103)
    ax.set_xticks([0, 0.2, 0.4, 0.6]); ax.set_xticklabels(["0", ".2", ".4", ".6"])
    ax.grid(True, axis="y")
    ax.tick_params(length=2, pad=1)
for ax in axes[:, 0]:
    ax.set_ylabel("TPR@1%FPR (%)")
for ax in axes[1, :]:
    ax.set_xlabel("ASI", labelpad=1)
handles = [Line2D([0], [0], color=COLOR[m], ls=STYLE[m], lw=1.2, label=NAME[m]) for m in METHODS]
fig.legend(handles=handles, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, 0.0), handlelength=2.4, columnspacing=1.2, handletextpad=0.5)
fig.subplots_adjust(left=0.06, right=0.995, top=0.92, bottom=0.30, wspace=0.12, hspace=0.45)
fig.savefig(f"{OUT}/fig2_curves.svg")
plt.close(fig)

# ---------------- Figure 3: heat map method x condition, synthetic category, both families ----------------
grid = list(csv.DictReader(open(f"{ROOT}/runs/2026-09-03_results/csv/T4_full_grid.csv")))
LEVELS = ["L1", "L2", "L3", "L4"]
SHORT = {"brightness": "bright", "contrast": "contrast", "crop": "crop", "gblur": "blur", "gnoise": "noise", "hue": "hue", "jpeg": "JPEG",
         "overlay": "overlay", "resize": "resize", "rotation": "rotate", "vae": "VAE", "diffusion_modern": "diffusion", "edit": "edit", "unmarker": "UnMarker",
         "resize_jpeg_messenger": "messenger", "brightness_contrast_filter": "filter", "crop_resize_jpeg_social": "social",
         "resize_jpeg_resize_jpeg_reshare": "reshare", "rotation_crop_resize_jpeg_straighten": "straighten",
         "brightness_saturation_sharpen_jpeg_filterpost": "filterpost", "gnoise_gblur_jpeg_noisedenoise": "noisedenoise",
         "overlay_resize_jpeg_meme": "meme", "edit_resize_jpeg_editshare_flux2": "editshare-F", "edit_resize_jpeg_editshare_qwen": "editshare-Q",
         "vae_jpeg_vaeregen": "vaeregen", "diffusion_crop_jpeg_regenshare": "regenshare", "diffusion_gnoise_gblur_sharpen_jpeg_scrub": "scrub",
         "unmarker_resize_jpeg_unmarkshare": "unmarkshare"}
SEV = {"str0_1": "0.1", "str0_2": "0.2", "str0_3": "0.3", "flux2_klein_fast": "F", "qwen_image_edit_fast": "Q", "q1": "q1", "q3": "q3", "default": "", "chain": ""}
L1_ORDER = ["brightness", "contrast", "hue", "overlay", "gnoise", "gblur", "resize", "jpeg", "crop", "rotation"]
def sevkey(a, s):
    try: return float(s)
    except: return {"q1": 1, "q3": 3, "str0_1": 1, "str0_2": 2, "str0_3": 3, "flux2_klein_fast": 1, "qwen_image_edit_fast": 2}.get(s, 0)
conds = collections.OrderedDict()
for lv in LEVELS:
    cs = sorted({(r["attack"], r["severity"]) for r in grid if r["level"] == lv and r["category"] == "synthetic"},
                key=lambda t: ((L1_ORDER.index(t[0]) if t[0] in L1_ORDER else 99), sevkey(*t)))
    if lv == "L2":
        order = ["edit", "vae", "diffusion_modern", "unmarker"]
        cs.sort(key=lambda t: (order.index(t[0]), sevkey(*t)))
    if lv == "L3":
        order = ["brightness_contrast_filter", "resize_jpeg_messenger", "brightness_saturation_sharpen_jpeg_filterpost", "resize_jpeg_resize_jpeg_reshare",
                 "gnoise_gblur_jpeg_noisedenoise", "overlay_resize_jpeg_meme", "crop_resize_jpeg_social", "rotation_crop_resize_jpeg_straighten"]
        cs.sort(key=lambda t: order.index(t[0]))
    if lv == "L4":
        order = ["edit_resize_jpeg_editshare_flux2", "edit_resize_jpeg_editshare_qwen", "vae_jpeg_vaeregen", "diffusion_gnoise_gblur_sharpen_jpeg_scrub",
                 "diffusion_crop_jpeg_regenshare", "unmarker_resize_jpeg_unmarkshare"]
        cs.sort(key=lambda t: order.index(t[0]))
    conds[lv] = cs
allc = [(lv, a, s) for lv in LEVELS for (a, s) in conds[lv]]
def val(cat, fam, m, a, s):
    rr = [r for r in grid if r["category"] == cat and r["family"] == fam and r["method"] == m and r["attack"] == a and r["severity"] == s]
    return 100 * float(rr[0]["tpr_far01"]) if rr and rr[0]["tpr_far01"] else np.nan   # TPR@1%FPR for BOTH families
rows_ph = [[val("synthetic", "post-hoc", m, a, s) for (_, a, s) in allc] for m in METHODS]
rows_ig = [[val("synthetic", "in-generation", m, a, s) for (_, a, s) in allc] for m in INGEN]
M = np.array(rows_ph + rows_ig, dtype=float)
cmap = LinearSegmentedColormap.from_list("seqblue", ["#ffffff", "#cde2fb", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"])
# Transposed layout (2026-09-21): one row per attack condition, one column per method, on a full appendix page,
# so that every condition label is set horizontally at a readable size.
MT = M.T; ncols = len(METHODS) + len(INGEN)
fig = plt.figure(figsize=(7.0, 8.8))
ax = fig.add_axes([0.20, 0.035, 0.69, 0.865])
im = ax.imshow(MT, cmap=cmap, vmin=0, vmax=100, aspect="auto", interpolation="nearest")
ax.set_xticks(range(ncols))
ax.set_xticklabels([NAME[m].replace("\\ ", " ").replace("\\", "") for m in METHODS] + [NAME[m].replace("\\ ", " ").replace("\\", "") for m in INGEN], rotation=55, ha="left", fontsize=7.5)
ax.xaxis.tick_top()
labels = []
for (lv, a, s) in allc:
    sv = SEV.get(s, s)
    labels.append(f"{SHORT[a]} {sv}".strip())
ax.set_yticks(range(len(allc))); ax.set_yticklabels(labels, fontsize=7.5)
ax.tick_params(length=0, pad=2)
y = -0.5
for lv in LEVELS:
    n = len(conds[lv]); y += n
    if lv != "L4": ax.axhline(y, color="#0b0b0b", lw=0.8)
    fig.text(0.012, 0.035 + 0.865 * (1 - (y - n / 2 + 0.5) / len(allc)),
             {"L1": "Attack category 1: single transformations", "L2": "Attack category 2:\nediting, removal", "L3": "Attack category 3:\nchains", "L4": "Attack\ncategory 4:\nremoval + chain"}[lv],
             rotation=90, ha="left", va="center", fontsize=7.5, color="#52514e", linespacing=1.1, multialignment="center")
ax.axvline(len(METHODS) - 0.5, color="#0b0b0b", lw=1.0)
fig.text(0.20 + 0.69 * (len(METHODS) / 2 / ncols), 0.012, "post-hoc", ha="center", va="bottom", fontsize=8, color="#52514e")
fig.text(0.20 + 0.69 * ((len(METHODS) + len(INGEN) / 2) / ncols), 0.012, "in-generation", ha="center", va="bottom", fontsize=8, color="#52514e")
for i in range(MT.shape[0]):
    for j in range(MT.shape[1]):
        if MT[i, j] < 50:
            ax.text(j, i, "·", ha="center", va="center", fontsize=8, color="#898781")
cax = fig.add_axes([0.905, 0.035, 0.014, 0.865])
cb = fig.colorbar(im, cax=cax); cb.set_ticks([0, 50, 100]); cb.ax.tick_params(length=2, labelsize=7)
cb.set_label("TPR@1%FPR (%)", fontsize=7.5, labelpad=2)
ax.set_ylim(len(allc) - 0.5, -0.5)
fig.savefig(f"{OUT}/fig3_heatmap.svg", bbox_inches="tight", pad_inches=0.02)
plt.close(fig)

# ---------------- Figure 4: bits vs meaning per condition ----------------
def load_sem(path):
    return [r for r in csv.DictReader(open(path)) if r["attack"] not in ("none", "") and r["bit_acc"] and r["qsr_corrected"]]
# post-hoc synthetic = the 4 generator arms pooled per (method, attack, severity), frame-weighted exactly as make_tables.py T3ARMS
SYN_ARMS = [("syn_sd21", 265), ("syn_sdxl", 263), ("syn_flux1", 268), ("syn_newgen", 797)]
_pool = collections.defaultdict(lambda: [0.0, 0.0, 0.0])   # key -> [sum w*bits, sum w*qsr, sum w]
for arm, w in SYN_ARMS:
    for r in load_sem(f"{ROOT}/runs/2026-08-02_leveled-eval/metrics_semantic_{arm}_semantic/semantic_conditions.csv"):
        k = (r["method"], r["attack"], r["severity"]); _pool[k][0] += w * float(r["bit_acc"]); _pool[k][1] += w * float(r["qsr_corrected"]); _pool[k][2] += w
synthetic = [{"method": k[0], "attack": k[1], "severity": k[2], "bit_acc": v[0] / v[2], "qsr_corrected": v[1] / v[2]} for k, v in _pool.items()]
# Family comparison (2026-09-18): post-hoc panel on the matched 1,193-stem cohort (one arm; scripts/matched_cohort/semantic_matched.py)
synthetic = load_sem(f"{ROOT}/runs/2026-09-18_matched-cohort/semantic/semantic_conditions.csv")
ingen = load_sem(f"{ROOT}/runs/2026-08-17_ingen-l14/metrics/semantic/semantic_conditions.csv")
fig, axes = plt.subplots(1, 2, figsize=(5.5, 1.6), sharey=True)   # full text width (5.5 in), same height on the page as the old 0.62-width include
for ax, data, title, col in [(axes[0], synthetic, "post-hoc (7 methods)", "#2a78d6"), (axes[1], ingen, "in-generation (3 methods)", "#eb6834")]:
    ax.axvspan(0.9, 1.0, ymin=0, ymax=0.5, color="#f3f3ef", zorder=0)
    xs = [float(r["bit_acc"]) for r in data]; ys = [float(r["qsr_corrected"]) for r in data]
    ax.scatter(xs, ys, s=9, color=col, alpha=0.55, linewidths=0, zorder=2)
    ax.plot([0.5, 1.0], [0, 1.0], color="#898781", lw=0.6, ls="--", zorder=1)
    n_diss = sum(1 for x, y in zip(xs, ys) if x >= 0.9 and y <= 0.5)
    ax.text(0.515, 0.93, f"shaded: bit acc. $\\geq$ 0.9 and QSR $\\leq$ 0.5\n{n_diss} of {len(xs)} conditions", fontsize=6, color="#52514e", va="top")
    ax.set_xlim(0.5, 1.0); ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("bit accuracy"); ax.set_title(title, pad=2)
    ax.grid(True); ax.tick_params(length=2, pad=1)
axes[0].set_ylabel("QSR")
fig.subplots_adjust(left=0.075, right=0.995, top=0.90, bottom=0.19, wspace=0.07)
fig.savefig(f"{OUT}/fig4_dissociation.svg")
plt.close(fig)
print("figures written:", sorted(f for f in os.listdir(OUT) if f.startswith("fig") and f.endswith(".svg")))
