# Attack gallery: sources of every value

Built by `tools/build_gallery.py` (run with the auvire python, `python -B`). The research repo
`<RESEARCH_REPO>` (= `R` below) is read only. Synthetic images only;
no real or manipulated (MultiFakeVerse) image is used.

## Entries

| image_id | family | method | generator / stem | message id |
|---|---|---|---|---|
| flux1_scenery_0616_gs | in-generation | Gaussian Shading | FLUX.1-dev / scenery_0616 (landscape) | long_103 ("wes made a chair on saturday") |
| flux1_object_0440_t2smark | in-generation | T2SMark | FLUX.1-dev / object_0440 (food and drink) | long_062 ("eva drew the violet stool") |
| flux1_scenery_0616_videoseal | post-hoc | VideoSeal | FLUX.1-dev / scenery_0616 (landscape) | long_015 ("zelda sold the maroon wagon") |
| flux1_object_0440_videoseal | post-hoc | VideoSeal | FLUX.1-dev / object_0440 (food and drink) | long_039 ("stefan took the gray kayak") |

Both scenes are in the matched synthetic cohort (`R/runs/2026-09-18_matched-cohort/cohort_stems.json`):
the post-hoc and in-generation versions share generator, prompt and seed. They carry
different messages (each entry's `payload_text`), drawn from the same message corpus.

## Pixels

- Prompt, seed, sub-class, clean and in-gen watermarked paths:
  `R/runs/2026-08-17_ingen-l14/metadata/ingen_master.jsonl` and `ingen_master_index.csv`.
- Unwatermarked: `R/runs/2026-07-18_ingen-flux1-{scenery,object}/combined/clean/<stem>.png`
  (identical, max abs diff 0, to the post-hoc input `R/runs/2026-07-31_posthoc-semantic/inputs/flux1/<stem>.png`).
  For in-generation methods this is the same prompt and seed WITHOUT a watermark, which is a
  different sample (the watermark changes the initial latent), so it is not pixel-aligned and no
  residual is given for in-gen entries.
- In-gen watermarked: `R/runs/2026-07-18_ingen-flux1-scenery/combined/gaussian_shading/scenery_0616.png`,
  `R/runs/2026-07-18_ingen-flux1-object/t2smark/t2smark/object_0440.png`.
- Post-hoc watermarked: `R/runs/2026-07-31_posthoc-semantic/out_img_flux1_eval999/videoseal/<stem>.png`
  (the first wm root that `attacks/leveled_attacks.py` resolves for `syn_flux1_semantic`).
- In-gen attacked (all 16 conditions): the evaluated files
  `R/runs/2026-08-17_ingen-l14/attacked_wm/<level>/<condition>/in_generation/flux1/<method>/<stem>.png`.
- Post-hoc attacked, C1 and C3 (9 conditions): the archived attacked pixels are not on disk
  (docs/20_RESULTS_INVENTORY.md section 6c), so they were re-rendered from the watermarked image with
  `leveled_attacks.apply_chain(img, stem, condition, stages)`; every stochastic stage is seeded by
  sha256(stem:condition:stage:attack:severity). Check: the same call on the in-gen Gaussian Shading
  image reproduced the on-disk files for jpeg_50, gnoise_10, overlay_0.2, rotation_10, meme,
  messenger and social with max abs pixel difference 0.
- Post-hoc attacked, C2 and C4 (edit, VAE, diffusion, UnMarker, editshare-qwen, regenshare, scrub):
  GPU-generated stages that exist only in the HF archive. `file` is null; metrics are real.
- Residual (post-hoc only): |watermarked - unwatermarked| x 10, clipped to 255, computed at 1024 px,
  then resized to 640 px. `psnr_db` is computed from the same pair (VideoSeal record `psnr` = 44.19 for scenery_0616 agrees).
- Edit instruction (edit_qwen, editshare-qwen): `R/runs/2026-08-17_ingen-l14/external/edit_manifest_qwen_image_edit_fast_pass1.jsonl`
  (row with matching `canonical`). The paper passes the same instruction to every watermarked variant of a scene.
- All images: 640 px wide WebP, quality 82.

## Per-condition values

### In-generation entries
- `asi`, `score`: `R/runs/2026-08-17_ingen-l14/metrics/records_ingen_v2.jsonl`
  (row with matching method, image `flux1/<stem>.png`, stage, attack, severity).
- `tau`: `R/runs/2026-08-17_ingen-l14/metrics/eval_v2/thresholds.csv`, mode score, far 0.01
  (calibrated on unwatermarked and attacked-unwatermarked images; Gaussian Shading 0.589844, T2SMark 0.574219).
- `detected`: score > tau (strict, as in `post_hoc/evalaute_wm_metric.py`).
- `bit_acc`, `decoded_text`: `R/runs/2026-08-17_ingen-l14/metrics/records_semantic_ingen.jsonl` gt_bits/dec_bits;
  bit_acc = matching bits / len(gt_bits) (formula of `post_hoc/semantic/evaluate_semantic_metrics.py`);
  text = `semantic_encoding.decode_bits(dec_bits, "packed5", 28)`.
- Message id: `R/runs/2026-08-17_ingen-l14/metrics/codebook_semantic_ingen.json` (semantic.methods.<m>.messages["flux1/<stem>"]);
  text and questions: `R/post_hoc/semantic/semantic_corpus.json`.
- `qsr`: `R/runs/2026-08-17_ingen-l14/metrics/qsr_out/qsr_qa.csv` (Qwen2.5-7B-Instruct reader);
  qsr_corrected = mean(correct) - mean(blank_correct), as in evaluate_semantic_metrics.py; per-question gold/pred/correct kept.

### Post-hoc entries
- `asi`, gt_bits, dec_bits, identity: `R/runs/2026-07-31_posthoc-semantic/out_img_flux1/results/records.jsonl`
  (method videoseal, image `<stem>.png`).
- `score`: max over the first 100 codewords of `R/runs/2026-07-31_posthoc-semantic/out_img_flux1/results/codebook.json`
  of the fractional bit match (`match_scores` in `post_hoc/evalaute_wm_metric.py`); `identity_correct` = argmax == record identity.
- `tau`: `R/runs/2026-08-02_leveled-eval/metrics_syn_flux1_semantic/thresholds.csv`, videoseal, codebook, n_eval 100, far 0.01 = 0.609375.
- `detected`: score > tau.
- `bit_acc`, `decoded_text`: as for in-gen, from the records above (chars 28, packed5; codebook semantic section).
- `qsr`: `R/runs/2026-08-02_leveled-eval/qsr_syn_flux1_semantic/qsr_qa.csv`, same formula.
- UnMarker: no post-hoc semantic-arm UnMarker record exists for these two stems (UnMarker runs on a
  50-per-subclass subset), so every value is null.

## Paper figures
- `fig/protocol-*.{webp,png}`: resized from `<PAPER_SOURCE>/fig/fig1_protocol.png` (Lanczos).
- `fig/{curves,heatmap,dissociation}.{png,webp}`: `convert -density 300` of the Overleaf `fig2_curves.pdf`,
  `fig3_heatmap.pdf`, `fig4_dissociation.pdf`, flattened on white, trimmed, 12 px border.
- `fig/svg/*.svg`: `tools/make_figs_svg.py` (copy of `R/paper/scripts/make_figs.py`, output dir and
  extension changed only). Same data as the paper PDFs (visually checked); fonts differ slightly.
- `img/og-card.png`: `tools/make_og_card.py`.
