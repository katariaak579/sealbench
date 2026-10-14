# Data layer: provenance and verification

`tools/build_data.py` writes the seven JSON files in `data/`. It uses only the Python standard library and reads two sources without modifying them:

- `<PAPER>`: the Overleaf checkout of the paper (`main.tex`, the generated `tables/*.tex`, `references.bib`). Build of record: commit `a0d8e31` (2026-10-14).
- `<REPO>`: the research repository. The metric CSVs are untracked run outputs. `docs/20_RESULTS_INVENTORY.md` §4 marks them CURRENT, and the paper's own scripts `paper/scripts/make_figs.py` and `make_tables.py` read the same files. The scripts are at commit `9620e81`.

To rebuild, run `python3 tools/build_data.py`. The script finds the two roots in `$SEALBENCH_PAPER`/`$SEALBENCH_REPO` or in `tools/local_paths.json`. That file is listed in `.gitignore` because the absolute paths identify the authors . In the JSON, sources appear only as `paper:<relative path>` and `repo:<relative path>`, and every file has a `_meta` block with the generation time, both commits and the source list.

On every run the script also re-checks the data. The results go to `tools/build_checks.json` and to stdout. **Current result: 172 of 172 checks pass.** Two of the passing checks record problems in the paper's captions (see "Discrepancies" below): they pass because the data is correct, but the caption text is wrong.

## Figure numbers (important for the site)

The figure files are named in an old order. In the compiled paper they are numbered differently:

| paper figure | label | file | data file |
|---|---|---|---|
| Figure 1 | fig:protocol | `fig/fig1_protocol.png` | none (image) |
| Figure 2 | fig:dissociation | `fig/fig4_dissociation.pdf` | `scatter.json` |
| Figure 3 | fig:heatmap | `fig/fig3_heatmap.pdf` | `heatmap.json` |
| Figure 4 | fig:curves | `fig/fig2_curves.pdf` | `curves.json` |

The script computes these numbers by counting captions in source order and stores them in each JSON (`paper_figure.number`). The task brief called the curves "Figure 2" and the scatter "Figure 4", which follows the file names, not the paper.

## leaderboards.json: 27 tables, 377 rows

- **How it is built.** The script strips comment lines from the main tex and walks the sections, floats and labels to number every table, figure and section. For each table environment it reads the caption, the label, the header rows (including `\multicolumn` column groups and `\shortstack` headers) and any row-group lines that sit before `\input`. It then splits in the rows from `tables/<id>.tex`. Every cell keeps its raw `tex` and a plain `text`. Numbers are parsed into `value`, bold is recorded, `--` becomes null, `0.6 (rotation 10)` becomes a value with a note, and comma lists (attack severities, ASI) become arrays. Each row also carries `method_key`, `family` (post-hoc or in-generation) and `category` where these can be derived from the row label or its group, plus `attack_type` for rows in the attack tables.
- **Included tables.** The 22 generated tables used in the paper, from Table 3 to Table 26. Four inline tables: tab:comparison (1), tab:methods (2), tab:qsrcases (7) and tab:budget_sensitivity (8). And `tab_unmarker`, which has `in_paper: false` (see below).
- **Wording.** Row and group labels show the paper's `fake` as `manipulated`, which made 15 substitutions. The raw `tex` fields keep the original label.
- **Checks.**
  - For each of the 23 rows files, the parsed rows correspond one-to-one to the file's data lines.
  - Every number formats back to the exact printed string, with the same number of decimals and the same sign.
  - Every row has the tabular's column count.
  - The identity block of tab_crossfamily (60 values) was recomputed as TPR@1%FPR from `runs/2026-09-18_matched-cohort/metrics_syn_matched_identity/detection.csv` and `runs/2026-08-17_ingen-l14/metrics/eval_v2/detection.csv` and matches the table.

## heatmap.json: the Figure 3 data, plus manipulated and real grids

