# Retrieved source artefacts — substrate material library (PROPOSED)

**Status:** proposed content for `docs/plans/Refractive_Substrate_Emission_Plan.md`. Not
shipped, not wired into `radiant.data`. If §7 is ratified, these move to
`docs/validation/substrate_datasheets/` (repo-only, never in the wheel) per Rule 26(c)
and the Gap 119 precedent.

Every file below is the **exact byte stream retrieved**, unedited. All retrieved
**2026-10-04** by `python urllib.request` from the URLs given. SHA-256 is of the retrieved
bytes.

## refractiveindex.info database — n(λ)

The refractiveindex.info database is released under **CC0 1.0** (public domain
dedication); each file's own header says so. Retrieved from the project's GitHub mirror at
`https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/master/database/data/<path>`.
The human-readable page for each entry is
`https://refractiveindex.info/?shelf=main&book=<book>&page=<page>`.

| file | database path | primary reference | SHA-256 |
|---|---|---|---|
| `main__Ge__nk__Li-293K.yml` | `main/Ge/nk/Li-293K.yml` | H. H. Li, *J. Phys. Chem. Ref. Data* **9**, 561 (1980/1993), doi:10.1063/1.555624 | `fa84a9dc95711cefebdc3fcd827da76dfa1d67fa192c07cfc703fec457f11aa7` |
| `main__Si__nk__Li-293K.yml` | `main/Si/nk/Li-293K.yml` | H. H. Li, same | `a4ba5d46309c1ac43624b8d7347d8fe2f544c90b28cc0ae3eca9d4ec60a92507` |
| `main__ZnSe__nk__Connolly.yml` | `main/ZnSe/nk/Connolly.yml` | Connolly/diBenedetto/Donadio, *Proc. SPIE* **181**, 141 (1979); Tatian fit, *Appl. Opt.* **23**, 4477 (1984), doi:10.1364/AO.23.004477 | `8e9c0a7c21995e34ddb9c3d1fa8d04f16955e2d784d6ab98c7121a8a241617ee` |
| `main__ZnS__nk__Debenham.yml` | `main/ZnS/nk/Debenham.yml` | Debenham, *Appl. Opt.* **23**, 2238 (1984); Klein fit, *Appl. Opt.* **25**, 1873 (1986), doi:10.1364/AO.25.001873 | `c8b2093062ca4331953b53ec51a59518ea0d23f4d387f1a6e521ae33fa25efe0` |
| `main__Al2O3__nk__Malitson-o.yml` | `main/Al2O3/nk/Malitson-o.yml` | Malitson & Dodge, *J. Opt. Soc. Am.* **62**, 1405 (1972); Dodge, CRC Handbook of Laser Sci. & Tech. IV (1986) | `459f0cb41f105b9a01dc96a7d2eab0a71c5d43f7355fba3c4d3d6969fc76a41b` |
| `main__CaF2__nk__Li.yml` | `main/CaF2/nk/Li.yml` | H. H. Li, *J. Phys. Chem. Ref. Data* **9**, 161 (1980), doi:10.1063/1.555616 | `66fd889e1874466f5ce78bf75d422337d0a99cfaf7a92a599f8dba40eec20751` |
| `main__BaF2__nk__Li.yml` | `main/BaF2/nk/Li.yml` | H. H. Li, same | `b4519240e93e8f6d3baf6f36708177855c7787bcdb1c5b7c362463456a4dba8d` |
| `main__SiO2__nk__Malitson.yml` | `main/SiO2/nk/Malitson.yml` | Malitson, *J. Opt. Soc. Am.* **55**, 1205 (1965), doi:10.1364/JOSA.55.001205 | `c587670f397241ecb93a1af3279d6fe7ed67888e587e399074b0eab729c92b52` |

### Evidence files (not used to build any table)

| file | database path | why it is here | SHA-256 |
|---|---|---|---|
| `main__ZnSe__nk__Querry.yml` | `main/ZnSe/nk/Querry.yml` | Querry, CRDEC-CR-88009 (1987). **Study §7.1's load-bearing negative evidence**: the `tabulated nk` block reports `k = 0.0000000` at every point from 2.0 µm to 14 µm — the tabulated-k route is a null for transparency-window absorption. | `b9ad75ccdf8701400faa28ea5d55315907a8d256ad9f2ca79da4c2ff25c6b2f8` |
| `main__Ge__nk__Li-100K.yml` | `main/Ge/nk/Li-100K.yml` | **Study §7.2's asymmetry evidence**: n(λ,T) for Ge is published at nine temperatures (100–550 K) while α(λ,T) is published at none. | `b3d81d9e11899bccc032403cd6831235cce520048a16a08528e080a1c7590672` |
| `main__Ge__nk__Li-200K.yml` | `main/Ge/nk/Li-200K.yml` | same | `62a9d9699f116603cd1835e58ceb8a5de2cc021c4c5c849c4e806ba0b4bac4fe` |
| `main__Ge__nk__Li-350K.yml` | `main/Ge/nk/Li-350K.yml` | same | `9d6f0e871c7bdad7530fb0c10c77ecc73c3a3aabadf7461f0ab234006b8b9e2d` |

