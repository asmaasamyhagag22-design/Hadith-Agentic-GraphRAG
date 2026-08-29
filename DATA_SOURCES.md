# External data acquisition and provenance

The files under `data/raw/external/` are third-party inputs and are intentionally
git-ignored. They are not graph outputs and their presence does not mean narrator
entity resolution has been performed.

## Multi-IsnadSet (MIS / MIDS)

- Source: Multi-IsnadSet (MIDS) for Sahih Muslim, Mendeley Data version 2.
- DOI: <https://doi.org/10.17632/gzprcr93zn.2>
- License declared by the deposit: CC BY 4.0.
- Associated data paper: <https://pmc.ncbi.nlm.nih.gov/articles/PMC11096860/>

Download version 2 and place these files without renaming them:

```text
data/raw/external/mis/
├── 1_Hadith_SahihMuslim_HadithContent.xlsx
├── 2_Hadith_SahihMuslim_Narrators_Nodes_for_Graph.xlsx
└── 3_Hadith_SahihMuslim_Isnad_Edges_for_Graph.xlsx
```

The exact SHA-256 values used for the 2026-08-16 linkage measurements are
recorded in `EXPERIMENTS.md` and generated again in
`data/processed/mis_linkage.json`.

Repository truth differs from the publication summary: the downloaded edge
workbook contains 63,642 rows, while the data paper describes a larger combined
"Narrators of Multi-Isnad" record count. Measurements in this repository use
the actual downloaded workbooks.

The associated paper's schema defines `NarratorNameAr` as the narrator's
complete Arabic name and `NarratorNameAr-Mapped` as the narrator's short Arabic
name. Both fields are populated in all 2,092 downloaded node rows. They are not
interchangeable: only 57 pairs are equal under the project's narrow normalizer,
and the mapped short name has fewer tokens in 1,500 rows. The paper also says
the narrator links were produced with logical code, fuzzy matching, and manual
mapping. Those historical links and the mapped short-name field are therefore
source evidence, not independently validated person-identity ground truth.

## Itqan narrator profiles

- Source repository: <https://github.com/R3GENESI5/Itqan>
- Profile directory: `app/data/rijal/`
- Auxiliary indexes: `app/data/narrator_grades.json` and
  `app/data/narrator_index.json`
- Downloaded manifest version used here: `1.20`.
- License status: the repository declares its code MIT, but the downloaded
  unified profile shards combine several upstream datasets and classical-text
  parses. A single explicit license for these derived data files was not found;
  redistribution remains unresolved, so the files stay ignored.

Place the seven `profiles_*.json` shards plus `by_name.json` and `manifest.json`
under `data/raw/external/itqan/`, together with the two auxiliary indexes. The
expected local set contains 11 JSON files. The manifest declares 115,735
profiles; every shard count and every file parse is checked by
`src/profile_itqan.py`.

The upstream repository is mutable and the local download did not retain an
upstream commit identifier. Reproducibility for the current snapshot therefore
depends on the per-file SHA-256 values emitted into
`data/processed/itqan_profile.json`. The missing upstream commit pin is a known
provenance limitation.

The local snapshot contains 115,735 `full_name` values and 196,488 raw
`namings[]` items (270,236 profile-level unique canonical-or-naming
representations after within-profile narrow deduplication). The upstream project
describes these as full names and spelling/name variants consolidated from
multiple structured and textual sources, but the local machine-readable
manifest does not guarantee that every historically known or source-specific
form is present. Some `namings[]` values are contextual relations such as
`أبيه` and `جده`, so a naming equality is candidate evidence rather than proof
of identity.

## Reproduce the audits

After installing the locked environment and placing the external files:

```bash
uv run python -m src.profile_data
uv run python -m src.profile_mis
uv run python -m src.build_linkage_audit
uv run python -m src.build_linkage_validation
uv run python -m src.profile_itqan
uv run python -m src.audit_gradings
uv run python -m src.build_narrator_candidates
uv run python -m src.analyze_narrator_unmatched
```

`build_linkage_validation` preserves an identical unlabeled frozen sample and
refuses to overwrite a reviewer file once any human verdict exists.