- **Source.** `repo:runs/2026-09-03_results/csv/T4_full_grid.csv`, column `tpr_far01` × 100 for both families. The 52 conditions, their order, the short labels (`bright 0.7`, `edit F`, `VAE q1`, `editshare-Q`, ...) and the C1–C4 assignment are ported line for line from `make_figs.py`. The paper figure is `grids.synthetic.post_hoc` (11 methods) plus `grids.synthetic.in_generation` (4 methods).
- **Extra grids, not in the paper.** `grids.manipulated` and `grids.real` (post-hoc) come from the same CSV. There are also `*_n` grids (image counts) and `post_hoc_attribution_acc` grids (T4 column `acc`).
- **Values are stored unrounded** (100·x). Rounding them to 1 decimal reproduces the paper's own formatting. For example, RingID under UnMarker is 100·0.2955 = 29.549999…, which prints as 29.5 in tab_unmarker and with JavaScript `toFixed(1)`. If the value were stored rounded to 29.55, it would print as 29.6.
- **Nulls.** There are exactly 14 null cells: real-category UnMarker and unmarkshare for the 7 sentence-capable methods. On real images those conditions were run only on the sentence-payload images, so identity mode has no value, and tab_unmarker prints `--` for them. No other cell is missing.
- **Mean ASI.** T4 has no ASI column (its columns are category, family, method, level, attack, severity, n, acc, tpr_far01). `mean_asi` is therefore computed from `robust_curves.csv` (column `x`) as the mean over methods, for four populations: manipulated, real, the pooled 1,593-image synthetic set (two arms pooled per method by `n_pos`) and synthetic in-generation. The paper does not print these values. The paper's own matched-cohort ASI values are in attacks.json.
- **Checks.**
  - tab_unmarker equals the heat-map cells for 74 of 74 values, including the null positions.
  - The post-hoc TPR rows of tab_levels (C1–C4 and All for 3 categories, 15 values) are reproduced from the grids and `n`.
  - The in-generation C1–C4 and All values of tab_crossfamily (20 values) are reproduced from the in-generation grid.
  - 24 numbers stated in the paper text all reproduce: the noise versus diffusion comparison at equal ASI (99.8% vs 24.7%, ASI 0.233 vs 0.243; in-generation 98.5% vs 74.7%), the σ=20 comparisons, the VAE q1 statements (6–7 methods below 10%, in-generation mean 63%, Gaussian Shading 93%, PRC 22%), the diffusion 0.3 statements (only WAM and VINE above 20%, post-hoc mean 12–19%, in-generation mean 68%), the UnMarker statements, and in-generation 0–3% under crop 0.5 and rotation 15.

## curves.json: the Figure 4 data, plus five further sets

- **Paper set.** `sets[0]` (`manipulated_post_hoc`) is built exactly as in `make_figs.py`. x is the condition mean ASI from `metrics_fake_identity/robust_curves.csv`. y is TPR@1%FPR from `detection.csv` (far=0.01, n_eval=100). The anchor is the unattacked TPR at ASI 0. There are 14 single attack types and 11 methods, and all 154 curves have measured points.
- **Further sets (same construction, each labelled with its source).**
  - `real_post_hoc` (`runs/2026-08-14_posthoc-real/metrics_real_identity`). The UnMarker curve exists only for CIN, PIMoG, WAM and TrustMark, so this set has 147 curves.
  - The two synthetic arms that the paper pools: `syn_identity` (796 images) and `syn_newgen_identity` (797 images).
  - `synthetic_post_hoc_matched` (1,193 images, `runs/2026-09-18_matched-cohort/metrics_syn_matched_identity`).
  - `synthetic_in_generation` (`runs/2026-08-17_ingen-l14/metrics/eval_v2`; RingID uses its 1,024-key detector rows).
- **Other contents.** Every set also has the 14 chains as single points, plus per-method AURSC by attack type, AURSC over all 28 attack types and Obs. Min@0.2. These follow the `make_tables.py` recipe in pure Python.
- **Checks.** Recomputing from these curves reproduces:
  - tab_main3 AURSC and Obs. Min@0.2 for manipulated, real and pooled synthetic (66 values), and the unattacked TPR;
  - tab_arms AURSC and Obs. Min@0.2 (22 rows);
  - tab_ingen Obs. Min@0.2 and AURSC (4 methods);
  - tab_family (28 attack types × 4 columns = 112 values).

  All values agree at 3 decimals.

## scatter.json: the Figure 2 data

- **Sources.** These are the two files that `make_figs.py` reads. Post-hoc: `repo:runs/2026-09-18_matched-cohort/semantic/semantic_conditions.csv` (7 methods, matched 1,193-image cohort). In-generation: `repo:runs/2026-08-17_ingen-l14/metrics/semantic/semantic_conditions.csv` (Gaussian Shading, T2SMark, PRC). Attack `none` is excluded.
- **Point fields.** Each point has method, family, attack type, severity, condition id, category C1–C4, mean ASI, bit accuracy, QSR (`qsr_corrected`, primary reader), `n`, and complete-message recovery where the CSV has it (post-hoc only). The unattacked values are stored separately per method.
- **Counts.** 364 post-hoc points, of which 42 have bit accuracy ≥ 0.9 and QSR ≤ 0.5. 156 in-generation points, of which 1 meets the same condition. Both counts match the paper text ("42 of 364", "1 of 156").
- **Check.** From the same rows, the script recomputes for the 10 methods of tab_tier3_main: QSR for Unattacked, C1–C4 and All, sem-AURSC, bit-AURSC and Bit Acc. All 90 values match.

## attacks.json: the 52 conditions

