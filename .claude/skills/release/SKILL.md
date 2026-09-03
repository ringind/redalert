---
name: release
description: Cut a versioned release of the Red Alert Home Assistant add-on — bump the version in both places, update the changelog, push, wait for green CI, tag, and publish the GitHub release. Use when the user says "release", "veröffentliche release", "tag", "cut X.Y.Z", or after a batch of changes that should ship to add-on users.
---

# Cutting a Red Alert add-on release

Semver `MAJOR.MINOR.PATCH`: PATCH = bugfix, MINOR = new option/effect/endpoint,
MAJOR = breaking. Every pushed commit that changes add-on behaviour should get its
own version even if it is not released (HA's update mechanism keys on it), so the
version is often already bumped by the time you release — check first.

## 1. Preconditions

- Working tree clean, on `main`, `git status` shows nothing to commit.
- The commit you will tag is already pushed **and CI is green** for it
  (`gh run list --workflow=build.yaml --branch main -L1`). Never tag a red or
  pending commit.
- Know the previous **released** tag: `gh release list`. Notes must cover every
  change since that tag, which may be several commits / intermediate versions.

## 2. Version bump (only if not already done for this commit)

The version string lives in **two** files and they must match:

- `redalert/config.yaml` → `version: "X.Y.Z"`
- `redalert/Dockerfile` → `LABEL ... io.hass.version="X.Y.Z"`

Prepend a section to `redalert/CHANGELOG.md`:

```markdown
## X.Y.Z

- **<area>:** <what changed and why, user-facing>.
```

Commit (`X.Y.Z: <summary>`), push, then wait for CI green (see CLAUDE.md snippet),
backgrounded.

## 3. Tag

```bash
git -c user.name="Daniel Ring" -c user.email="daniel.ring@web.de" \
  tag -a vX.Y.Z -m "Red Alert Entertainment X.Y.Z

<2-3 sentence summary of the release>. CI green (lint + amd64/aarch64)."
git push origin vX.Y.Z
```

Tag name is `vX.Y.Z` (leading `v`). Annotated, not lightweight.

## 4. GitHub release

```bash
gh release create vX.Y.Z --verify-tag --latest \
  --title "Red Alert Entertainment X.Y.Z" \
  --notes "<see structure below>"
```

`--verify-tag` (tag must already exist on the remote) and `--latest`. Not a draft,
not a prerelease.

Notes structure (German, matches prior releases):
- One-line intro; if intermediate versions weren't released, say
  "Enthält alle Änderungen seit A.B.C."
- `## Geändert` / `## Neu` / `## Fix` sections as applicable — describe the
  user-visible behaviour, not the code.
- `## Installation` — the 3-step store-repo flow, and "Bestehende Installation:
  auf X.Y.Z aktualisieren."
- Footer: `Vollständige Doku: .../blob/vX.Y.Z/redalert/DOCS.md` and
  `**Changelog:** .../compare/vA.B.C...vX.Y.Z`.

## 5. Verify

```bash
gh release view vX.Y.Z --json url,tagName,targetCommitish,isDraft
gh release list
```

Report the release URL. `gh release view --json isLatest` is **not** a valid
field — use `gh release list` (shows the `Latest` marker).
