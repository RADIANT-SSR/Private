# Remediation Blockers

## BLOCKER B0 — `dev_tools/geometry_gui_v2/` is entirely untracked in git

**Discovered:** 2026-04-28, before T1 branch creation.

**Symptom:**
The remediation work order in `PLAN_v2_remediation_agent.md` and the wrapping
prompt both describe Phases 0–7 of `PLAN_v2.md` as "shipped." The wrapping
prompt instructs:

> Branch: create `fix/visual-remediation` off `main` before T1.

But `git ls-files dev_tools/geometry_gui_v2/` returns nothing. `git log --all
-- dev_tools/geometry_gui_v2/` returns nothing. The directory exists in the
working tree (173 files, 1.5 MB) but is uncommitted in every branch and every
worktree (7 inspected). Phases 0–7 are *physically present on disk* but are
not *committed history* anywhere I can see.

**Why this matters:**
- The remediation premise is "build T1–T10 on top of shipped Phase 0–7." If I
  branch off `main`, the v2 baseline is a 173-file untracked blob, not a
  reviewable commit history.
- The plan asks for "one branch off `main` → one commit per task." A first
  commit on the new branch would have to be either (a) the entire 173-file
  Phase 0–7 baseline as a single squash, or (b) per-task commits that mix
  baseline lift with remediation, which violates "one task one commit."
- I cannot tell which files in the working tree are "Phase 0–7 ship" versus
  uncommitted in-progress work that someone else is mid-edit on. Several
  other untracked items in the same `git status` (PLAN_v2.md in the *v1*
  geometry_gui directory, an Excel `.~lock` file, audit_2026/) suggest a
  general uncommitted-work situation.

**What I tried:**
1. `git ls-files dev_tools/geometry_gui_v2/` → empty.
2. `git log --all --oneline -- dev_tools/geometry_gui_v2/` → empty.
3. Inspected each of the 7 locked worktrees (`worktree-agent-*`); none of
   them contain v2 files in their commit trees.
4. Verified the current branch (`chore/cu-007-mwir-t3mixed-routing`) is
   ahead of `main` by 3 commits, none of which touch v2.

**What I need from the human reviewer to unblock:**

Pick one of:

1. **Commit the existing Phase 0–7 baseline first.** I create
   `fix/visual-remediation` off `main`, commit the entire untracked v2
   tree as a single "Phase 0–7 baseline lift" commit, then start T1 on top.
   Risk: I cannot distinguish baseline files from in-progress work that
   may be sitting in the working tree from someone else's session.

2. **Point me to the actual baseline branch / commit.** If Phase 0–7 was
   committed somewhere I cannot see (a remote, a stashed branch, a
   different repo), tell me where, and I will branch off that point.

3. **Confirm that the untracked tree IS the baseline,** and authorize a
   single bulk-commit of the 173 files as the starting point.

**I have not switched branches, created the remediation branch, or modified
anything.** Per the spec ("Do not silently work around the spec"), I'm
stopping here for direction before T1.
