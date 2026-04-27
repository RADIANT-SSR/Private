# Phase 7 — Polish, run instructions, /src untouched gate

**Category:** D (Integration & docs)
**Pre-reads:** all prior phase reports; PLAN.md §3 hard constraints.

## Hard constraint
**Do not edit `/src/`.** This phase explicitly verifies that no `/src` file has been touched
across the entire tool's history.

## Goal
1. The tool is documented well enough that a colleague can clone the repo and have it running
   in under five minutes.
2. A single command runs all GUI tests.
3. A repo-level guard makes the C1 invariant impossible to violate accidentally going forward.

## Tasks

### Run instructions
Update `dev_tools/geometry_gui/README.md` with:
- A "Run" section: `pip install -r dev_tools/geometry_gui/requirements.txt`, then
  `python -m dev_tools.geometry_gui.app.main`, then open `localhost:8050`.
- A "Test" section: `pytest dev_tools/geometry_gui/tests/`.
- A "Caveats" section repeating PLAN.md §8 verbatim (the developer running the tool sees them
  without leaving the README).

### Screenshot gallery
Add `dev_tools/geometry_gui/docs_screenshots/` with one screenshot per shape, plus one each
for extended / point-source modes, plus one with the sun arrow & terminator visible.
Reference them in the README.

### /src untouched gate (C1 verification)
Add `dev_tools/geometry_gui/tests/test_no_src_writes.py`:
```python
def test_no_src_files_modified_by_this_tool():
    """C1: this tool must never modify /src."""
    repo_root = Path(__file__).resolve().parents[3]
    # Find every commit that modified /src AND any file under dev_tools/geometry_gui/.
    # That's evidence of a bundled change. Fail if any exists.
    out = subprocess.check_output([
        "git", "log", "--all", "--name-only", "--pretty=format:COMMIT %H",
        "--", "src/", "dev_tools/geometry_gui/",
    ], cwd=repo_root, text=True)
    # Parse: for each commit block, check if files from BOTH paths appear.
    # If so, that commit violated C1 — print the SHA and fail.
    ...
```
The test passes today (the tool only ever creates files under `dev_tools/geometry_gui/`).
It will fail if a future contributor bundles a `/src` change with a GUI change.

### Pre-commit hint
In the README, add a one-liner the user can paste into `.git/hooks/pre-commit` to refuse
commits that touch both paths. This is a hint — not enforced repo-wide.

### CI line for `pyproject.toml` (optional, document only)
The README should include a suggested GitHub Actions step that runs the GUI test suite —
but Phase 7 does NOT modify `pyproject.toml` or any CI config (those live outside
`dev_tools/geometry_gui/`). The doc just shows the snippet for the project owner to add
later if desired.

## Tests
- `pytest dev_tools/geometry_gui/tests/ -v` — all green, including the new C1 gate test.
- The C1 gate test is the headline acceptance criterion.

## Forbidden
- Adding any feature that wasn't in PLAN.md. Out-of-scope ideas go to PLAN.md §10
  (the follow-on list), not into the codebase.
- Modifying `/src`, `/scenarios`, `/docs`, `/tests`, or root `pyproject.toml`. This phase
  only touches `dev_tools/geometry_gui/`.

## Report (Category D)
- File list.
- Test results, including the C1 gate.
- One sentence confirming `git log --all --name-only -- 'src/**'` is byte-identical to the
  same command run before Phase 0.
- Updated PLAN.md §10 if any out-of-scope idea surfaced during Phases 0–7.
