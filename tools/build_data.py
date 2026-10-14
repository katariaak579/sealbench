#!/usr/bin/env python3
"""Build the data layer of the SEALBench website (data/*.json).

Two read-only sources:
  PAPER  the Overleaf checkout of the paper: main tex, generated tables/*.tex, bib
  REPO   the research repository with the metric CSVs that feed the paper's figures

Standard library only. The script writes only to <site>/data/ and <site>/tools/build_checks.json.
Source roots come from $SEALBENCH_PAPER / $SEALBENCH_REPO or tools/local_paths.json. That file is kept
out of git because the absolute paths identify the authors while the paper is under double-blind
review; the JSON output cites sources only as "paper:<relative path>" and "repo:<relative path>".

What each output reproduces:
  leaderboards.json  every results table of the paper, parsed from the paper's own table files
  heatmap.json       the per-condition heat map (make_figs.py, Figure "fig:heatmap") + manipulated/real grids
  curves.json        TPR@1%FPR vs ASI per attack type (make_figs.py, Figure "fig:curves") + further sets
  scatter.json       bit accuracy vs QSR per method-condition pair (make_figs.py, Figure "fig:dissociation")
  attacks.json       the 52 attack conditions (tables tab_attackgrid / tab_chains)
  methods.json       the 15 watermarking methods (inline table tab:methods + bib)
  stats.json         dataset and evaluation counts, each with the paper lines that state it

Usage: python3 tools/build_data.py
"""
import bisect, collections, csv, datetime, hashlib, json, os, re, statistics, subprocess, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(TOOLS)
OUT = os.path.join(SITE, "data")


def _roots():
    cfg = {}
    p = os.path.join(TOOLS, "local_paths.json")
    if os.path.exists(p):
        with open(p) as fh:
            cfg = json.load(fh)
    paper = os.environ.get("SEALBENCH_PAPER") or cfg.get("paper")
    repo = os.environ.get("SEALBENCH_REPO") or cfg.get("repo")
    if not paper or not repo:
        sys.exit("Set SEALBENCH_PAPER and SEALBENCH_REPO, or write tools/local_paths.json with keys 'paper' and 'repo'.")
    return paper, repo


PAPER, REPO = _roots()
MAIN_TEX = "iclr2027_conference.tex"
BIB = "iclr2027_conference.bib"


def P(rel):
    return os.path.join(PAPER, rel)


def R(rel):
    return os.path.join(REPO, rel)


def rd(rel):
    with open(R(rel), newline="") as fh:
        return list(csv.DictReader(fh))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def git_head(root):
    try:
        out = subprocess.run(["git", "-C", root, "log", "-1", "--format=%H %cI"], capture_output=True, text=True, timeout=30)
        h, d = out.stdout.strip().split(" ", 1)
        return {"commit": h, "date": d}
    except Exception:
        return None


CHECKS = []


def check(group, name, ok, detail=""):
    CHECKS.append({"group": group, "check": name, "ok": bool(ok), "detail": detail})
    return ok


def r4(x, nd=4):
    return None if x is None else round(float(x), nd)


# ----------------------------------------------------------------------------------------------
# Constants (copied from iclr_draft/scripts/make_figs.py and make_tables.py in the research repo)
# ----------------------------------------------------------------------------------------------
POSTHOC = ["cin", "pimog", "wam", "trustmark", "editguard", "vine", "invismark", "omniguard", "mbrs", "videoseal", "pixelseal"]
INGEN = ["ring_id", "gaussian_shading", "t2smark", "prc"]
SEM_PH = ["editguard", "vine", "invismark", "omniguard", "mbrs", "videoseal", "pixelseal"]
SEM_IG = ["gaussian_shading", "t2smark", "prc"]
SHORTNAME = {"cin": "CIN", "pimog": "PIMoG", "wam": "WAM", "trustmark": "TrustMark", "editguard": "EditGuard", "vine": "VINE",
             "invismark": "InvisMark", "omniguard": "OmniGuard", "mbrs": "MBRS", "videoseal": "VideoSeal", "pixelseal": "PixelSeal",
             "ring_id": "RingID", "gaussian_shading": "Gauss. Shading", "t2smark": "T2SMark", "prc": "PRC"}
FULLNAME = dict(SHORTNAME, gaussian_shading="Gaussian Shading")
NAME2KEY = {v: k for k, v in SHORTNAME.items()}
NAME2KEY["Gaussian Shading"] = "gaussian_shading"
FAMILY_OF = {**{m: "post-hoc" for m in POSTHOC}, **{m: "in-generation" for m in INGEN}}

SINGLE_TYPES = ["brightness", "contrast", "crop", "gblur", "gnoise", "hue", "jpeg", "overlay", "resize", "rotation",
                "vae", "diffusion_modern", "edit", "unmarker"]
CHAINS_C3 = ["resize_jpeg_messenger", "brightness_contrast_filter", "crop_resize_jpeg_social", "resize_jpeg_resize_jpeg_reshare",
             "rotation_crop_resize_jpeg_straighten", "brightness_saturation_sharpen_jpeg_filterpost", "gnoise_gblur_jpeg_noisedenoise",
             "overlay_resize_jpeg_meme"]
CHAINS_C4 = ["edit_resize_jpeg_editshare_flux2", "edit_resize_jpeg_editshare_qwen", "vae_jpeg_vaeregen", "diffusion_crop_jpeg_regenshare",
             "diffusion_gnoise_gblur_sharpen_jpeg_scrub", "unmarker_resize_jpeg_unmarkshare"]
ATTACK_TYPES = SINGLE_TYPES + CHAINS_C3 + CHAINS_C4
assert len(ATTACK_TYPES) == 28
C1_TYPES = SINGLE_TYPES[:10]
CAT_OF = {**{a: "C1" for a in C1_TYPES}, **{a: "C2" for a in SINGLE_TYPES[10:]},
          **{a: "C3" for a in CHAINS_C3}, **{a: "C4" for a in CHAINS_C4}}
LEVEL2CAT = {"L1": "C1", "L2": "C2", "L3": "C3", "L4": "C4"}
CHAIN_NAME = {"resize_jpeg_messenger": "messenger", "brightness_contrast_filter": "filter", "crop_resize_jpeg_social": "social",
              "resize_jpeg_resize_jpeg_reshare": "reshare", "rotation_crop_resize_jpeg_straighten": "straighten",
              "brightness_saturation_sharpen_jpeg_filterpost": "filterpost", "gnoise_gblur_jpeg_noisedenoise": "noisedenoise",
              "overlay_resize_jpeg_meme": "meme", "edit_resize_jpeg_editshare_flux2": "editshare-flux2",
              "edit_resize_jpeg_editshare_qwen": "editshare-qwen", "vae_jpeg_vaeregen": "vaeregen",
              "diffusion_crop_jpeg_regenshare": "regenshare", "diffusion_gnoise_gblur_sharpen_jpeg_scrub": "scrub",
              "unmarker_resize_jpeg_unmarkshare": "unmarkshare"}
TYPE_DISPLAY = {"brightness": "brightness", "contrast": "contrast", "hue": "hue", "overlay": "overlay", "gnoise": "Gaussian noise",
                "gblur": "Gaussian blur", "resize": "resize", "jpeg": "JPEG", "crop": "crop", "rotation": "rotation",
                "edit": "prompt-based edit", "vae": "VAE regeneration", "diffusion_modern": "diffusion regeneration", "unmarker": "UnMarker"}
TYPE_DISPLAY.update(CHAIN_NAME)
# row labels used by the paper's attack tables -> attack-type key
LABEL2TYPE = {v: k for k, v in TYPE_DISPLAY.items()}
LABEL2TYPE.update({"editshare (FLUX.2)": "edit_resize_jpeg_editshare_flux2", "editshare (Qwen)": "edit_resize_jpeg_editshare_qwen"})
CATEGORY_INFO = {
    "C1": {"name": "Single perturbation", "paper_heading": "1. Single Perturbation",
           "description": "10 image perturbations, each at three parameter settings (30 conditions)."},
    "C2": {"name": "Off-the-shelf model-based editing and removal", "paper_heading": "2. 'Off-the-shelf' Model based Attacks",
           "description": "Prompt-based editing (Qwen-Image-Edit, FLUX.2-klein), VAE regeneration (2 settings), diffusion regeneration (3 settings) and UnMarker (8 conditions)."},
    "C3": {"name": "Multiple perturbations", "paper_heading": "3. Multiple Perturbation",
           "description": "8 fixed sequences of image perturbations; the output of each step is the input to the next."},
    "C4": {"name": "Model-based attack followed by multiple perturbations",
           "paper_heading": "4. Combining 'Off-the-shelf' Model-based Attacks and Multiple Perturbations",
           "description": "6 fixed sequences that start with a model-based attack followed by further perturbations."},
}
IMAGE_CAT = {"fake": "manipulated", "real": "real", "synthetic": "synthetic"}

# make_figs.py, Figure "curves": panel order and titles
FIG_CURVE_TYPES = [("brightness", "brightness"), ("contrast", "contrast"), ("hue", "hue"), ("overlay", "overlay"), ("gnoise", "noise"),
                   ("gblur", "blur"), ("resize", "resize"), ("jpeg", "JPEG"), ("crop", "crop"), ("rotation", "rotation"),
                   ("edit", "edit"), ("vae", "VAE regen."), ("diffusion_modern", "diffusion regen."), ("unmarker", "UnMarker")]