- **Fields.** Each condition has an id, attack type, severity key, category C1–C4 with its name, display name, the heat-map short label, the parameter name and value (from tab_attackgrid), and for chains the steps and stage text (from tab_chains).
- **Order.** Conditions follow the heat-map order. `paper_table_order` gives the order of the appendix tables.
- **ASI columns.** The two mean-ASI columns of tab_attackgrid and tab_chains are "Mean ASI, post-hoc (synthetic)" and "Mean ASI, in-generation (synthetic)". The captions say both are averaged over images and methods on the **matched synthetic cohort**, one for each family. For chains, `post_hoc_manipulated` holds the Mean ASI column of tab_synergy, which is measured on manipulated images.
- **Computed ASI.** `mean_asi_computed` adds values for manipulated, real and pooled-synthetic post-hoc, and recomputes the two matched-cohort columns.
- **Checks.** There are 30/8/8/6 conditions in C1/C2/C3/C4, and every heat-map condition maps to a table row. The recomputed matched-cohort ASI equals both paper columns for all 52 conditions, and the manipulated chain ASI equals tab_synergy for all 14 chains.

## methods.json: the 15 methods

- **Sources.** Bits, message class and generator availability are parsed from the inline tab:methods table and cross-checked against the brief's numbers: CIN 30, PIMoG 30, WAM 32, TrustMark 48, EditGuard 64, VINE/InvisMark/OmniGuard 100, MBRS/VideoSeal/PixelSeal 256. The in-generation message class comes from tab_tier3_main (long). Citation title, venue and year come from the bib.
- **Evaluation settings.** Each method lists the settings it is evaluated in. Post-hoc: identity attribution with the 100-identity codebook, plus message recovery for the 7 sentence-capable methods. RingID: identity attribution with its 1,024 native keys. Gaussian Shading, T2SMark and PRC: message recovery. These are stated positively so that the site does not describe any method as lacking attribution.
- **Not included.** The paper and code URLs are left to another step.
- **Extra fields.** `figure_style` holds the colours and line styles that `make_figs.py` uses for the 11 post-hoc methods.

## stats.json

Each count from the brief is stored with the lines of `main.tex` (comment lines excluded) where the paper states it. All 34 patterns were found. Lists (generators, subclasses, readers, editors, image states) and derived values are separate: the 28 attack types used in AURSC are not printed as a number in the paper, and 1,600 + 1,600 + 1,593 = 4,793.

## Discrepancies and points for the authors

1. **tab_crossfamily caption (main text, Table 3) names the wrong metric for the identity block.** The caption says that block "reports open-set attribution accuracy". The numbers are TPR@1%FPR. Recomputed from `detection.csv` they match 60 of 60 values, while the attribution accuracy is different: RingID All is 80.1 in the table but 54.1 as attribution accuracy, which the paper's own appendix text also states ("80.1% TPR@1%FPR ... 54.1% attribution accuracy"); WAM is 90.2 versus 88.9. The previous caption in the repo mirror said "All values are TPR@1%FPR". `caption_site` states the correct metric; `caption` keeps the paper text.
2. **tab_modes caption (Table 10) lacks the definition of message mode.** It reads "…the basis of the identity-arm block of Table 3 and of the other detection tables in this appendix, the basis of the semantic-arm block of Table 3." `caption_site` restores the missing definition from the comment in `make_tables.py`. The wording should be confirmed by the authors.
3. **tab_tier3_main caption (Table 4) ends with a stray "Table~\ref{tab:tier3rest}."** This comes after a hard-coded "Appendix Table 18". The hard-coded number is correct at the current numbering (tab:tier3rest is Table 18), but it is not a `\ref`. `caption_site` drops the stray reference.
4. **tab_levels caption.** The caption says in-generation TPR is "on their sentence-carrying images", but the in-generation TPR row is the mean over all 4 in-generation methods, RingID included (mean of 4 = 75.25, which prints as 75.3; the mean of the 3 sentence carriers is 73.63). This is informational; the caption is not changed.
5. **Overleaf tables differ from the repo mirror** (`paper_mirror/tables`) in two files. tab_crossfamily's second group label is "Message Recovery" (mirror: "Semantic arm …"). tab_modes uses the mode label "message" (mirror: "sentence", which is what the current `make_tables.py` writes). All numbers are identical. The site follows the paper.
6. **tab_unmarker is not in the paper.** Its table environment is commented out, but `tables/tab_unmarker.tex` is still generated. The commented caption says "5 in-generation methods" and "Level 2/Level 4", whereas the rows file has the 4 current in-generation methods. The entry has `in_paper: false` and a corrected caption, and the original is kept in `caption_original_commented_tex`.
7. **tab:comparison** declares 6 columns in its tabular spec but uses 5. The empty column is dropped; this has no effect on the PDF.
8. **Missing data that the site must handle.** There are 14 null heat-map cells (real UnMarker/unmarkshare, 7 methods). The real-category curves have no UnMarker curve for those 7 methods. The in-generation scatter has no complete-message recovery per point, because its source CSV has no `exact_acc` column; the in-generation Msg. Rec. values are in the leaderboards.
9. **Computed values.** Every ASI value marked "computed" (the heat-map `mean_asi`, `attacks.json` `mean_asi_computed`) and every curves-set summary outside the paper set is produced by this script, not printed in the paper. Where a paper value exists, the computed value reproduces it.