## Crystran Ltd material pages — α(λ) anchors and the published spec values

Retrieved from `https://www.crystran.co.uk/optical-materials/<slug>`; each file is the
page's HTML with tags stripped to text (the stripping is reproducible by
`scrape_crystran.py`'s `text_of`, kept in the session scratch; the SHA-256 below is of the
**stripped text as committed**, since that is the artefact a reader checks). These are
**manufacturer pages, i.e. secondary sources**: each page carries its own numbered
reference list, and several attribute the absorption-coefficient row to
*"Manufacturers Published Data"*. Study §11 records the upgrade-to-primary opportunity.

| file | slug | what it supplies | SHA-256 |
|---|---|---|---|
| `germanium-ge.txt` | `germanium-ge` | α at 2.7 / 5.6 / 10.6 µm; n = 4.0021 and 53 % 2-surface reflection loss at 10.6 µm | `427d28f0df809c63fbe289746b538e7099cd11d88db0c827d3b3dca8ee0d4f61` |
| `silicon-si.txt` | `silicon-si` | α at 3.0 µm; n = 3.4223 and 46.2 % RL at 5 µm; the CZ 9 µm oxygen-band note | `9cfecf5d16010e64a32e952edc3698246a3d377392beac75fd1286fabf2a996d` |
| `zinc-selenide-znse.txt` | `zinc-selenide-znse` | α at 1.3 / 2.7 / 3.8 / 5.25 / 10.6 µm; n = 2.4028 and 29.1 % RL at 10.6 µm | `dd885269cb6cc8455312d4f0b2ef5ae9b3d5fcd375bc6283d464164077c70f0b` |
| `zinc-sulphide-zinc-sulfide-multispectral-zns.txt` | `zinc-sulphide-zinc-sulfide-multispectral-zns` | α at 1.3 / 2.7 / 3.8 / 9.27 / 10.6 µm; n = 2.20084 and 24.7 % RL at 10 µm | `8afd0712044d23e87f201edd044880a3e6aabac73eb5075983271a7c28439bf9` |
| `calcium-fluoride-caf2.txt` | `calcium-fluoride-caf2` | α at 2.7 / 6.25 / 7.69 / 8.69 / 9.09 / 10.6 µm; n = 1.39908 and 5.4 % RL at 5 µm | `d42cff5fdf8bc157fe112427bbff6c0e3b4af074722d3bd3533bc7dc258a02aa` |
| `barium-fluoride-baf2.txt` | `barium-fluoride-baf2` | α at 6.0 µm; n = 1.45 and 6.5 % RL at 5 µm | `63a9c835f931bfcb2e48ce132375361d040d6f20f46c8f01961edc2844a19b50` |
| `sapphire-al2o3.txt` | `sapphire-al2o3` | α at 2.4 µm; n_o = 1.75449 and 14 % RL at 1.06 µm | `9f92c07f20d9a747434c84fc4dd6b6deafc04d6a7d211fd886bb40da186c1371` |
| `fused-silica-glass-sio2.txt` | `fused-silica-glass-sio2` | α at 1.0 µm; n = 1.47012 at 4 µm; 7 % RL at 0.4 µm | `383ac84786d67da50869ad5bba0032dc3565cbdea7f3f675e30fe1017d260554` |

## Generators

- `../build_substrate_tables.py` — reads the material YAMLs (and the `ri_table` entries'
  source files above) and writes `../tables/<material>.csv`. Rule 26 generator-of-record.
- `../n2_derivation.py` — the study §7.3 derivation check. Needs no material data.
- `../grade_substrate_data.py` — the three-tier grading harness (study §8).
- `../ge_alpha_temperature.py` — the α(λ,T) evidence (study §7.2).

`../tables/*.csv` are generated and regenerable; if §7 is ratified they do not ship at all
(the loader evaluates the YAML's dispersion formula and α anchors directly). They are
committed here only so the owner can inspect the proposed numbers during ratification.
