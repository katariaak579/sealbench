# SEALBench website

Static site for **SEALBench: A Comprehensive Benchmark for Image Watermark Detection, Robustness, and Recovery**. Plain HTML, CSS and JavaScript with no build step; it is served from the repository root by GitHub Pages.

## Layout

| Path | Content |
|---|---|
| `index.html` | The page. Prose is static; tables, charts and the attack explorer are drawn by `js/site.js`. |
| `css/site.css` | Design tokens (light and dark) and all styles. |
| `js/data.js` | Generated data bundle (`window.SEAL`). Do not edit by hand. |
| `data/*.json` | Full data extracted from the paper's tables and the result CSVs. |
| `assets/fig/` | Figure 1 and the paper figures as WebP/PNG/SVG. |
| `assets/gallery/` | Synthetic images and per-image records for the attack explorer (`gallery.json`, `SOURCES.md`). |
| `tools/` | Scripts that rebuild the data (`build_data.py`, `build_bundle.py`, `build_gallery.py`, `make_figs_svg.py`, `make_og_card.py`) and the verification report `VERIFY_DATA.md`. |

## Rebuilding the data

```bash
python3 tools/build_data.py      # reads the paper tables and result CSVs (paths in tools/local_paths.json)
python3 tools/build_bundle.py    # writes js/data.js
```

## Before publishing

Search `index.html` for `TODO` and `data-todo`: author list, paper / code / dataset links, the submission-form link, and the BibTeX entry.

## Publishing on GitHub Pages

Push this directory to a repository, then Settings -> Pages -> Deploy from a branch -> `main` / root. `.nojekyll` is included so the files are served as they are.