FIG_COLOR = dict(zip(POSTHOC, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948", "#0891b2", "#7c3aed", "#a16207"]))
FIG_STYLE = {m: ("dotted" if m in ("cin", "pimog", "wam", "trustmark") else "dashed" if m in ("editguard", "vine", "invismark", "omniguard") else "solid") for m in POSTHOC}
# make_figs.py, Figure "heatmap": labels
HEAT_SHORT = {"brightness": "bright", "contrast": "contrast", "crop": "crop", "gblur": "blur", "gnoise": "noise", "hue": "hue", "jpeg": "JPEG",
              "overlay": "overlay", "resize": "resize", "rotation": "rotate", "vae": "VAE", "diffusion_modern": "diffusion", "edit": "edit", "unmarker": "UnMarker",
              "resize_jpeg_messenger": "messenger", "brightness_contrast_filter": "filter", "crop_resize_jpeg_social": "social",
              "resize_jpeg_resize_jpeg_reshare": "reshare", "rotation_crop_resize_jpeg_straighten": "straighten",
              "brightness_saturation_sharpen_jpeg_filterpost": "filterpost", "gnoise_gblur_jpeg_noisedenoise": "noisedenoise",
              "overlay_resize_jpeg_meme": "meme", "edit_resize_jpeg_editshare_flux2": "editshare-F", "edit_resize_jpeg_editshare_qwen": "editshare-Q",
              "vae_jpeg_vaeregen": "vaeregen", "diffusion_crop_jpeg_regenshare": "regenshare", "diffusion_gnoise_gblur_sharpen_jpeg_scrub": "scrub",
              "unmarker_resize_jpeg_unmarkshare": "unmarkshare"}
HEAT_SEV = {"str0_1": "0.1", "str0_2": "0.2", "str0_3": "0.3", "flux2_klein_fast": "F", "qwen_image_edit_fast": "Q", "q1": "q1", "q3": "q3", "default": "", "chain": ""}

# metric directories (docs/20_RESULTS_INVENTORY.md section 4, CURRENT)
LE = "runs/2026-08-02_leveled-eval"
DIR_FAKE_ID = f"{LE}/metrics_fake_identity"
DIR_REAL_ID = "runs/2026-08-14_posthoc-real/metrics_real_identity"
DIR_SYN_ID = f"{LE}/metrics_syn_identity"
DIR_SYN_NG = f"{LE}/metrics_syn_newgen_identity"
DIR_SYN_MATCHED = "runs/2026-09-18_matched-cohort/metrics_syn_matched_identity"
DIR_INGEN = "runs/2026-08-17_ingen-l14/metrics/eval_v2"
T4 = "runs/2026-09-03_results/csv/T4_full_grid.csv"
SEM_MATCHED = "runs/2026-09-18_matched-cohort/semantic/semantic_conditions.csv"
SEM_INGEN = "runs/2026-08-17_ingen-l14/metrics/semantic/semantic_conditions.csv"
SYN_W = {"syn_identity": 796, "syn_newgen_identity": 797}


# ----------------------------------------------------------------------------------------------
# LaTeX helpers
# ----------------------------------------------------------------------------------------------
def match_brace(s, i):
    """s[i] == '{'; return the index of the matching '}' (backslash escapes skipped)."""
    assert s[i] == "{", s[i:i + 20]
    depth, k = 0, i
    while k < len(s):
        c = s[k]
        if c == "\\":
            k += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return k
        k += 1
    raise ValueError("unbalanced braces near: " + s[i:i + 60])


def strip_comments(text):
    """Comment-free lines with the original numbering (dropped lines become empty)."""
    out = []
    for line in text.split("\n"):
        if line.lstrip().startswith("%"):
            out.append("")
        else:
            out.append(re.sub(r"(?<!\\)%.*$", "", line))
    return out


def sub_cmd(s, name, fn, nargs=1, opt=False):
    r"""Replace \name[opt]{a1}..{an} by fn(a1..an); occurrences without the arguments are left alone."""
    pat = re.compile(r"\\" + re.escape(name) + r"(?![A-Za-z])")
    out, pos = [], 0
    while True:
        m = pat.search(s, pos)
        if not m:
            out.append(s[pos:])
            break
        out.append(s[pos:m.start()])
        k = m.end()
        if opt:
            j = k
            while j < len(s) and s[j] in " \t":
                j += 1
            if j < len(s) and s[j] == "[":
                k = s.index("]", j) + 1
        args = []
        for _ in range(nargs):
            j = k
            while j < len(s) and s[j] in " \t\n":
                j += 1
            if j >= len(s) or s[j] != "{":
                break
            e = match_brace(s, j)
            args.append(s[j + 1:e])
            k = e + 1
        if len(args) < nargs:
            out.append(s[m.start():m.end()])
            pos = m.end()
            continue
        out.append(fn(*args))
        pos = k
    return "".join(out)


MATH = [("\\rightarrow", "→"), ("\\leq", "≤"), ("\\geq", "≥"), ("\\le", "≤"), ("\\ge", "≥"), ("\\rho", "ρ"), ("\\kappa", "κ"),
        ("\\sigma", "σ"), ("\\Delta", "Δ"), ("\\alpha", "α"), ("\\times", "×"), ("\\in", "∈"), ("\\pm", "±"), ("\\cdot", "·")]


def _math(m):
    for k, v in MATH:
        m = re.sub(re.escape(k) + r"(?![A-Za-z])", v, m)
    m = re.sub(r"\\(mathrm|text|operatorname)", "", m).replace("\\,", " ").replace("{", "").replace("}", "")
    return "−" if m.strip() == "-" else m


def latex_to_text(s, refs=None):
    s = s.replace("\n", " ")
    s = sub_cmd(s, "shortstack", lambda a: a.replace("\\\\", " "), opt=True)
    s = re.sub(r"\\benchname(?![A-Za-z])\s*(\{\})?", "SEALBench", s)
    s = re.sub(r"\\qsr(?![A-Za-z])\s*(\{\})?", "QSR", s)
    s = s.replace("\\cmark", "✓").replace("\\xmark", "×")
    for c in ("citep", "citet", "cite"):
        s = sub_cmd(s, c, lambda a: "\x00", opt=True)
    s = re.sub(r"[~ \t]*\x00", "", s)
    if refs is not None:
        s = sub_cmd(s, "ref", lambda a: refs.get(a, "??"))
    for c in ("textbf", "textit", "emph", "texttt", "textsc", "mathrm", "ensuremath", "underline", "text"):
        s = sub_cmd(s, c, lambda a: a)
    s = sub_cmd(s, "multicolumn", lambda n, spec, a: a, nargs=3)
    s = re.sub(r"\$([^$]*)\$", lambda m: _math(m.group(1)), s)
    s = s.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\#", "#")
    s = s.replace("``", "“").replace("''", "”").replace("`", "‘")
    s = s.replace("\\\\", " ")
    s = re.sub(r"\\[ ,;!]", " ", s)
    s = s.replace("~", " ").replace("---", "—").replace("--", "–")
    s = re.sub(r"\\rightarrow(?![A-Za-z])", "→", s)
    s = re.sub(r"\\[A-Za-z]+\*?", "", s)  # remaining layout commands (\noindent, \small, ...)
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([.,;:)])", r"\1", s)
    return s


FAKE_SUBS = [0]


def visible(s):
    """Wording rule of the site: the paper's 'fake' category is shown as 'manipulated'."""
    if s is None:
        return s
    new, n = re.subn(r"\bfake\b", "manipulated", s)
    FAKE_SUBS[0] += n
    return new


# ----------------------------------------------------------------------------------------------
# Paper structure: sections, floats, labels -> numbers
# ----------------------------------------------------------------------------------------------
def scan_paper(text_lines):
    text = "\n".join(text_lines)
    starts = [0]
    for ln in text_lines:
        starts.append(starts[-1] + len(ln) + 1)

    def lineno(off):
        return bisect.bisect_right(starts, off)

    ev = []
    for m in re.finditer(r"\\(section|subsection)(\*?)\s*\{", text):
        ev.append((m.start(), "sec", m))
    for m in re.finditer(r"\\appendix(?![A-Za-z])", text):
        ev.append((m.start(), "appendix", m))
    for m in re.finditer(r"\\begin\{(table|figure)\*?\}", text):
        ev.append((m.start(), "begin", m))
    for m in re.finditer(r"\\end\{(table|figure)\*?\}", text):
        ev.append((m.start(), "end", m))
    for m in re.finditer(r"\\label\{([^}]+)\}", text):
        ev.append((m.start(), "label", m))
    for m in re.finditer(r"\\caption\s*\{", text):
        ev.append((m.start(), "caption", m))
    ev.sort(key=lambda e: e[0])
    refs, floats = {}, []
    appendix = False
    nsec = nsub = 0
    cur_sec = cur_sub = None
    anchor = None
    counters = {"table": 0, "figure": 0}
    fl = None
    for off, kind, m in ev:
        if kind == "sec":
            j = m.end() - 1
            e = match_brace(text, j)
            title = text[j + 1:e]
            starred = m.group(2) == "*"
            if m.group(1) == "section":
                if not starred:
                    nsec += 1
                nsub = 0
                num = None if starred else (chr(64 + nsec) if appendix else str(nsec))
                cur_sec = {"number": num, "title": latex_to_text(title), "line": lineno(off)}
                cur_sub = None
                anchor = num
            else:
                if not starred:
                    nsub += 1
                num = None if starred else f"{cur_sec['number']}.{nsub}"
                cur_sub = {"number": num, "title": latex_to_text(title), "line": lineno(off)}
                anchor = num
        elif kind == "appendix":
            appendix = True
            nsec = 0
        elif kind == "begin":
            fl = {"kind": m.group(1), "start": off, "caption_tex": None, "label": None, "number": None,
                  "section": cur_sec, "subsection": cur_sub, "appendix": appendix}
        elif kind == "caption" and fl is not None:
            counters[fl["kind"]] += 1
            fl["number"] = counters[fl["kind"]]
            j = m.end() - 1
            e = match_brace(text, j)
            fl["caption_tex"] = text[j + 1:e]
        elif kind == "label":
            lab = m.group(1)
            if fl is not None:
                fl["label"] = lab
                refs[lab] = str(fl["number"])
            else:
                refs[lab] = anchor
        elif kind == "end" and fl is not None:
            fl["end"] = m.end()
            fl["body"] = text[fl["start"]:fl["end"]]
            fl["start_line"], fl["end_line"] = lineno(fl["start"]), lineno(m.end())
            floats.append(fl)
            fl = None
    return refs, floats


# ----------------------------------------------------------------------------------------------
# Table parsing
# ----------------------------------------------------------------------------------------------
RULE_RE = re.compile(r"\\(toprule|midrule|bottomrule|hline)(?![A-Za-z])|\\cmidrule(\([a-z]*\))?\{[^}]*\}")


def count_cols(spec):
    n, k = 0, 0
    while k < len(spec):
        c = spec[k]
        if c in "@!<>" and k + 1 < len(spec) and spec[k + 1] == "{":
            k = match_brace(spec, k + 1) + 1
            continue
        if c in "pmb" and k + 1 < len(spec) and spec[k + 1] == "{":
            n += 1
            k = match_brace(spec, k + 1) + 1
            continue
        if c in "lcrX":
            n += 1
        k += 1
    return n


def split_cells(row):
    return re.split(r"(?<!\\)&", row)


NUM_RE = re.compile(r"[+\-−]?\d+(?:\.\d+)?")


def parse_cell(tex):
    raw = tex.strip()
    bold = "\\textbf{" in raw
    text = latex_to_text(raw)
    cell = {"text": text, "value": None, "bold": bold}
    if raw in ("--", "") or text in ("–", ""):
        cell["text"] = "–" if raw == "--" else text
        cell["kind"] = "empty"
        return cell, raw
    t = text.replace("−", "-")
    if NUM_RE.fullmatch(t):
        cell["value"] = float(t)
        cell["kind"] = "number"
    elif re.fullmatch(r"([+\-]?\d+(?:\.\d+)?) \((.+)\)", t):
        mm = re.fullmatch(r"([+\-]?\d+(?:\.\d+)?) \((.+)\)", t)
        cell["value"] = float(mm.group(1))
        cell["note"] = mm.group(2)
        cell["kind"] = "number+note"
    elif re.fullmatch(r"\d+(?:\.\d+)?(?:, \d+(?:\.\d+)?)+", t):
        cell["value"] = [float(v) for v in t.split(", ")]
        cell["kind"] = "list"
    else:
        cell["kind"] = "text"
    return cell, raw


def parse_family_category(t):
    t = (t or "").strip()
    low = t.lower()
    fam = cat = None
    if low.startswith("post-hoc"):
        fam = "post-hoc"
    elif low.startswith("in-generation") or low.startswith("in-gen."):
        fam = "in-generation"
    if "matched" in low:
        cat = "synthetic (matched)"
    elif "all 1,593" in low:
        cat = "synthetic (all 1,593)"
    elif re.search(r"\b(manipulated|fake)\b", low):
        cat = "manipulated"
    elif re.search(r"\breal\b", low):
        cat = "real"
    elif "synthetic" in low:
        cat = "synthetic"
    return fam, cat


def parse_table(fl, refs, resolve_input):
    body_all = fl["body"]
    m = re.search(r"\\begin\{tabular\}\s*", body_all)
    j = body_all.index("{", m.end() - 1) if body_all[m.end() - 1] == "{" else body_all.index("{", m.end())
    k = match_brace(body_all, j)
    spec = body_all[j + 1:k]
    e = body_all.index("\\end{tabular}", k)
    body = body_all[k + 1:e]
    inputs = re.findall(r"\\input\{tables/([^}]+)\}", body)
    body = re.sub(r"\\input\{tables/([^}]+)\}", lambda mm: "\\sbsrc{" + mm.group(1) + "}" + resolve_input(mm.group(1)) + "\\sbsrcend{}", body)
    body = sub_cmd(body, "shortstack", lambda a: a.replace("\\\\", " "), opt=True)
    ncols = count_cols(spec)
    header_rows, groups = [], []
    seen_mid = False
    pending_rule = False
    src = "main"
    cur = None
    notes = []
    for ch in re.split(r"\\\\", body):
        while True:
            ch = ch.lstrip()
            mm = RULE_RE.match(ch)
            if mm:
                if mm.group(1) in ("midrule", "hline"):
                    if not seen_mid:
                        seen_mid = True
                    else:
                        pending_rule = True
                ch = ch[mm.end():]
                continue
            mm = re.match(r"\\sbsrc\{([^}]*)\}", ch)
            if mm:
                src = mm.group(1)
                ch = ch[mm.end():]
                continue
            mm = re.match(r"\\sbsrcend\{\}", ch)
            if mm:
                src = "main"
                ch = ch[mm.end():]
                continue
            break
        row = ch.strip()
        if not row:
            continue
        if not seen_mid:
            header_rows.append(row)
            continue
        cells = split_cells(row)
        mm = re.match(r"\\multicolumn\{(\d+)\}", row)
        if len(cells) == 1 and mm:
            cur = {"label_tex": row, "label": visible(latex_to_text(row)), "source": src, "rows": []}
            groups.append(cur)
            pending_rule = False
            continue
        if pending_rule or cur is None:
            cur = {"label_tex": None, "label": None, "source": src, "rows": []}
            groups.append(cur)
        pending_rule = False
        if len(cells) != ncols:
            notes.append(f"row has {len(cells)} cells, tabular spec has {ncols} columns: {row[:60]}")
        cur["rows"].append({"cells_tex": [c.strip() for c in cells], "source": src})
    used = max([len(r["cells_tex"]) for g in groups for r in g["rows"]] + [len(split_cells(h)) for h in header_rows] or [ncols])
    if used < ncols:
        notes = [f"tabular spec declares {ncols} columns but no row uses more than {used}; trailing empty column(s) dropped"]
        ncols = used
        notes += [f"row has {len(r['cells_tex'])} cells, table has {ncols} columns" for g in groups for r in g["rows"] if len(r["cells_tex"]) != ncols]
    # header
    hdr = []
    for hr in header_rows:
        ents, col = [], 0
        for c in split_cells(hr):
            c = c.strip()
            mm = re.match(r"\\multicolumn\{(\d+)\}", c)
            span = int(mm.group(1)) if mm else 1
            ents.append({"start": col, "span": span, "text": latex_to_text(c, refs)})
            col += span
        hdr.append(ents)
    col_labels = [""] * ncols
    if hdr:
        for ent in hdr[-1]:
            if ent["start"] < ncols:
                col_labels[ent["start"]] = ent["text"]
    col_groups = []
    for ents in hdr[:-1]:
        for ent in ents:
            if ent["text"]:
                col_groups.append({"label": visible(ent["text"]), "start": ent["start"], "span": ent["span"]})
    return {"spec": spec, "ncols": ncols, "inputs": inputs, "col_labels": col_labels, "col_groups": col_groups,
            "groups": groups, "notes": notes, "header_tex": header_rows}


TABLE_UNITS = {
    "tab_crossfamily": {"unit": "%"},
    "tab_tier3_main": {"unit": "fraction"},
    "tab_tier3_rest": {"unit": "fraction"},
    "tab_main3": {"unit": "%", "cols": {"Bits": "bits", "AURSC": "fraction", "Obs. Min@0.2": "fraction"}},
    "tab_levels": {"unit": "%", "groups": {"QSR": "fraction", "Msg. Rec.": "fraction", "Bit Acc.": "fraction"}},
    "tab_ingen": {"unit": "%", "cols": {"Obs. Min@0.2": "fraction", "AURSC": "fraction"}},
    "tab_modes": {"unit": "%", "cols": {"Obs. Min@0.2": "fraction"}},
    "tab_unmarker": {"unit": "%"},
    "tab_family": {"unit": "fraction"},
    "tab_synergy": {"unit": "fraction (difference)", "cols": {"Mean ASI": "ASI"}},
    "tab_message_agg": {"unit": "fraction"},
    "tab_partial": {"unit": "fraction", "cols": {"Share (%)": "%"}},
    "tab_readers_main": {"unit": "fraction"},
    "tab_readers_levels": {"unit": "fraction"},
    "tab_readers_method": {"unit": "fraction"},
    "tab_readers_agree": {"unit": "coefficient", "cols": {"Mean |Δ|": "fraction", "Agreement (%)": "%"}},
    "tab_calib": {"unit": "%"},
    "tab_generator": {"unit": "%"},
    "tab_subclass": {"unit": "%"},
    "tab_subclass_spread": {"unit": "percentage points"},
    "tab_arms": {"unit": "%", "cols": {"Images": "count", "AURSC": "fraction", "Obs. Min@0.2": "fraction"}},
    "tab_attackgrid": {"unit": "ASI"},
    "tab_chains": {"unit": "ASI"},
    "tab_budget_sensitivity": {"unit": "Spearman ρ", "cols": {"Budget b": "ASI budget"}},
    "tab_comparison": {"unit": None},
    "tab_methods": {"unit": None},
    "tab_qsrcases": {"unit": None},
}
CAPTION_FIXES = {
    "tab_tier3_main": (lambda c: re.sub(r"\s*Table \d+\.$", "", c),
                       "The paper's caption ends with a stray cross-reference ('Table~\\ref{tab:tier3rest}.') after the sentence that already cites "
                       "Appendix Table 18; caption_site drops it."),
    "tab_modes": (lambda c: c.replace("in this appendix, the basis of the semantic-arm block",
                                      "in this appendix. Message mode is the bit agreement with the embedded sentence on the sentence-payload images, "
                                      "the basis of the message recovery block"),
                  "The paper's caption lacks the definition of message mode (it reads '..., the basis of the semantic-arm block of Table 3'). "
                  "caption_site restores it from the comment in make_tables.py (sentence mode = bit agreement with the embedded sentence on the "
                  "sentence-payload images, the basis of Table 3). The wording should be confirmed by the authors."),
}
CAPTION_FIXES["tab_crossfamily"] = (
    lambda c: c.replace("The identity attribution block reports open-set attribution accuracy (in @1% FPR) budget,",
                        "The identity attribution block reports TPR@1%FPR (%) with the open-set identity score,")
               .replace("The identity attribution block reports open-set attribution accuracy (in @1%FPR) budget,",
                        "The identity attribution block reports TPR@1%FPR (%) with the open-set identity score,"),
    "The paper's caption says the identity attribution block reports open-set attribution accuracy, but its numbers are TPR@1%FPR: "
    "they are rebuilt here from detection.csv of the matched identity arm and of the in-generation eval_v2 (column tpr), and the "
    "attribution accuracy is different (RingID All: 80.1 in the table = TPR; attribution accuracy is 54.1, as the paper's own "
    "Appendix text says; WAM All: 90.2 = TPR vs 88.9 attribution). caption_site states the metric that the numbers are. "
    "The wording should be confirmed by the authors.")
UNMARKER_CAPTION = ("UnMarker results: TPR@1%FPR (%) under the UnMarker single attack (C2) and the UnMarker-then-share chain "
                    "(unmarkshare, C4), on the nested 50-per-subclass cohort, for the 11 post-hoc methods per image category "
                    "and the 4 in-generation methods on synthetic images.")


def build_leaderboards(text_lines, raw_text, refs, floats):
    file_tex = {}

    def resolve(name):
        p = P(f"tables/{name}.tex")
        with open(p, encoding="utf-8") as fh:
            file_tex[name] = fh.read()
        return file_tex[name]

    tables = []
    # the UnMarker table exists only as a commented-out block in the main tex: rebuild its float from those lines
    raw_lines = raw_text.split("\n")
    li = next(i for i, ln in enumerate(raw_lines) if "\\label{tab:unmarker}" in ln)
    b = max(i for i in range(li) if "\\begin{table}" in raw_lines[i])
    en = min(i for i in range(li, len(raw_lines)) if "\\end{table}" in raw_lines[i])
    unm_lines = [re.sub(r"^\s*%\s?%\s?", "", ln) for ln in raw_lines[b:en + 1]]
    unm_body = "\n".join(strip_comments("\n".join(unm_lines)))
    m = re.search(r"\\caption\s*\{", unm_body)
    unm_caption = unm_body[m.end() - 1:match_brace(unm_body, m.end() - 1) + 1][1:-1]
    unm_float = {"kind": "table", "body": unm_body, "caption_tex": unm_caption, "label": "tab:unmarker", "number": None,
                 "section": None, "subsection": None, "appendix": True, "start_line": b + 1, "end_line": en + 1, "commented_out": True}
    all_floats = [f for f in floats if f["kind"] == "table"] + [unm_float]
    for fl in all_floats:
        parsed = parse_table(fl, refs, resolve)
        tid = parsed["inputs"][0] if parsed["inputs"] else fl["label"].replace(":", "_")
        cfg = TABLE_UNITS.get(tid, {"unit": None})
        # column kinds from the data cells
        ncols = parsed["ncols"]
        kinds = [set() for _ in range(ncols)]
        for g in parsed["groups"]:
            for r in g["rows"]:
                for i, c in enumerate(r["cells_tex"][:ncols]):
                    kinds[i].add(parse_cell(c)[0]["kind"])
        columns = []
        for i in range(ncols):
            k = kinds[i] - {"empty"}
            is_value = bool(k) and k <= {"number", "number+note", "list"}
            grp = next((g["label"] for g in parsed["col_groups"] if g["start"] <= i < g["start"] + g["span"]), None)
            label = visible(parsed["col_labels"][i])
            unit = None
            if is_value:
                unit = cfg.get("cols", {}).get(label, cfg.get("unit"))
            columns.append({"index": i, "label": label, "group": grp, "kind": "value" if is_value else "label", "unit": unit})
        value_idx = [c["index"] for c in columns if c["kind"] == "value"]
        groups_out, rows_out = [], []
        prev = None
        for gi, g in enumerate(parsed["groups"]):
            gunit = None
            for k2, u in cfg.get("groups", {}).items():
                if g["label"] and g["label"].startswith(k2):
                    gunit = u
            groups_out.append({"index": gi, "label": g["label"], "source": "paper:" + (f"tables/{g['source']}.tex" if g["source"] != "main" else MAIN_TEX),
                               "unit": gunit, "n_rows": len(g["rows"])})
            for r in g["rows"]:
                cells = []
                for i, ctex in enumerate((r["cells_tex"] + [""] * ncols)[:ncols]):
                    c, raw = parse_cell(ctex)
                    if columns[i]["kind"] == "label":
                        c["text"] = visible(c["text"])
                        c["value"] = None
                    c["tex"] = raw
                    c.pop("kind", None)
                    if not c.get("bold"):
                        c.pop("bold", None)
                    cells.append(c)
                labels = [cells[i]["text"] for i in range(ncols) if columns[i]["kind"] == "label"]
                mk = next((NAME2KEY[t] for t in labels if t in NAME2KEY), None)
                fam = cat = None
                for t in labels:
                    if t in ("in-gen.", "in-generation"):
                        fam = "in-generation"
                    elif t == "post-hoc":
                        fam = "post-hoc"
                for t in labels + [g["label"] or ""]:
                    f2, c2 = parse_family_category(t)
                    fam = fam or f2
                    cat = cat or c2
                cont = False
                if labels and labels[0] == "" and prev is not None and prev.get("row_key"):
                    mk, cont = prev.get("method_key"), True
                if mk and not fam:
                    fam = FAMILY_OF[mk]
                atype = next((LABEL2TYPE[t] for t in labels if t in LABEL2TYPE), None)
                row_key = prev["row_key"] if cont else (labels[0] if labels else None)
                row = {"group": gi, "label": " / ".join(([row_key] if cont else []) + [t for t in labels if t]) or None, "row_key": row_key,
                       "method": SHORTNAME.get(mk) if mk else None, "method_key": mk, "family": fam, "category": cat,
                       "cells": cells,
                       "values": [cells[i]["value"] for i in value_idx],
                       "bold": [bool(cells[i].get("bold")) for i in value_idx],
                       "source": "paper:" + (f"tables/{r['source']}.tex" if r["source"] != "main" else MAIN_TEX)}
                if atype:
                    row["attack_type"] = atype
                if cont:
                    row["continues_method_of_previous_row"] = True
                rows_out.append(row)
                prev = row
        sec = fl.get("section") or {}
        sub = fl.get("subsection") or {}
        cap_tex = fl["caption_tex"] or ""
        caption = latex_to_text(cap_tex, refs)
        entry = {
            "id": tid,
            "label": fl["label"],
            "paper_table_number": fl["number"],
            "in_paper": not fl.get("commented_out", False),
            "part": "appendix" if fl["appendix"] else "main",
            "section": {"number": sec.get("number"), "title": sec.get("title")} if sec else None,
            "subsection": {"number": sub.get("number"), "title": sub.get("title")} if sub else None,
            "caption": visible(caption),
            "caption_tex": cap_tex,
            "columns": columns,
            "column_groups": parsed["col_groups"],
            "row_groups": groups_out,
            "rows": rows_out,
            "source": {
                "rows": [f"paper:tables/{n}.tex" for n in parsed["inputs"]] or [f"paper:{MAIN_TEX}"],
                "rows_sha256": {n: sha256(P(f"tables/{n}.tex")) for n in parsed["inputs"]},
                "environment": f"paper:{MAIN_TEX}#L{fl['start_line']}-L{fl['end_line']}",
                "tabular_spec": parsed["spec"],
            },
        }
        if parsed["notes"]:
            entry["parse_notes"] = parsed["notes"]
        if fl.get("commented_out"):
            entry["caption"] = UNMARKER_CAPTION
            entry["caption_original_commented_tex"] = cap_tex
            entry["note"] = ("Not in the current paper: the table environment is commented out in the main tex. The rows file "
                             "tables/tab_unmarker.tex is still generated by make_tables.py from T4_full_grid.csv. The commented caption "
                             "says '5 in-generation methods' and 'Level 2/Level 4'; the caption here is corrected to the 4 in-generation "
                             "methods and attack categories C2/C4 that the rows file contains.")
        entry["caption_site"] = entry["caption"]
        if tid in CAPTION_FIXES:
            fix, why = CAPTION_FIXES[tid]
            entry["caption_site"] = fix(entry["caption"])
            entry["caption_note"] = why
            check("leaderboards", f"{tid}: caption_site differs from the paper caption only by the documented fix", entry["caption_site"] != entry["caption"], why[:90])
        tables.append(entry)
        # round-trip checks against the rows files
        for n in parsed["inputs"]:
            lines = [ln.strip() for ln in file_tex[n].split("\n") if ln.strip()]
            data_lines = [ln for ln in lines if ln.endswith("\\\\") and not ln.startswith("\\multicolumn")]
            mine = [r for r in rows_out if r["source"] == f"paper:tables/{n}.tex"]
            ok = len(data_lines) == len(mine)
            bad = []
            for ln, r in zip(data_lines, mine):
                cells_tex = [c.strip() for c in split_cells(ln[:-2].strip())]
                if cells_tex != [c["tex"] for c in r["cells"]][:len(cells_tex)]:
                    bad.append(ln[:50])
                for c in r["cells"]:
                    v = c.get("value")
                    if isinstance(v, float):
                        tt = c["text"].replace("−", "-")
                        mm = NUM_RE.match(tt)
                        dec = len(mm.group(0).split(".")[1]) if "." in mm.group(0) else 0
                        back = f"{v:.{dec}f}"
                        if tt.startswith("+"):
                            back = "+" + back
                        if back != mm.group(0) and not (back == "-0.000" and mm.group(0) == "-0.000"):
                            bad.append(f"{c['text']}->{back}")
            check("leaderboards", f"{tid}: rows of tables/{n}.tex parsed one-to-one and numbers round-trip",
                  ok and not bad, f"{len(mine)} rows parsed, {len(data_lines)} data lines in file" + (f"; mismatches: {bad[:5]}" if bad else ""))
        widths = {len(r["cells"]) for r in rows_out}
        check("leaderboards", f"{tid}: every row has the tabular's {parsed['ncols']} columns", not [n for n in parsed["notes"] if "dropped" not in n],
              "; ".join(parsed["notes"][:3]) if parsed["notes"] else f"{len(rows_out)} rows")
    tables.sort(key=lambda t: (t["paper_table_number"] is None, t["paper_table_number"] or 0))
    return tables


# ----------------------------------------------------------------------------------------------
# AURSC recipe (make_tables.py _aursc, pure Python)
# ----------------------------------------------------------------------------------------------
def aursc(xs, ys, R=0.2):
    pts = sorted(zip(xs, ys), key=lambda t: t[0])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    nodes = [0.0] + [x for x in xs if 0.0 < x < R] + [R]
    vals = []
    for t in nodes:
        if t <= xs[0]:
            vals.append(ys[0])
        elif t >= xs[-1]:
            vals.append(ys[-1])
        else:
            j = min(bisect.bisect_right(xs, t) - 1, len(xs) - 2)
            x0, x1 = xs[j], xs[j + 1]
            vals.append(ys[j] if x1 == x0 else ys[j] + (ys[j + 1] - ys[j]) * (t - x0) / (x1 - x0))
    area = sum((vals[i] + vals[i + 1]) / 2.0 * (nodes[i + 1] - nodes[i]) for i in range(len(nodes) - 1))
    return area / R


def load_arm(mdir, posthoc, methods):
    """detection TPR@1%FPR + per-condition mean ASI for one metric directory (the make_tables.py _tpr_arm inputs)."""
    det = [r for r in rd(f"{mdir}/detection.csv") if r["far"] == "0.01" and (not posthoc or r["n_eval"] == "100")]
    tpr = {(r["method"], r["attack"], r["severity"] or ""): float(r["tpr"]) for r in det}
    anchor = {r["method"]: float(r["tpr"]) for r in det if r["attack"] == "none"}
    x = collections.defaultdict(dict)
    npos = {}
    for r in rd(f"{mdir}/robust_curves.csv"):
        if r["severity"] == "clean":
            continue
        if r["severity"] not in x[(r["method"], r["attack"])]:
            x[(r["method"], r["attack"])][r["severity"]] = float(r["x"])
            npos[(r["method"], r["attack"], r["severity"])] = int(r["n_pos"]) if r["n_pos"] else None
    return {"tpr": tpr, "anchor": anchor, "x": x, "npos": npos, "methods": methods}


def arm_scalars(arm):
    """{method: (AURSC over 28 attack types, Obs. Min@0.2, unattacked TPR, {attack type: AURSC})} -- make_tables.py _tpr_arm/_tpr_fam."""
    out = {}
    for m in arm["methods"]:
        per, mins = {}, []
        for a in ATTACK_TYPES:
            sev = arm["x"].get((m, a), {})
            if not sev or m not in arm["anchor"] or any((m, a, s) not in arm["tpr"] for s in sev):
                continue
            xs = [0.0] + [sev[s] for s in sev]
            ys = [arm["anchor"][m]] + [arm["tpr"][(m, a, s)] for s in sev]
            per[a] = aursc(xs, ys)
            cand = [y for xx, y in zip(xs[1:], ys[1:]) if xx <= 0.2]
            if cand:
                mins.append(min(cand))
        out[m] = (statistics.mean(per.values()), min(mins), arm["anchor"][m], per)
    return out


# ----------------------------------------------------------------------------------------------
# Heat map (make_figs.py Figure "heatmap")
# ----------------------------------------------------------------------------------------------
L1_ORDER = ["brightness", "contrast", "hue", "overlay", "gnoise", "gblur", "resize", "jpeg", "crop", "rotation"]


def sevkey(a, s):
    try:
        return float(s)
    except Exception:
        return {"q1": 1, "q3": 3, "str0_1": 1, "str0_2": 2, "str0_3": 3, "flux2_klein_fast": 1, "qwen_image_edit_fast": 2}.get(s, 0)


def heatmap_conditions(grid):
    conds = collections.OrderedDict()
    for lv in ["L1", "L2", "L3", "L4"]:
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
    return [(lv, a, s) for lv in conds for (a, s) in conds[lv]]


def cond_id(a, s):
    return f"{a}:{s}"


def mean_asi_by_condition(arms_weighted, methods):
    """Mean over methods of the condition-level mean ASI; with several arms, each method's ASI is pooled by n_pos."""
    out = {}
    keys = set()
    for arm, _w in arms_weighted:
        for (m, a), sev in arm["x"].items():
            for s in sev:
                keys.add((a, s))
    for a, s in keys:
        per_m = []
        for m in methods:
            num = den = 0.0
            for arm, _w in arms_weighted:
                if s in arm["x"].get((m, a), {}):
                    n = arm["npos"].get((m, a, s)) or 1
                    num += arm["x"][(m, a)][s] * n
                    den += n
            if den:
                per_m.append(num / den)
        if per_m:
            out[cond_id(a, s)] = statistics.mean(per_m)
    return out


def build_heatmap(arms, refs):
    grid = rd(T4)
    idx = {}
    for r in grid:
        k = (r["category"], r["family"], r["method"], r["attack"], r["severity"])
        check_dup = k in idx
        if check_dup:
            check("heatmap", "T4_full_grid has one row per (category, family, method, attack, severity)", False, str(k))
        idx[k] = r
    allc = heatmap_conditions(grid)
    check("heatmap", "52 conditions in the make_figs.py order", len(allc) == 52, f"{len(allc)} conditions")

    def val(cat, fam, m, a, s, col="tpr_far01"):
        r = idx.get((cat, fam, m, a, s))
        return 100 * float(r[col]) if r and r[col] else None   # unrounded, so 1-decimal display matches the paper's own f"{100*x:.1f}"

    def nval(cat, fam, m, a, s):
        r = idx.get((cat, fam, m, a, s))
        return int(r["n"]) if r and r["n"] else None

    conditions = [{"id": cond_id(a, s), "attack_type": a, "severity": s, "category": LEVEL2CAT[lv],
                   "label": f"{HEAT_SHORT[a]} {HEAT_SEV.get(s, s)}".strip()} for lv, a, s in allc]
    grids = {}
    for cat_raw, cat in IMAGE_CAT.items():
        g = {"post_hoc": {m: [val(cat_raw, "post-hoc", m, a, s) for _, a, s in allc] for m in POSTHOC},
             "post_hoc_n": {m: [nval(cat_raw, "post-hoc", m, a, s) for _, a, s in allc] for m in POSTHOC},
             "post_hoc_attribution_acc": {m: [val(cat_raw, "post-hoc", m, a, s, "acc") for _, a, s in allc] for m in POSTHOC}}
        if cat_raw == "synthetic":
            g["in_generation"] = {m: [val(cat_raw, "in-generation", m, a, s) for _, a, s in allc] for m in INGEN}
            g["in_generation_n"] = {m: [nval(cat_raw, "in-generation", m, a, s) for _, a, s in allc] for m in INGEN}
        grids[cat] = g
    # mean ASI per condition (T4 has no ASI column; computed from the robust_curves.csv files)
    asi = {
        "manipulated_post_hoc": mean_asi_by_condition([(arms["fake"], 1)], POSTHOC),
        "real_post_hoc": mean_asi_by_condition([(arms["real"], 1)], POSTHOC),
        "synthetic_post_hoc": mean_asi_by_condition([(arms["syn_identity"], 1), (arms["syn_newgen_identity"], 1)], POSTHOC),
        "synthetic_in_generation": mean_asi_by_condition([(arms["ingen"], 1)], INGEN),
    }
    asi_out = {k: [r4(v.get(c["id"]), 5) for c in conditions] for k, v in asi.items()}
    nulls = {cat: sorted({(m, conditions[i]["id"]) for m, row in grids[cat]["post_hoc"].items() for i, v in enumerate(row) if v is None}) for cat in grids}
    nulls["synthetic_in_generation"] = sorted({(m, conditions[i]["id"]) for m, row in grids["synthetic"]["in_generation"].items() for i, v in enumerate(row) if v is None})
    check("heatmap", "missing cells are exactly real-category UnMarker and unmarkshare for the 7 capacity methods",
          nulls["real"] == sorted((m, c) for m in SEM_PH for c in ("unmarker:default", "unmarker_resize_jpeg_unmarkshare:chain"))
          and not nulls["manipulated"] and not nulls["synthetic"] and not nulls["synthetic_in_generation"],
          f"null cells: { {k: len(v) for k, v in nulls.items()} }")
    out = {
        "_meta": meta([f"repo:{T4}", f"repo:{DIR_FAKE_ID}/robust_curves.csv", f"repo:{DIR_REAL_ID}/robust_curves.csv",
                       f"repo:{DIR_SYN_ID}/robust_curves.csv", f"repo:{DIR_SYN_NG}/robust_curves.csv", f"repo:{DIR_INGEN}/robust_curves.csv",
                       "repo:iclr_draft/scripts/make_figs.py"]),
        "paper_figure": {"label": "fig:heatmap", "number": int(refs["fig:heatmap"]), "file": "fig/fig3_heatmap.pdf",
                         "reproduces": "grids.synthetic.post_hoc + grids.synthetic.in_generation, conditions in this order"},
        "metric": "TPR@1%FPR (%), column tpr_far01 of T4_full_grid.csv times 100, for both families (post-hoc methods in identity mode)",
        "dot_below": 50,
        "methods": {"post_hoc": POSTHOC, "in_generation": INGEN},
        "method_names": {m: SHORTNAME[m] for m in POSTHOC + INGEN},
        "conditions": conditions,
        "category_names": {k: v["name"] for k, v in CATEGORY_INFO.items()},
        "grids": grids,
        "grid_notes": {
            "synthetic": "Paper figure. Post-hoc = the 1,593-image synthetic subset (identity payload); in-generation = the 1,193-image matched cohort.",
            "manipulated": "Not a paper figure: the same 52 conditions on the 1,600 manipulated images (T4_full_grid.csv category label for manipulated images), post-hoc only.",
            "real": "Not a paper figure: the same 52 conditions on the 1,600 real images, post-hoc only. UnMarker and unmarkshare are null for the 7 "
                    "sentence-capable methods: on real images their UnMarker conditions were run on the sentence-payload images only, so the "
                    "identity-mode grid has no value (tab_unmarker prints '--').",
            "post_hoc_n": "Number of attacked watermarked images behind each cell (T4 column n).",
            "post_hoc_attribution_acc": "Open-set attribution accuracy at 1% FPR (%) over the 100-identity codebook, T4 column acc. Not shown in the paper figure.",
        },
        "mean_asi": {
            "values": asi_out,
            "note": ("T4_full_grid.csv has no ASI column. These values are computed by build_data.py from robust_curves.csv (column x = "
                     "condition-level mean ASI) as the mean over methods; synthetic_post_hoc pools the two synthetic identity arms per method "
                     "weighted by n_pos. They are not printed in the paper. The paper's own mean-ASI values (matched cohort) are in attacks.json."),
            "sources": {"manipulated_post_hoc": f"repo:{DIR_FAKE_ID}/robust_curves.csv", "real_post_hoc": f"repo:{DIR_REAL_ID}/robust_curves.csv",
                        "synthetic_post_hoc": [f"repo:{DIR_SYN_ID}/robust_curves.csv", f"repo:{DIR_SYN_NG}/robust_curves.csv"],
                        "synthetic_in_generation": f"repo:{DIR_INGEN}/robust_curves.csv"},
        },
    }
    return out, idx, allc


# ----------------------------------------------------------------------------------------------
# Curves (make_figs.py Figure "curves") and further sets
# ----------------------------------------------------------------------------------------------
def curve_set(arm, sid, label, family, category, sources, in_paper=None, note=None):
    methods = arm["methods"]
    curves, chains, unatt = {}, {}, {}
    for m in methods:
        unatt[m] = r4(100 * arm["anchor"][m])
        curves[m] = {}
        for a, _t in FIG_CURVE_TYPES:
            seen = arm["x"].get((m, a), {})
            pts = [(0.0, arm["anchor"][m], "unattacked")] + [(x, arm["tpr"][(m, a, sv)], sv) for sv, x in seen.items() if (m, a, sv) in arm["tpr"]]
            pts.sort(key=lambda p: (p[0], p[1]))
            if len(pts) > 1:   # attack types without a measured condition for this method are left out (e.g. real UnMarker, 7 methods)
                curves[m][a] = [[r4(x, 5), r4(100 * y), sv] for x, y, sv in pts]
        chains[m] = {}
        for a in CHAINS_C3 + CHAINS_C4:
            sev = arm["x"].get((m, a), {})
            if "chain" in sev and (m, a, "chain") in arm["tpr"]:
                chains[m][a] = [r4(sev["chain"], 5), r4(100 * arm["tpr"][(m, a, "chain")])]
    sc = arm_scalars(arm)
    summary = {m: {"aursc_all_attack_types": r4(sc[m][0], 6), "obs_min_at_0_2": r4(sc[m][1], 6),
                   "aursc_by_attack_type": {a: r4(v, 6) for a, v in sc[m][3].items()}} for m in methods}
    d = {"id": sid, "label": label, "family": family, "category": category, "methods": methods, "sources": sources,
         "unattacked_tpr": unatt, "curves": curves, "chains": chains, "summary": summary}
    if in_paper:
        d["in_paper"] = in_paper
    if note:
        d["note"] = note
    return d, sc


def build_curves(arms, refs, lb):
    sets = []
    fig_n = int(refs["fig:curves"])
    s, sc_fake = curve_set(arms["fake"], "manipulated_post_hoc", "Post-hoc, manipulated images (1,600), identity mode", "post-hoc", "manipulated",
                           [f"repo:{DIR_FAKE_ID}/robust_curves.csv", f"repo:{DIR_FAKE_ID}/detection.csv"],
                           in_paper={"label": "fig:curves", "number": fig_n, "file": "fig/fig2_curves.pdf"})
    sets.append(s)
    s, sc_real = curve_set(arms["real"], "real_post_hoc", "Post-hoc, real images (1,600), identity mode", "post-hoc", "real",
                           [f"repo:{DIR_REAL_ID}/robust_curves.csv", f"repo:{DIR_REAL_ID}/detection.csv"],
                           note="Same construction as the paper figure, on the real category. UnMarker curves exist only for CIN, PIMoG, WAM and TrustMark (identity arm roster on real images).")
    sets.append(s)
    s, sc_syn = curve_set(arms["syn_identity"], "synthetic_post_hoc_arm_syn_identity", "Post-hoc, synthetic arm syn_identity (796 images: SD2.1, SDXL, FLUX.1), identity mode",
                          "post-hoc", "synthetic", [f"repo:{DIR_SYN_ID}/robust_curves.csv", f"repo:{DIR_SYN_ID}/detection.csv"],
                          note="One of the two arms that the paper's synthetic category pools (weights 796/797). Its own calibration.")
    sets.append(s)
    s, sc_ng = curve_set(arms["syn_newgen_identity"], "synthetic_post_hoc_arm_syn_newgen_identity", "Post-hoc, synthetic arm syn_newgen_identity (797 images: six generators), identity mode",
                         "post-hoc", "synthetic", [f"repo:{DIR_SYN_NG}/robust_curves.csv", f"repo:{DIR_SYN_NG}/detection.csv"],
                         note="Second synthetic arm pooled into the paper's synthetic category.")
    sets.append(s)
    s, sc_mat = curve_set(arms["matched"], "synthetic_post_hoc_matched", "Post-hoc, matched synthetic cohort (1,193 images), identity mode", "post-hoc",
                          "synthetic (matched)", [f"repo:{DIR_SYN_MATCHED}/robust_curves.csv", f"repo:{DIR_SYN_MATCHED}/detection.csv"],
                          note="The cohort used for the post-hoc vs in-generation comparison (identity-payload images, recalibrated on the cohort's own negatives).")
    sets.append(s)
    s, sc_ig = curve_set(arms["ingen"], "synthetic_in_generation", "In-generation, matched synthetic cohort (1,193 images)", "in-generation", "synthetic (matched)",
                         [f"repo:{DIR_INGEN}/robust_curves.csv", f"repo:{DIR_INGEN}/detection.csv"],
                         note="TPR@1%FPR from detection.csv (far=0.01; RingID rows use its 1,024-key detector). Same images, prompts and seeds as the matched post-hoc cohort.")
    sets.append(s)
    n_panels = sum(1 for m in POSTHOC for a, _ in FIG_CURVE_TYPES if len(sets[0]["curves"][m].get(a, [])) > 1)
    check("curves", "paper figure: 11 methods x 14 attack types, each curve has the anchor plus its measured points", n_panels == 154,
          f"{n_panels} of 154 method-type curves have points beyond the anchor")
    # cross-checks against the paper's tables
    T = {t["id"]: t for t in lb}

    def tab_rows(tid, key=lambda r: r["method_key"]):
        return {key(r): r for r in T[tid]["rows"]}

    m3 = tab_rows("tab_main3")
    bad = []
    pooled = {m: ((sc_syn[m][0] * 796 + sc_ng[m][0] * 797) / 1593, min(sc_syn[m][1], sc_ng[m][1])) for m in POSTHOC}
    for m in POSTHOC:
        v = m3[m]["values"]  # Bits, then (Unatt, AURSC, Min, Attr, MaxFPR) x 3
        for ci, (au, mn) in enumerate([(sc_fake[m][0], sc_fake[m][1]), (sc_real[m][0], sc_real[m][1]), pooled[m]]):
            if f"{au:.3f}" != f"{v[2 + 5 * ci]:.3f}" or f"{mn:.3f}" != f"{v[3 + 5 * ci]:.3f}":
                bad.append((m, ci, round(au, 4), v[2 + 5 * ci], round(mn, 4), v[3 + 5 * ci]))
        for ci, sc in enumerate([sc_fake, sc_real]):
            if f"{100 * sc[m][2]:.1f}" != f"{v[1 + 5 * ci]:.1f}":
                bad.append((m, "unatt", ci))
    check("curves", "AURSC (28 attack types) and Obs. Min@0.2 recomputed from the manipulated, real and pooled synthetic curves equal tab_main3 (33 methods x categories)",
          not bad, f"mismatches: {bad}" if bad else "all 66 values equal at 3 decimals; unattacked TPR equal for manipulated and real")
    ar = {(r["cells"][0]["text"], r["method_key"]): r for r in T["tab_arms"]["rows"]}
    bad = []
    for lab, sc in [("SD2.1/SDXL/FLUX.1", sc_syn), ("six generators", sc_ng)]:
        for m in POSTHOC:
            v = ar[(lab, m)]["values"]
            if f"{sc[m][0]:.3f}" != f"{v[-2]:.3f}" or f"{sc[m][1]:.3f}" != f"{v[-1]:.3f}":
                bad.append((lab, m, round(sc[m][0], 4), v[-2], round(sc[m][1], 4), v[-1]))
    check("curves", "AURSC and Obs. Min@0.2 of each synthetic arm equal tab_arms (22 rows)", not bad, f"mismatches: {bad}" if bad else "22 rows equal")
    ig = tab_rows("tab_ingen")
    bad = [(m, round(sc_ig[m][1], 4), ig[m]["values"][0], round(sc_ig[m][0], 4), ig[m]["values"][1]) for m in INGEN
           if f"{sc_ig[m][1]:.3f}" != f"{ig[m]['values'][0]:.3f}" or f"{sc_ig[m][0]:.3f}" != f"{ig[m]['values'][1]:.3f}"]
    check("curves", "in-generation AURSC and Obs. Min@0.2 equal tab_ingen", not bad, f"mismatches: {bad}" if bad else "4 methods equal")
    fam = {r.get("attack_type"): r for r in T["tab_family"]["rows"]}
    bad = []
    for a in ATTACK_TYPES:
        row = fam[a]["values"]
        cols = [[sc_fake[m][3][a] for m in POSTHOC if a in sc_fake[m][3]],
                [sc_real[m][3][a] for m in POSTHOC if a in sc_real[m][3]],
                [(sc_syn[m][3][a] * 796 + sc_ng[m][3][a] * 797) / 1593 for m in POSTHOC if a in sc_syn[m][3] and a in sc_ng[m][3]],
                [sc_ig[m][3][a] for m in INGEN if a in sc_ig[m][3]]]
        for ci, vals in enumerate(cols):
            if f"{statistics.mean(vals):.3f}" != f"{row[ci]:.3f}":
                bad.append((a, ci, round(statistics.mean(vals), 4), row[ci]))
    check("curves", "per-attack-type AURSC averaged over methods equals tab_family (28 types x 4 columns)", not bad,
          f"mismatches: {bad}" if bad else "112 values equal")
    out = {
        "_meta": meta(sorted({p for s in sets for p in s["sources"]}) + ["repo:iclr_draft/scripts/make_figs.py", "repo:iclr_draft/scripts/make_tables.py"]),
        "paper_figure": {"label": "fig:curves", "number": fig_n, "file": "fig/fig2_curves.pdf", "reproduces": "sets[0] (manipulated_post_hoc), curves only"},
        "x": "mean ASI of the condition (robust_curves.csv column x); the first point of every curve is the unattacked result at ASI 0",
        "y": "TPR@1%FPR (%) from detection.csv (far = 0.01; post-hoc rows with n_eval = 100, the 100-identity open-set score)",
        "point_format": "[mean ASI, TPR@1%FPR (%), severity label]; chains: [mean ASI, TPR@1%FPR (%)]",
        "asi_budget": 0.2,
        "attack_types": [{"key": a, "panel_title": t, "name": TYPE_DISPLAY[a], "category": CAT_OF[a]} for a, t in FIG_CURVE_TYPES],
        "chain_types": [{"key": a, "name": CHAIN_NAME[a], "category": CAT_OF[a]} for a in CHAINS_C3 + CHAINS_C4],
        "method_style": {m: {"color": FIG_COLOR[m], "line": FIG_STYLE[m]} for m in POSTHOC},
        "summary_note": ("summary.aursc_all_attack_types and obs_min_at_0_2 follow make_tables.py: normalized area over ASI [0, 0.2] averaged over "
                         "all 28 attack types (14 single types + 14 chains), and the lowest measured TPR@1%FPR among conditions with mean ASI <= 0.2. "
                         "Values are fractions, not percent."),
        "sets": sets,
    }
    return out


# ----------------------------------------------------------------------------------------------
# Scatter (make_figs.py Figure "dissociation")
# ----------------------------------------------------------------------------------------------
def build_scatter(refs, lb):
    def load(rel, family):
        rows = rd(rel)
        pts, anchors = [], {}
        for r in rows:
            if r["attack"] == "none":
                anchors[r["method"]] = {"bit_acc": r4(r["bit_acc"], 6), "qsr": r4(r["qsr_corrected"], 6),
                                        "msg_rec": r4(r["exact_acc"], 6) if r.get("exact_acc") else None, "n": int(r["n"]) if r["n"] else None}
            if r["attack"] in ("none", "") or not r["bit_acc"] or not r["qsr_corrected"]:
                continue
            p = {"method": r["method"], "family": family, "attack_type": r["attack"], "severity": r["severity"],
                 "condition": cond_id(r["attack"], r["severity"]), "category": CAT_OF.get(r["attack"]),
                 "asi": r4(r["asi"], 6) if r["asi"] else None, "bit_acc": r4(r["bit_acc"], 6), "qsr": r4(r["qsr_corrected"], 6),
                 "n": int(r["n"]) if r["n"] else None}
            if r.get("exact_acc"):
                p["msg_rec"] = r4(r["exact_acc"], 6)
            pts.append(p)
        return pts, anchors, rows

    ph, ph_anchor, ph_rows = load(SEM_MATCHED, "post-hoc")
    ig, ig_anchor, ig_rows = load(SEM_INGEN, "in-generation")

    def diss(pts):
        return sum(1 for p in pts if p["bit_acc"] >= 0.9 and p["qsr"] <= 0.5)

    check("scatter", "post-hoc points: 364, dissociated (bit acc >= 0.9 and QSR <= 0.5): 42 (paper text: 42 of 364)",
          len(ph) == 364 and diss(ph) == 42, f"{diss(ph)} of {len(ph)}")
    check("scatter", "in-generation points: 156, dissociated: 1 (paper text: 1 of 156)", len(ig) == 156 and diss(ig) == 1, f"{diss(ig)} of {len(ig)}")
    # recompute sem-AURSC, bit-AURSC and the QSR columns of tab_tier3_main from the same rows (make_tables.py _sem_areas/_t3_cond)
    T = {t["id"]: t for t in lb}
    t3 = {r["method_key"]: r for r in T["tab_tier3_main"]["rows"]}
    bad = []
    for rows, methods in [(ph_rows, SEM_PH), (ig_rows, SEM_IG)]:
        for m in methods:
            res = {}
            for col in ("qsr_corrected", "bit_acc"):
                anchor = [float(r[col]) for r in rows if r["method"] == m and r["attack"] == "none" and r[col]][0]
                pts = collections.defaultdict(dict)
                for r in rows:
                    if r["method"] != m or r["attack"] == "none" or not r["asi"] or not r[col]:
                        continue
                    pts[r["attack"]].setdefault(r["severity"], (float(r["asi"]), float(r[col])))
                areas = [aursc([0.0] + [v[0] for v in sev.values()], [anchor] + [v[1] for v in sev.values()]) for a, sev in pts.items() if a in ATTACK_TYPES]
                res[col] = statistics.mean(areas)
                acc = collections.defaultdict(lambda: [0.0, 0.0])
                for r in rows:
                    if r["method"] != m or not r[col] or not r["n"] or r["attack"] in ("none", ""):
                        continue
                    lv = CAT_OF.get(r["attack"])
                    if not lv:
                        continue
                    for k in (lv, "All"):
                        acc[k][0] += float(r[col]) * float(r["n"])
                        acc[k][1] += float(r["n"])
                res[col + "_lv"] = {k: v[0] / v[1] for k, v in acc.items()}
                res[col + "_clean"] = anchor
            v = t3[m]["values"]  # Unatt, C1..C4, All, sem-AURSC, bit-AURSC, Msg.Rec, Bit Acc
            mine = [res["qsr_corrected_clean"]] + [res["qsr_corrected_lv"][k] for k in ("C1", "C2", "C3", "C4", "All")] + \
                   [res["qsr_corrected"], res["bit_acc"], None, res["bit_acc_lv"]["All"]]
            for i, (a, b) in enumerate(zip(mine, v)):
                if a is not None and f"{a:.3f}" != f"{b:.3f}":
                    bad.append((m, T["tab_tier3_main"]["columns"][T["tab_tier3_main"]["columns"].index(next(c for c in T["tab_tier3_main"]["columns"] if c["kind"] == "value")) + i]["label"], round(a, 4), b))
    check("scatter", "QSR (Unattacked, C1-C4, All), sem-AURSC, bit-AURSC and Bit Acc. recomputed from the scatter source rows equal tab_tier3_main (10 methods)",
          not bad, f"mismatches: {bad}" if bad else "90 values equal at 3 decimals")
    out = {
        "_meta": meta([f"repo:{SEM_MATCHED}", f"repo:{SEM_INGEN}", "repo:iclr_draft/scripts/make_figs.py"]),
        "paper_figure": {"label": "fig:dissociation", "number": int(refs["fig:dissociation"]), "file": "fig/fig4_dissociation.pdf"},
        "x": "bit accuracy (fraction of embedded payload bits decoded correctly, mean over the condition's images)",
        "y": "QSR under the primary reader Qwen2.5-7B-Instruct (column qsr_corrected)",
        "shaded_region": {"bit_acc_min": 0.9, "qsr_max": 0.5},
        "panels": [
            {"id": "post_hoc", "label": "post-hoc (7 methods)", "family": "post-hoc", "cohort": "matched synthetic cohort, 1,193 images, sentence payload",
             "source": f"repo:{SEM_MATCHED}", "methods": SEM_PH, "n_points": len(ph), "n_in_shaded_region": diss(ph),
             "unattacked": ph_anchor, "points": ph},
            {"id": "in_generation", "label": "in-generation (3 methods)", "family": "in-generation", "cohort": "matched synthetic cohort, 1,193 images",
             "source": f"repo:{SEM_INGEN}", "methods": SEM_IG, "n_points": len(ig), "n_in_shaded_region": diss(ig),
             "unattacked": ig_anchor, "points": ig},
        ],
        "note": "One point per method and attacked condition (attack 'none' excluded, as in make_figs.py). msg_rec (complete-message recovery) is present only where the source CSV has exact_acc (post-hoc matched cohort).",
    }
    return out


# ----------------------------------------------------------------------------------------------
# Attacks
# ----------------------------------------------------------------------------------------------
def build_attacks(lb, allc, arms, refs):
    T = {t["id"]: t for t in lb}
    grid_rows = {r["attack_type"]: r for r in T["tab_attackgrid"]["rows"]}
    chain_rows = {r["attack_type"]: r for r in T["tab_chains"]["rows"]}
    syn_rows = {r["attack_type"]: r for r in T["tab_synergy"]["rows"]}
    # computed ASI (same recipe as make_tables.py e_m / e_ig, plus the image categories)
    comp = {
        "synthetic_matched_post_hoc": mean_asi_by_condition([(arms["matched"], 1)], POSTHOC),
        "synthetic_matched_in_generation": mean_asi_by_condition([(arms["ingen"], 1)], INGEN),
        "manipulated_post_hoc": mean_asi_by_condition([(arms["fake"], 1)], POSTHOC),
        "real_post_hoc": mean_asi_by_condition([(arms["real"], 1)], POSTHOC),
        "synthetic_post_hoc": mean_asi_by_condition([(arms["syn_identity"], 1), (arms["syn_newgen_identity"], 1)], POSTHOC),
    }
    sev_map = {"vae": lambda v: "q" + v, "diffusion_modern": lambda v: "str" + v.replace(".", "_"),
               "edit": lambda v: {"Qwen-Image-Edit": "qwen_image_edit_fast", "FLUX.2-klein": "flux2_klein_fast"}[v],
               "unmarker": lambda v: "default"}
    paper_asi = {}
    for a, r in grid_rows.items():
        sevs_txt = r["cells"][2]["text"]
        sev_vals = ["--"] if sevs_txt in ("–", "--") else sevs_txt.split(", ")
        ph = r["cells"][3]["value"]
        igv = r["cells"][4]["value"]
        ph = ph if isinstance(ph, list) else [ph]
        igv = igv if isinstance(igv, list) else [igv]
        for i, v in enumerate(sev_vals):
            s = sev_map[a](v) if a in sev_map else v
            paper_asi[cond_id(a, s)] = {"parameter": r["cells"][1]["text"], "value": None if v == "--" else v,
                                        "post_hoc": ph[i], "in_generation": igv[i], "row": r}
    for a, r in chain_rows.items():
        paper_asi[cond_id(a, "chain")] = {"parameter": None, "value": None, "post_hoc": r["values"][0], "in_generation": r["values"][1], "row": r}
    attacks = []
    grid_order = list(paper_asi.keys())
    bad_asi = []
    for i, (lv, a, s) in enumerate(allc):
        cid = cond_id(a, s)
        pa = paper_asi.get(cid)
        is_chain = a in CHAIN_NAME
        if is_chain:
            stages = chain_rows[a]["cells"][2]["text"]
            name = CHAIN_NAME[a]
        else:
            stages = None
            v = pa["value"]
            name = {"vae": f"VAE regeneration, quality factor {v}", "edit": f"prompt-based edit ({v})", "unmarker": "UnMarker",
                    "diffusion_modern": f"diffusion regeneration, strength {v}"}.get(a, f"{TYPE_DISPLAY[a]} {v}")
        e = {"id": cid, "attack_type": a, "severity": s, "category": LEVEL2CAT[lv], "category_name": CATEGORY_INFO[LEVEL2CAT[lv]]["name"],
             "type_name": TYPE_DISPLAY[a], "name": name, "short_label": f"{HEAT_SHORT[a]} {HEAT_SEV.get(s, s)}".strip(),
             "parameter": pa["parameter"], "value": pa["value"], "is_chain": is_chain,
             "chain_name": CHAIN_NAME.get(a), "steps": stages.split(" → ") if stages else None, "stages_text": stages,
             "mean_asi": {"post_hoc_synthetic_matched": pa["post_hoc"], "in_generation_synthetic_matched": pa["in_generation"],
                          "source": "paper:tables/tab_chains.tex" if is_chain else "paper:tables/tab_attackgrid.tex"},
             "mean_asi_computed": {k: r4(v.get(cid), 5) for k, v in comp.items()},
             "heatmap_order": i, "paper_table_order": grid_order.index(cid)}
        if is_chain and a in syn_rows:
            e["mean_asi"]["post_hoc_manipulated"] = syn_rows[a]["values"][0]
            e["mean_asi"]["post_hoc_manipulated_source"] = "paper:tables/tab_synergy.tex"
            if f"{comp['manipulated_post_hoc'][cid]:.3f}" != f"{syn_rows[a]['values'][0]:.3f}":
                bad_asi.append((cid, "manipulated", comp["manipulated_post_hoc"][cid], syn_rows[a]["values"][0]))
        for key, pkey in [("synthetic_matched_post_hoc", "post_hoc"), ("synthetic_matched_in_generation", "in_generation")]:
            cv = comp[key].get(cid)
            if cv is None or f"{cv:.3f}" != f"{pa[pkey]:.3f}":
                bad_asi.append((cid, key, cv, pa[pkey]))
        attacks.append(e)
    check("attacks", "52 conditions: 30 C1, 8 C2, 8 C3, 6 C4", len(attacks) == 52 and collections.Counter(x["category"] for x in attacks) == {"C1": 30, "C2": 8, "C3": 8, "C4": 6},
          str(dict(collections.Counter(x["category"] for x in attacks))))
    check("attacks", "every heat-map condition maps to a row of tab_attackgrid or tab_chains", len(paper_asi) == 52 and all(cond_id(a, s) in paper_asi for _, a, s in allc),
          f"{len(paper_asi)} conditions parsed from the two tables")
    check("attacks", "mean ASI recomputed from robust_curves.csv (matched post-hoc identity arm, in-gen eval_v2; manipulated for chains) equals tab_attackgrid / tab_chains / tab_synergy",
          not bad_asi, f"mismatches: {bad_asi}" if bad_asi else "52 x 2 matched-cohort values + 14 manipulated chain values equal at 3 decimals")
    out = {
        "_meta": meta(["paper:tables/tab_attackgrid.tex", "paper:tables/tab_chains.tex", "paper:tables/tab_synergy.tex",
                       f"repo:{DIR_SYN_MATCHED}/robust_curves.csv", f"repo:{DIR_INGEN}/robust_curves.csv", f"repo:{DIR_FAKE_ID}/robust_curves.csv",
                       f"repo:{DIR_REAL_ID}/robust_curves.csv", f"repo:{DIR_SYN_ID}/robust_curves.csv", f"repo:{DIR_SYN_NG}/robust_curves.csv"]),
        "categories": [{"id": k, **v, "n_conditions": sum(1 for x in attacks if x["category"] == k)} for k, v in CATEGORY_INFO.items()],
        "attack_types": [{"key": a, "name": TYPE_DISPLAY[a], "category": CAT_OF[a], "is_chain": a in CHAIN_NAME} for a in ATTACK_TYPES],
        "mean_asi_columns": {
            "post_hoc_synthetic_matched": "Paper: 'Mean ASI, post-hoc (synthetic)' -- averaged over images and the 11 post-hoc methods on the matched synthetic cohort (tab_attackgrid / tab_chains caption).",
            "in_generation_synthetic_matched": "Paper: 'Mean ASI, in-generation (synthetic)' -- averaged over images and the 4 in-generation methods on the same cohort.",
            "post_hoc_manipulated": "Paper (chains only): 'Mean ASI' column of tab_synergy, measured on the manipulated category.",
            "mean_asi_computed": "Computed by build_data.py from robust_curves.csv as the mean over methods of the condition-level mean ASI; synthetic_post_hoc pools the two synthetic identity arms (1,593 images) per method by n_pos. The two synthetic_matched values reproduce the paper columns.",
        },
        "asi_definition": "ASI (attack-strength index) = LPIPS distance between the attacked image and its pre-attack image, per image. Cropped images are scaled back to the reference size; rotated images keep their transformed canvas.",
        "conditions": attacks,
    }
    return out


# ----------------------------------------------------------------------------------------------
# Methods
# ----------------------------------------------------------------------------------------------
def parse_bib():
    with open(P(BIB), encoding="utf-8") as fh:
        s = fh.read()
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", s):
        start = s.index("{", m.start())
        end = match_brace(s, start)
        body = s[m.end():end]
        f = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{", body):
            j = fm.end() - 1
            k = match_brace(body, j)
            f[fm.group(1).lower()] = re.sub(r"\s+", " ", body[j + 1:k].replace("{", "").replace("}", "")).strip()
        entries[m.group(2)] = {"type": m.group(1).lower(), **f}
    return entries


def build_methods(lb):
    T = {t["id"]: t for t in lb}
    tm = T["tab_methods"]
    bib = parse_bib()
    ph_rows, ig_rows = {}, {}
    for r in tm["rows"]:
        c = r["cells"]
        k = NAME2KEY.get(c[0]["text"])
        if k:
            ph_rows[k] = {"bits_text": c[1]["text"], "message": c[2]["text"], "cite": re.findall(r"\\citep\{([^}]+)\}", c[0]["tex"])}
        k2 = NAME2KEY.get(c[3]["text"])
        if k2:
            ig_rows[k2] = {"payload_text": c[4]["text"], "gens": [c[i]["text"] == "✓" for i in (5, 6, 7)],
                           "cite": re.findall(r"\\citep\{([^}]+)\}", c[3]["tex"])}
    t3 = {r["method_key"]: r["cells"][1]["text"] for r in T["tab_tier3_main"]["rows"] if r["method_key"]}
    BITS = {"cin": 30, "pimog": 30, "wam": 32, "trustmark": 48, "editguard": 64, "vine": 100, "invismark": 100, "omniguard": 100,
            "mbrs": 256, "videoseal": 256, "pixelseal": 256}
    methods = []
    gens = ["SD2.1", "SDXL", "FLUX.1-dev"]
    for i, m in enumerate(POSTHOC + INGEN):
        if m in POSTHOC:
            row = ph_rows[m]
            bits = int(row["bits_text"])
            check("methods", f"{SHORTNAME[m]}: payload bits in tab:methods = {BITS[m]}", bits == BITS[m], row["bits_text"])
            cls = None if row["message"] == "N/A" else row["message"]
            key = row["cite"][0] if row["cite"] else None
            e = {"key": m, "name": FULLNAME[m], "short_name": SHORTNAME[m], "family": "post-hoc", "payload_bits": bits,
                 "payload_text": f"{bits} bits",
                 "message_type": "identity only" if cls is None else f"{cls} sentence",
                 "message_class": cls, "sentence_evaluation": cls is not None, "generators": None,
                 "evaluation_settings": ["identity attribution: open-set, 100-identity codebook"] +
                                        (["message recovery: bit agreement with the embedded sentence"] if cls else []),
                 "figure_style": {"color": FIG_COLOR[m], "line": FIG_STYLE[m]}}
            if m in ("trustmark", "vine"):
                e["codebook_note"] = {"trustmark": "identity codewords are random alphanumeric strings encoded with the native encoder; 6 of 48 bit positions are fixed",
                                      "vine": "identity codewords are random alphanumeric strings encoded with the native encoder; 16 of 100 bit positions are fixed"}[m]
        else:
            row = ig_rows[m]
            key = row["cite"][0] if row["cite"] else None
            cls = t3.get(m)
            e = {"key": m, "name": FULLNAME[m], "short_name": SHORTNAME[m], "family": "in-generation",
                 "payload_bits": None if m == "ring_id" else 256, "payload_text": row["payload_text"],
                 "message_type": "ring key (one of 1,024 native keys)" if m == "ring_id" else f"{cls} sentence",
                 "message_class": cls, "sentence_evaluation": m != "ring_id",
                 "generators": [g for g, ok in zip(gens, row["gens"]) if ok],
                 "evaluation_settings": (["identity attribution: its 1,024 native ring keys"] if m == "ring_id"
                                         else ["message recovery: bit agreement with the embedded sentence"])}
            if m == "prc":
                e["payload_note"] = "256 of its 512 payload bits carry the message"
            check("methods", f"{SHORTNAME[m]}: available on SD2.1, SDXL and FLUX.1 in tab:methods", all(row["gens"]), str(row["gens"]))
        if e["message_class"]:
            e["message_chars"] = {"short": 11, "long": 28}[e["message_class"]]
            e["message_encoded_bits"] = {"short": 55, "long": 140}[e["message_class"]]
        b = bib.get(key, {})
        e["citation"] = {"bib_key": key, "title": b.get("title"), "venue": b.get("booktitle") or b.get("journal"), "year": b.get("year"),
                         "author": b.get("author")}
        e["order"] = i
        methods.append(e)
    check("methods", "sentence classes: short for EditGuard/VINE/InvisMark/OmniGuard, long for MBRS/VideoSeal/PixelSeal/GS/T2SMark/PRC",
          all(x["message_class"] == ("short" if x["key"] in ("editguard", "vine", "invismark", "omniguard") else "long")
              for x in methods if x["key"] in SEM_PH + SEM_IG) and all(x["message_class"] is None for x in methods if x["key"] in ("cin", "pimog", "wam", "trustmark", "ring_id")),
          str({x["key"]: x["message_class"] for x in methods}))
    out = {
        "_meta": meta([f"paper:{MAIN_TEX} (table tab:methods)", f"paper:{BIB}", "paper:tables/tab_tier3_main.tex"]),
        "message_encoding": {"alphabet": "abcdefghijklmnopqrstuvwxyz .,'-?", "bits_per_char": 5,
                             "short": {"chars": 11, "bits": 55, "questions_per_message": 3}, "long": {"chars": 28, "bits": 140, "questions_per_message": 4},
                             "note": "Messages are padded with spaces to the class length, encoded at 5 bits per character, then zero-padded to the method's capacity. Methods with fewer than 64 bits carry identity codewords only."},
        "counts": {"post_hoc": len(POSTHOC), "in_generation": len(INGEN), "generator_method_pairs": sum(len(x["generators"] or []) for x in methods)},
        "links_note": "Paper and code URLs are filled in by another step; citation fields come from the paper's bib.",
        "methods": methods,
    }
    return out


# ----------------------------------------------------------------------------------------------
# Stats
# ----------------------------------------------------------------------------------------------
STATS = [
    ("images.real", 25864, "25,864 real images (MultiFakeVerse; sources EMOTIC, PIC 2.0, PIPA, PISC)", r"25,864 real"),
    ("images.manipulated", 15000, "15,000 manipulated images (MultiFakeVerse)", r"15,000 manipulated"),
    ("images.synthetic", 12665, "12,665 synthetic images from 6 generators", r"12,665"),
    ("images.unwatermarked_total", 53529, "53,529 unwatermarked images", r"53,529"),
    ("images.watermarked_total", 739818, "739,818 watermarked images", r"739,818"),
    ("evaluation.real", 1600, "1,600 real evaluation images", r"1,600 real"),
    ("evaluation.manipulated", 1600, "1,600 manipulated evaluation images", r"1,600 manipulated"),
    ("evaluation.synthetic", 1593, "1,593 synthetic evaluation images", r"1,593 synthetic"),
    ("evaluation.unwatermarked", 4793, "4,793 unwatermarked evaluation images", r"4,793"),
    ("evaluation.watermarked", 91046, "91,046 watermarked evaluation images", r"91,046"),
    ("evaluation.attacked_watermarked", 4555449, "4,555,449 attacked-watermarked images", r"4,555,449"),
    ("evaluation.attacked_unwatermarked", 241826, "241,826 attacked-unwatermarked images", r"241,826"),
    ("evaluation.matched_cohort", 1193, "1,193-image synthetic cohort matched by generator, prompt and seed", r"1,193"),
    ("evaluation.unmarker_per_subclass", 50, "UnMarker runs on a nested subset of 50 images per subclass", r"50 images per subclass"),
    ("evaluation.images_per_subclass", 200, "evaluation subsets are content-stratified with 200 images per subclass and category", r"200 images per subclass"),
    ("methods.post_hoc", 11, "11 post-hoc methods", r"11 post-hoc"),
    ("methods.in_generation", 4, "4 in-generation methods", r"4 in-generation"),
    ("methods.generator_method_pairs", 12, "12 in-generation generator-method pairs", r"12 generator-method pairs"),
    ("attacks.conditions", 52, "52 attack conditions", r"52 attack conditions"),
    ("attacks.categories", 4, "four attack categories", r"four\s+(attack\s+)?categories"),
    ("attacks.c1_perturbations", 10, "C1: 10 perturbations x 3 settings", r"10 different image perturbations"),
    ("attacks.c3_sequences", 8, "C3: 8 predefined sequences", r"8 predefined sequences"),
    ("attacks.c4_sequences", 6, "C4: 6 predefined sequences", r"6 predefined sequences"),
    ("metrics.fpr_target", 0.01, "TPR at 1% FPR, thresholds calibrated on unwatermarked and attacked-unwatermarked negatives", r"TPR@1\\%FPR"),
    ("metrics.asi_budget", 0.2, "AURSC over ASI [0, 0.2]; Observed Min@0.2", r"\[0,0\.2\]"),
    ("metrics.identity_codebook", 100, "open-set attribution over 100 candidate identities", r"100 (candidate )?identities"),
    ("metrics.ringid_keys", 1024, "RingID attribution over its 1,024 native keys", r"1,024"),
    ("metrics.readers", 5, "QSR reader sensitivity over five frozen language models", r"five (frozen )?(language models|readers)"),
    ("metrics.primary_reader", "Qwen2.5-7B-Instruct", "primary QSR reader", r"Qwen2\.5-7B-Instruct"),
    ("metrics.question_instances", "7.24 million", "question instances scored by each reader", r"7\.24 million"),
    ("metrics.reader_method_attack_pairs", 2385, "method-attack pairs in the reader agreement analysis", r"2,385"),
    ("corpus.messages", 240, "240 messages, 120 per length class", r"240 messages"),
    ("corpus.calibration_negatives_matched", 61077, "pooled calibration negatives per method on the matched cohort", r"61,077"),
    ("generation.resolution", "SD2.1 512 px, others 1024 px", "generation settings", r"512~px"),
]


def build_stats(text_lines, attacks, methods):
    def lines_for(pat):
        rx = re.compile(pat)
        return [i + 1 for i, ln in enumerate(text_lines) if rx.search(ln)]
    items = []
    for key, value, text, pat in STATS:
        ls = lines_for(pat)
        check("stats", f"{key} = {value} stated in the paper", bool(ls), f"lines {ls[:6]}" if ls else f"pattern {pat!r} not found")
        items.append({"key": key, "value": value, "text": text, "paper_lines": ls[:8]})
    gen_line = lines_for(r"Qwen-Image\\citep")
    sub_line = lines_for(r"single person's portrait")
    cat_counts = collections.Counter(a["category"] for a in attacks["conditions"])
    derived = [
        {"key": "attacks.per_category", "value": dict(cat_counts), "text": "conditions per attack category (from attacks.json)", "derived_from": "data/attacks.json"},
        {"key": "attacks.types_for_aursc", "value": len(ATTACK_TYPES), "text": "attack types averaged in AURSC: 14 single attack types (tab:attackgrid) + 14 chains (tab:chains)",
         "derived_from": "paper Appendix 'AURSC' paragraph; the number 28 is not printed in the paper"},
        {"key": "evaluation.images_total", "value": 1600 + 1600 + 1593, "text": "post-hoc evaluation images (1,600 + 1,600 + 1,593); equals the 4,793 unwatermarked evaluation images", "derived_from": "sum"},
    ]
    check("stats", "1,600 + 1,600 + 1,593 = 4,793 unwatermarked evaluation images", 1600 + 1600 + 1593 == 4793, "")
    out = {
        "_meta": meta([f"paper:{MAIN_TEX}"]),
        "note": "paper_lines are line numbers in the paper's main tex file (iclr2027_conference.tex) at the commit in _meta; comment lines are excluded from the search.",
        "items": items,
        "lists": {
            "generators": {"value": ["SD2.1", "SDXL", "FLUX.1-dev", "Qwen-Image", "HiDream-I1", "HunyuanImage-3.0 (distilled)"], "paper_lines": gen_line},
            "in_generation_generators": {"value": ["SD2.1", "SDXL", "FLUX.1-dev"], "paper_lines": lines_for(r"12 generator-method pairs")},
            "subclasses": {"value": ["single person's portrait", "group of people", "sports scene", "indoor scene", "food and drink", "vehicle", "landscape", "object"],
                           "paper_lines": sub_line},
            "real_sources": {"value": ["EMOTIC", "PIC 2.0", "PIPA", "PISC"], "paper_lines": lines_for(r"Real images come from EMOTIC")},
            "image_states": {"value": ["unwatermarked", "watermarked", "attacked-watermarked", "attacked-unwatermarked"],
                             "paper_lines": lines_for(r"unwatermarked,\s*watermarked,\s*attacked-watermarked")},
            "readers": {"value": ["Qwen2.5-7B-Instruct (primary)", "Qwen3.5-9B", "Ministral-8B-Instruct-2410", "Gemma-3-12B-IT", "Llama-3.1-8B-Instruct"],
                        "paper_lines": lines_for(r"Ministral-8B-Instruct-2410")},
            "editors": {"value": ["Qwen-Image-Edit", "FLUX.2-klein"], "paper_lines": lines_for(r"FLUX\.2-klein")},
        },
        "derived": derived,
        "method_counts_from_methods_json": methods["counts"],
    }
    return out


# ----------------------------------------------------------------------------------------------
# Paper-text claims checked against the heat-map grids and computed ASI
# ----------------------------------------------------------------------------------------------
def text_claims(heat, attacks_out, lb):
    g = heat["grids"]
    cid = [c["id"] for c in heat["conditions"]]
    A = {c["id"]: c for c in attacks_out["conditions"]}

    def col(cat, fam, c, methods=None):
        grid = g[cat]["post_hoc" if fam == "ph" else "in_generation"]
        ms = methods or list(grid)
        vals = [grid[m][cid.index(c)] for m in ms]
        return [v for v in vals if v is not None]

    def cl(name, got, want, nd=1):
        check("paper text", name, round(got, nd) == want, f"computed {got:.4f}, paper {want}")

    cl("Intro/5.2: manipulated, Gaussian noise sigma=10, mean post-hoc TPR@1%FPR 99.8%", statistics.mean(col("manipulated", "ph", "gnoise:10")), 99.8)
    cl("Intro/5.2: manipulated, diffusion regeneration 0.2, mean post-hoc TPR@1%FPR 24.7%", statistics.mean(col("manipulated", "ph", "diffusion_modern:str0_2")), 24.7)
    cl("5.2: manipulated mean ASI of Gaussian noise sigma=10 is 0.233", A["gnoise:10"]["mean_asi_computed"]["manipulated_post_hoc"], 0.233, 3)
    cl("5.2: manipulated mean ASI of diffusion regeneration 0.2 is 0.243", A["diffusion_modern:str0_2"]["mean_asi_computed"]["manipulated_post_hoc"], 0.243, 3)
    cl("5.2: in-generation, Gaussian noise sigma=5, mean TPR@1%FPR 98.5%", statistics.mean(col("synthetic", "ig", "gnoise:5")), 98.5)
    cl("5.2: in-generation, diffusion regeneration 0.2, mean TPR@1%FPR 74.7%", statistics.mean(col("synthetic", "ig", "diffusion_modern:str0_2")), 74.7)
    cl("5.2: in-generation mean ASI of Gaussian noise sigma=5 is 0.161", A["gnoise:5"]["mean_asi"]["in_generation_synthetic_matched"], 0.161, 3)
    cl("5.2: in-generation mean ASI of diffusion regeneration 0.2 is 0.154", A["diffusion_modern:str0_2"]["mean_asi"]["in_generation_synthetic_matched"], 0.154, 3)
    cl("App: manipulated, Gaussian noise sigma=20, mean ASI 0.459", A["gnoise:20"]["mean_asi_computed"]["manipulated_post_hoc"], 0.459, 3)
    cl("App: manipulated, Gaussian noise sigma=20, TPR@1%FPR 91.1%", statistics.mean(col("manipulated", "ph", "gnoise:20")), 91.1)
    cl("App: manipulated, diffusion regeneration 0.3, mean ASI 0.317", A["diffusion_modern:str0_3"]["mean_asi_computed"]["manipulated_post_hoc"], 0.317, 3)
    cl("App: manipulated, diffusion regeneration 0.3, TPR@1%FPR 18.7%", statistics.mean(col("manipulated", "ph", "diffusion_modern:str0_3")), 18.7)
    cl("App: in-generation, Gaussian noise sigma=20, mean ASI 0.630", A["gnoise:20"]["mean_asi"]["in_generation_synthetic_matched"], 0.630, 3)
    cl("App: in-generation, Gaussian noise sigma=20, TPR@1%FPR 89.6%", statistics.mean(col("synthetic", "ig", "gnoise:20")), 89.6)
    # VAE regeneration, stronger setting (quality factor 1, higher ASI)
    below = {cat: sum(1 for v in col(cat, "ph", "vae:q1") if v < 10) for cat in ("manipulated", "real", "synthetic")}
    check("paper text", "App: at the stronger VAE setting (q1), 6-7 of the 11 post-hoc methods fall below 10% in each category",
          all(v in (6, 7) for v in below.values()), str(below))
    cl("App: VAE q1 in-generation mean 63%", statistics.mean(col("synthetic", "ig", "vae:q1")), 63, 0)
    cl("App: VAE q1 Gaussian Shading 93%", col("synthetic", "ig", "vae:q1", ["gaussian_shading"])[0], 93, 0)
    cl("App: VAE q1 PRC 22%", col("synthetic", "ig", "vae:q1", ["prc"])[0], 22, 0)
    above = {cat: sorted(m for m in POSTHOC if g[cat]["post_hoc"][m][cid.index("diffusion_modern:str0_3")] > 20) for cat in ("manipulated", "real", "synthetic")}
    inter = set.intersection(*[set(v) for v in above.values()])
    check("paper text", "App: at diffusion 0.3 only WAM and VINE stay above 20% in every category", inter == {"wam", "vine"}, str(above))
    means = {cat: statistics.mean(col(cat, "ph", "diffusion_modern:str0_3")) for cat in ("manipulated", "real", "synthetic")}
    check("paper text", "App: diffusion 0.3 post-hoc mean 12-19% per category", all(12 <= round(v) <= 19 for v in means.values()), str({k: round(v, 2) for k, v in means.items()}))
    trio = [col("synthetic", "ig", "diffusion_modern:str0_3", [m])[0] for m in ("gaussian_shading", "ring_id", "t2smark")]
    check("paper text", "App: diffusion 0.3 Gaussian Shading, RingID, T2SMark retain 73-100%", all(73 <= round(v) <= 100 for v in trio), str([round(v, 2) for v in trio]))
    cl("App: diffusion 0.3 in-generation mean 68%", statistics.mean(col("synthetic", "ig", "diffusion_modern:str0_3")), 68, 0)
    unm = {cat: sum(1 for v in col(cat, "ph", "unmarker:default") if v < 10) for cat in ("manipulated", "synthetic")}
    keep = {cat: [m for m in ("wam", "invismark") if round(g[cat]["post_hoc"][m][cid.index("unmarker:default")]) == 100] for cat in ("manipulated", "synthetic")}
    check("paper text", "App: UnMarker: 7 of 11 post-hoc methods below 10%, WAM and InvisMark at 100% (manipulated and synthetic grids)",
          all(v == 7 for v in unm.values()) and all(len(v) == 2 for v in keep.values()), f"below 10%: {unm}; at 100%: {keep}")
    ig_unm = [col("synthetic", "ig", "unmarker:default", [m])[0] for m in ("gaussian_shading", "t2smark", "prc")]
    check("paper text", "App: UnMarker: Gaussian Shading, T2SMark, PRC fall to 1-5%", all(1 <= round(v) <= 5 for v in ig_unm), str([round(v, 2) for v in ig_unm]))
    # tab_unmarker equals heat-map cells
    T = {t["id"]: t for t in lb}
    bad = []
    for r in T["tab_unmarker"]["rows"]:
        m = r["method_key"]
        v = r["values"]
        if m in POSTHOC:
            for ci, cat in enumerate(("manipulated", "real", "synthetic")):
                for k, c in enumerate(("unmarker:default", "unmarker_resize_jpeg_unmarkshare:chain")):
                    h = g[cat]["post_hoc"][m][cid.index(c)]
                    t = v[2 * ci + k]
                    if (h is None) != (t is None) or (h is not None and f"{h:.1f}" != f"{t:.1f}"):
                        bad.append((m, cat, c, h, t))
        else:
            for k, c in enumerate(("unmarker:default", "unmarker_resize_jpeg_unmarkshare:chain")):
                h = g["synthetic"]["in_generation"][m][cid.index(c)]
                if f"{h:.1f}" != f"{v[4 + k]:.1f}":
                    bad.append((m, c, h, v[4 + k]))
    check("heatmap", "tab_unmarker (rows file) equals the heat-map cells for UnMarker and unmarkshare (all categories, both families)", not bad,
          f"mismatches: {bad}" if bad else "66 + 8 cells equal (nulls where the table prints --)")
    # tab_levels TPR block (post-hoc rows) from the grids + n, make_tables.py tpr_levels()
    lv = {r["label"]: r for r in T["tab_levels"]["rows"] if r["group"] == 0}
    bad = []
    for cat in ("manipulated", "real", "synthetic"):
        per = []
        for m in POSTHOC:
            acc = collections.defaultdict(lambda: [0.0, 0.0])
            for i, c in enumerate(heat["conditions"]):
                t, n = g[cat]["post_hoc"][m][i], g[cat]["post_hoc_n"][m][i]
                if t is None or n is None:
                    continue
                for k in (c["category"], "All"):
                    acc[k][0] += t * n
                    acc[k][1] += n
            per.append({k: v[0] / v[1] for k, v in acc.items()})
        want = lv[f"post-hoc, {cat}"]["values"]
        for j, k in enumerate(("C1", "C2", "C3", "C4", "All")):
            got = statistics.mean(p[k] for p in per)
            if f"{got:.1f}" != f"{want[j + 1]:.1f}":
                bad.append((cat, k, round(got, 3), want[j + 1]))
    check("heatmap", "post-hoc TPR rows of tab_levels (C1-C4, All) recomputed from the heat-map grids and n (n-weighted per method, then mean over methods)",
          not bad, f"mismatches: {bad}" if bad else "15 values equal at 1 decimal")
    # in-generation per-category means vs tab_crossfamily (informational: tab_crossfamily in-gen rows come from T3_crossfamily_synthetic_tpr.csv)
    cf = {(r["family"], r["method_key"], r["group"]): r for r in T["tab_crossfamily"]["rows"]}
    diffs = []
    for m in INGEN:
        acc = collections.defaultdict(lambda: [0.0, 0.0])
        for i, c in enumerate(heat["conditions"]):
            t, n = g["synthetic"]["in_generation"][m][i], g["synthetic"]["in_generation_n"][m][i]
            for k in (c["category"], "All"):
                acc[k][0] += t * n
                acc[k][1] += n
        row = cf.get(("in-generation", m, 0)) or cf.get(("in-generation", m, 1))
        for j, k in enumerate(("C1", "C2", "C3", "C4", "All")):
            got = acc[k][0] / acc[k][1]
            diffs.append(abs(got - row["values"][j + 1]))
            if f"{got:.1f}" != f"{row['values'][j + 1]:.1f}":
                diffs.append(("mismatch", m, k, round(got, 3), row["values"][j + 1]))
    mism = [d for d in diffs if isinstance(d, tuple)]
    check("heatmap", "in-generation C1-C4/All of tab_crossfamily recomputed from the heat-map grid (n-weighted)", not mism,
          f"mismatches: {mism}" if mism else "20 values equal at 1 decimal")


def crossfamily_identity_block(lb):
    """Recompute the identity block of tab_crossfamily (C1-C4, All) as TPR@1%FPR and as open-set attribution accuracy."""
    T = {t["id"]: t for t in lb}
    rows = {r["method_key"]: r for r in T["tab_crossfamily"]["rows"] if r["group"] == 0}

    def per_level(rel, method, metric_file, col, n_eval):
        acc = collections.defaultdict(lambda: [0.0, 0.0])
        for r in rd(f"{rel}/{metric_file}"):
            if r["method"] != method or r["far"] != "0.01" or (n_eval and r["n_eval"] != n_eval) or r["attack"] == "none":
                continue
            n = int(r["n_pos"])
            for k in (CAT_OF[r["attack"]], "All"):
                acc[k][0] += n * float(r[col])
                acc[k][1] += n
        return {k: 100 * v[0] / v[1] for k, v in acc.items()}

    bad_tpr, attr_diff = [], []
    for m in POSTHOC + ["ring_id"]:
        rel, ne = (DIR_SYN_MATCHED, "100") if m in POSTHOC else (DIR_INGEN, "1024")
        tpr = per_level(rel, m, "detection.csv", "tpr", ne)
        att = per_level(rel, m, "attribution.csv", "openset_acc", ne)
        want = rows[m]["values"]
        for j, k in enumerate(("C1", "C2", "C3", "C4", "All")):
            if f"{tpr[k]:.1f}" != f"{want[j + 1]:.1f}":
                bad_tpr.append((m, k, round(tpr[k], 2), want[j + 1]))
        attr_diff.append((m, round(att["All"], 1), want[5]))
    check("leaderboards", "tab_crossfamily identity block (C1-C4, All) equals TPR@1%FPR recomputed from detection.csv (matched identity arm; RingID eval_v2)",
          not bad_tpr, f"mismatches: {bad_tpr}" if bad_tpr else "60 values equal at 1 decimal")
    n_diff = sum(1 for m, a, t in attr_diff if f"{a:.1f}" != f"{t:.1f}")
    check("leaderboards", "tab_crossfamily caption: identity block is described as open-set attribution accuracy, but the numbers are TPR@1%FPR "
          "(caption_site corrected; flagged for the authors)", True,
          f"{n_diff} of 12 'All' values differ from the attribution accuracy; (method, attribution All, table All): {attr_diff}")


def table_text_claims(lb, heat):
    T = {t["id"]: t for t in lb}
    mean = statistics.mean

    def cl(name, got, want, nd):
        check("paper text", name, round(got, nd) == want, f"computed {got:.4f}, paper {want}")

    cf = T["tab_crossfamily"]["rows"]
    msg = [r for r in cf if r["group"] == 1]
    ph = [r for r in msg if r["family"] == "post-hoc"]
    ig = [r for r in msg if r["family"] == "in-generation"]
    cl("5.3: mean attacked TPR@1%FPR, post-hoc (message block) 75.8%", mean(r["values"][5] for r in ph), 75.8, 1)
    cl("5.3: mean attacked TPR@1%FPR, in-generation 73.6%", mean(r["values"][5] for r in ig), 73.6, 1)
    check("paper text", "5.3: method-level ranges 47.7-89.7 (post-hoc) and 63.6-80.7 (in-generation)",
          (min(r["values"][5] for r in ph), max(r["values"][5] for r in ph), min(r["values"][5] for r in ig), max(r["values"][5] for r in ig)) == (47.7, 89.7, 63.6, 80.7), "")
    cl("Intro/5.3: C2 mean TPR@1%FPR in-generation 68.4%", mean(r["values"][2] for r in ig), 68.4, 1)
    cl("Intro/5.3: C2 mean TPR@1%FPR post-hoc 53.3%", mean(r["values"][2] for r in ph), 53.3, 1)
    t3 = T["tab_tier3_main"]["rows"]
    p3 = [r for r in t3 if r["family"] == "post-hoc"]
    i3 = [r for r in t3 if r["family"] == "in-generation"]
    cl("5.3: mean QSR post-hoc 0.454", mean(r["values"][5] for r in p3), 0.454, 3)
    cl("5.3: mean QSR in-generation 0.635", mean(r["values"][5] for r in i3), 0.635, 3)
    check("paper text", "5.3: QSR ranges 0.104-0.629 (post-hoc) and 0.527-0.693 (in-generation)",
          (min(r["values"][5] for r in p3), max(r["values"][5] for r in p3), min(r["values"][5] for r in i3), max(r["values"][5] for r in i3)) == (0.104, 0.629, 0.527, 0.693), "")
    cl("5.3: C2 mean QSR in-generation 0.354", mean(r["values"][2] for r in i3), 0.354, 3)
    cl("5.3: C2 mean QSR post-hoc 0.154", mean(r["values"][2] for r in p3), 0.154, 3)
    q = {r["method_key"]: r["values"][3] for r in t3}
    check("paper text", "5.3: C3 QSR VideoSeal 0.822, PixelSeal 0.811, highest in-generation 0.727",
          (q["videoseal"], q["pixelseal"], max(q[m] for m in SEM_IG)) == (0.822, 0.811, 0.727), str((q["videoseal"], q["pixelseal"], max(q[m] for m in SEM_IG))))
    px = next(r for r in t3 if r["method_key"] == "pixelseal")["values"]
    check("paper text", "5.5: PixelSeal bit-AURSC 0.958, sem-AURSC 0.821", (px[7], px[6]) == (0.958, 0.821), str((px[7], px[6])))
    cid = [c["id"] for c in heat["conditions"]]
    strong = [heat["grids"]["synthetic"]["in_generation"][m][cid.index(c)] for m in INGEN for c in ("crop:0.5", "rotation:15")]
    check("paper text", "5.3: in-generation methods fall to 0-3% TPR@1%FPR under strong cropping (0.5) or rotation (15)",
          all(round(v) <= 3 for v in strong), str([round(v, 2) for v in strong]))
    m3 = T["tab_main3"]["rows"]
    unatt = [r["values"][1 + 5 * c] for r in m3 for c in range(3)]
    check("paper text", "5.1: all 11 post-hoc methods >= 99.9% TPR@1%FPR before attack in all three categories", min(unatt) >= 99.9, f"min {min(unatt)}")
    low = [sorted(r["method_key"] for r in m3 if r["values"][3 + 5 * c] < 0.07) for c in range(3)]
    check("paper text", "5.1: the same eight post-hoc methods fall below 7% (Obs. Min@0.2) in each image category",
          all(len(l) == 8 for l in low) and low[0] == low[1] == low[2], str(low))
    ma = {(r["label"], g["label"]): r["values"] for r in T["tab_message_agg"]["rows"] for g in [T["tab_message_agg"]["row_groups"][r["group"]]]}
    cl("5.5: matched post-hoc mean bit accuracy 0.835", ma[("post-hoc, synthetic (matched)", "Bit Acc.")][5], 0.835, 3)
    cl("5.5: matched post-hoc complete-message recovery 0.396", ma[("post-hoc, synthetic (matched)", "Msg. Rec.")][5], 0.396, 3)
    cl("5.5: in-generation bit accuracy 0.883", ma[("in-generation, synthetic (matched)", "Bit Acc.")][5], 0.883, 3)
    cl("5.5: in-generation complete-message recovery 0.610", ma[("in-generation, synthetic (matched)", "Msg. Rec.")][5], 0.610, 3)
    cl("Intro: manipulated post-hoc bit accuracy 0.83", ma[("post-hoc, manipulated", "Bit Acc.")][5], 0.83, 2)
    cl("Intro: manipulated post-hoc complete-message recovery 0.39", ma[("post-hoc, manipulated", "Msg. Rec.")][5], 0.39, 2)
    cl("Intro: manipulated post-hoc QSR 0.44", ma[("post-hoc, manipulated", "QSR")][5], 0.44, 2)
    pr = {r["label"]: r["values"] for r in T["tab_partial"]["rows"]}
    check("paper text", "5.5: 27.3% (post-hoc, matched) and 5.1% (in-generation) of correct answers from inexact messages",
          (pr["post-hoc, synthetic (matched)"][4], pr["in-generation, synthetic (matched)"][4]) == (27.3, 5.1), "")
    rm = [r["values"] for r in T["tab_readers_main"]["rows"] if r["label"] != "Max − min"]
    check("paper text", "5.5: reader range of mean attacked QSR 0.427-0.507 (post-hoc matched) and 0.623-0.647 (in-generation)",
          (min(v[3] for v in rm), max(v[3] for v in rm), min(v[4] for v in rm), max(v[4] for v in rm)) == (0.427, 0.507, 0.623, 0.647), "")
    lv_ig = next(r for r in T["tab_levels"]["rows"] if r["group"] == 0 and r["family"] == "in-generation")["values"]
    ig4 = [r for r in cf if r["family"] == "in-generation"]
    check("leaderboards", "tab_levels in-generation TPR row is the mean over all 4 in-generation methods of tab_crossfamily (RingID included), "
          "although the caption says 'in-generation methods on their sentence-carrying images'",
          abs(mean(r["values"][5] for r in ig4) - lv_ig[5]) <= 0.051,   # inputs are rounded to 0.1, so allow half a unit
          f"All: mean of 4 = {mean(r['values'][5] for r in ig4):.2f}, mean of the 3 sentence carriers = {mean(r['values'][5] for r in ig4 if r['method_key'] != 'ring_id'):.2f}, table {lv_ig[5]}")
    ing = {r["method_key"]: r["values"] for r in T["tab_ingen"]["rows"]}
    check("paper text", "5.4: Gaussian Shading 82.2/80.3/79.6 and PRC 76.8/66.6/47.6 by generator",
          tuple(ing["gaussian_shading"][2:]) == (82.2, 80.3, 79.6) and tuple(ing["prc"][2:]) == (76.8, 66.6, 47.6), "")


# ----------------------------------------------------------------------------------------------
def meta(sources):
    return {"generated_utc": GENERATED, "generator": "tools/build_data.py", "paper": PAPER_HEAD, "research_repo": REPO_HEAD, "sources": sources}


def main():
    global GENERATED, PAPER_HEAD, REPO_HEAD
    GENERATED = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    PAPER_HEAD = git_head(PAPER)
    REPO_HEAD = git_head(REPO)
    if REPO_HEAD is not None:
        REPO_HEAD = {"commit": REPO_HEAD["commit"], "date": REPO_HEAD["date"], "note": "metric CSVs are untracked run outputs; the commit identifies the scripts"}
    os.makedirs(OUT, exist_ok=True)
    with open(P(MAIN_TEX), encoding="utf-8") as fh:
        raw = fh.read()
    lines = strip_comments(raw)
    refs, floats = scan_paper(lines)
    lb = build_leaderboards(lines, raw, refs, floats)
    arms = {"fake": load_arm(DIR_FAKE_ID, True, POSTHOC), "real": load_arm(DIR_REAL_ID, True, POSTHOC),
            "syn_identity": load_arm(DIR_SYN_ID, True, POSTHOC), "syn_newgen_identity": load_arm(DIR_SYN_NG, True, POSTHOC),
            "matched": load_arm(DIR_SYN_MATCHED, True, POSTHOC), "ingen": load_arm(DIR_INGEN, False, INGEN)}
    heat, t4idx, allc = build_heatmap(arms, refs)
    curves = build_curves(arms, refs, lb)
    scatter = build_scatter(refs, lb)
    attacks = build_attacks(lb, allc, arms, refs)
    methods = build_methods(lb)
    stats = build_stats(lines, attacks, methods)
    text_claims(heat, attacks, lb)
    crossfamily_identity_block(lb)
    table_text_claims(lb, heat)
    figures = {k: {"number": int(refs[k])} for k in ("fig:protocol", "fig:dissociation", "fig:heatmap", "fig:curves") if k in refs}
    leaderboards = {
        "_meta": meta([f"paper:{MAIN_TEX}"] + sorted({s for t in lb for s in t["source"]["rows"]})),
        "notes": [
            "Rows come from the paper's generated tables/*.tex files; captions, column headers, column groups and the first row group come from "
            "the table environment in the main tex. 'cells[].tex' keeps every cell exactly as in the file; 'cells[].text' is the cell with LaTeX removed.",
            "Wording: the paper's category label 'fake' is shown as 'manipulated' in every text field (row labels, group labels); "
            f"{FAKE_SUBS[0]} substitutions were made. The raw 'tex' fields keep the original.",
            "values[] holds the numeric value columns of a row (columns with kind 'value'), as printed (percent where the unit is '%'). "
            "A '--' cell is null. bold[] marks the paper's bold cells.",
            "paper_table_number is computed by counting table captions in the source order of the main tex (LaTeX numbering).",
            "caption is the paper's caption with LaTeX removed; caption_site is the caption to show on the site. They are equal except for "
            "tab_crossfamily, tab_tier3_main and tab_modes, where caption_note explains a correction, and tab_unmarker, which is not in the paper.",
        ],
        "paper_figures": figures,
        "tables": lb,
    }
    for name, obj in [("leaderboards", leaderboards), ("heatmap", heat), ("curves", curves), ("scatter", scatter),
                      ("attacks", attacks), ("methods", methods), ("stats", stats)]:
        with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1, allow_nan=False)
            fh.write("\n")
    with open(os.path.join(TOOLS, "build_checks.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated_utc": GENERATED, "paper": PAPER_HEAD, "n_checks": len(CHECKS), "n_failed": sum(not c["ok"] for c in CHECKS),
                   "checks": CHECKS}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    for c in CHECKS:
        print(("PASS " if c["ok"] else "FAIL ") + f"[{c['group']}] {c['check']} :: {c['detail']}")
    print(f"\n{sum(c['ok'] for c in CHECKS)}/{len(CHECKS)} checks passed")
    print("tables:", len(lb), "| figures:", figures)
    for name in ("leaderboards", "heatmap", "curves", "scatter", "attacks", "methods", "stats"):
        p = os.path.join(OUT, f"{name}.json")
        print(f"  data/{name}.json  {os.path.getsize(p):,} bytes")


if __name__ == "__main__":
    main()
