# FPA Reference Documents — Manifest

Committed reference PDFs (vendor datasheets, papers) cited by the shipped FPA
presets in `src/radiant/data/tables/fpa/`, per CLAUDE.md Rule 26(c)
(owner-ratified 2026-09-06, Gap 119). Repo-only — never shipped in the wheel;
wheel users get each preset's citation URL/DOI instead.

Rules (plan §3.5):

- One row per file, append-only; commit manifest rows with the file they
  describe. A vendor revision is a **new file + preset update**, never an
  in-place replacement.
- `tests/test_fpa_presets.py` (lands with the first preset) asserts every
  `file:` a preset cites exists here and matches its SHA-256.
- Prefer freely downloadable primary sources; the acquisition URL column
  records where each came from (Wayback URL when the live document is
  delisted). Fetch-URL register: plan Appendix A.

| File | Title | Source URL | Retrieved | SHA-256 | Citing preset(s) |
|---|---|---|---|---|---|
| `geosnap18_datasheet_2022.pdf` | GeoSnap-18 Focal Plane Array (Teledyne Imaging Sensors, DOPSR 23-S-0343) | <https://www.teledyne-si.com/en-us/Products-and-Services_/Documents/Infrared%20and%20Visible%20FPAs/GeoSnap_18.pdf> | 2026-09-06 | `afa147ad26c1b6ac8a22a3ce2691c231b1334536a750d873016f3755545a9dd5` | geosnap-18 |
| `geosnap18_leaflet_2025.pdf` | GeoSnap-18 Product Leaflet (Teledyne Space Imaging, Apr 2025) | <https://www.teledynespaceimaging.com/en-us/Products_/Documents/GeoSnap/GeoSnap-18%20Product%20Leaflet%20Apr%202025.pdf> | 2026-09-06 | `03b9e24d6d4e3ba82da4d52b879e0ad0776fb5f23e3a6c4e44c7b4c94b95db85` | geosnap-18 |
| `geosnap10_leaflet_2025.pdf` | GeoSnap-10 Product Leaflet (Teledyne Space Imaging, Apr 2025) | <https://www.teledynespaceimaging.com/en-us/Products_/Documents/GeoSnap/GeoSnap-10%20Product%20Leaflet%20Apr%202025.pdf> | 2026-09-06 | `335f9dcfdc9add1d502edff6215f5dc7aeb31c29424dafd9ef27604890aca80e` | geosnap-10 |
| `bowens_geosnap_lw_spie_2024.pdf` | Bowens et al., Characterization of a longwave HgCdTe GeoSnap detector, Proc. SPIE 13103 (arXiv:2405.20440) | <https://arxiv.org/pdf/2405.20440> | 2026-09-06 | `80abc817306febcc473afde6a35e26dc835436909d6595965926d9b0004c3c95` | geosnap-18 |
| `leisenring_geosnap_13um_an_2023.pdf` | Leisenring et al., Evaluating the GeoSnap 13-µm cutoff HgCdTe detector, Astron. Nachr. 344 (arXiv:2306.05470) | <https://arxiv.org/pdf/2306.05470> | 2026-09-06 | `c684659c951ee02251b55890e45bc47d9162851ece6401e00e45c405f6405949` | geosnap-18 |
| `neutrino_lc_ogi_datasheet_2025.pdf` | Neutrino LC OGI Datasheet (Teledyne FLIR, rev 2025-06-18) | <https://flir.netx.net/file/asset/59789/original/attachment> | 2026-09-06 | `ba528b9a3d19014b613e0b30037b3576935789a4d5959b2cb6dc7eb9401abd80` | flir-neutrino-lc |
| `boson_plus_datasheet_2026.pdf` | Boson+ LWIR OEM Thermal Camera Module datasheet (Teledyne FLIR, rev 2026-04-30) | <https://flir.netx.net/file/asset/43192/original/attachment> | 2026-09-06 | `36f04a0eea9818af15284f57b38ccd64d51a54a6d8073835773c75d7972f1cfa` | flir-boson-plus-640 |
| `boson_plus_engineering_datasheet_2025.pdf` | Boson+ Thermal Imaging Core Product Datasheet (engineering, Doc 102-2013-45 Rel 114, 2025-09-05) | <https://flir.netx.net/file/asset/55485/original/attachment> | 2026-09-06 | `c8e8c3236099c5643c2fe3b67aeed5ed6662713754ffa27361bf7b6d66ceadea` | flir-boson-plus-640 |
| `h2rg_brochure_tsi0855_2022.pdf` | H2RG Visible & Infrared Focal Plane Array (TSI-0855, DOPSR 22-S-1034, Feb 2022) | <https://www.teledyne-si.com/en-us/Products-and-Services_/Documents/Infrared%20and%20Visible%20FPAs/TSI-0855%20H2RG%20Brochure-25Feb2022.pdf> | 2026-09-06 | `ad1a90813b359b3a0fd68ee3b37114404a440834812fbcdf004720899ab47c98` | teledyne-h2rg-2p5 |
| `schultz_dfpa_llj_2014.pdf` | Schultz et al., Digital-Pixel Focal Plane Array Technology, Lincoln Laboratory Journal 20(2), 2014 (Wayback) | <http://web.archive.org/web/20141222135440id_/http://www.ll.mit.edu:80/publications/journal/pdf/vol20_no2/20_2_2_Schultz.pdf> | 2026-09-06 | `a7735eb676717e689fff0b1376023614df4ece76fdb795c57a497b8010d1ca35` | dfpa-generic |
