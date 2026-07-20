# CI Maintainer Notes

Operational steps that a `gramps-project/addons-source` maintainer
needs to handle once PR 820 (and the branch-neutral follow-up) lands.
The pipeline is otherwise self-driving — this document is only about
the rough edges.

For day-to-day addon-release maintenance see [MAINTAINERS.md](../MAINTAINERS.md);
for the contributor-facing summary of what a green CI check means on
an unreleased branch see [CONTRIBUTING.md](../CONTRIBUTING.md#work-towards-a-merge).

## Contents

1. [One-time setup when the PR first merges](#one-time-setup-when-the-pr-first-merges)
2. [Creating a new maintenance branch](#creating-a-new-maintenance-branch)
3. [When a Gramps minor release lands on PyPI](#when-a-gramps-minor-release-lands-on-pypi)
4. [Diagnostic log markers](#diagnostic-log-markers)
5. [Optional future-proofing knobs](#optional-future-proofing-knobs)

## One-time setup when the PR first merges

### 1. Make the `gramps-ci` GHCR package public

`docker-build.yml` pushes images to
`ghcr.io/gramps-project/addons-source/gramps-ci:<suffix>` using the
workflow's `GITHUB_TOKEN`. GHCR creates the package as **private** the
first time. Same-repo CI keeps working (token covers own packages),
but **fork PRs cannot pull the image** because their `GITHUB_TOKEN`
has no read access to private packages in `gramps-project`. Fork-PR
container jobs would fail at "Initialize containers" with an
authentication error.

Fix once, immediately after the first `Build Docker Images` run
finishes:

1. Go to <https://github.com/orgs/gramps-project/packages/container/addons-source%2Fgramps-ci/settings>
2. Under "Danger Zone" → "Change visibility" → set to **Public**

Every existing and future `gramps-ci:<suffix>` tag inherits public
visibility from this single setting.

### 2. Expect the first-push race on `maintenance/gramps60`

The first push event after merge fires both workflows in parallel:

- `Build Docker Images` builds and pushes `gramps-ci:gramps60`
  (~5 min cold).
- `CI` runs `setup` (~2 s), then its container jobs try to pull the
  image.

Because both start on the same push, the CI container jobs race the
image push and may fail at "Initialize containers" the first time.
This race only happens once per branch:

1. Wait for `Build Docker Images` to complete.
2. Open the failed CI run → click "Re-run failed jobs".
3. Subsequent pushes find the image already in GHCR — no race.

This is also explained in the header comment of `ci.yml`.

## Creating a new maintenance branch

When a new Gramps minor series goes into development and addons need
a corresponding branch (e.g. `maintenance/gramps62` once 6.2 opens):

```
git branch maintenance/gramps62 maintenance/gramps61
git push origin maintenance/gramps62
```

No *workflow* edits required — the workflows derive everything from
`github.ref_name`. The first push fires the same race described
above — re-run the failed CI jobs once `Build Docker Images`
finishes.

One file is NOT auto-derived and must be bumped by hand on the new
branch: **`.github/environment.yml`**'s gramps pin (`gramps>=6.0,<6.1`).
The conda Windows lane installs gramps from PyPI through that pin, so
until you bump it to the new series (e.g. `>=6.2,<6.3`) — and the
series is actually published on PyPI — the Windows lane keeps
validating addons against the old series. `ci.yml`'s "Report
gramps-vs-branch series" step prints a loud `::warning::` while the two
diverge; it does not fail.

The setup job's regex (`gramps[0-9][0-9]`) requires a two-digit
suffix. When Gramps 10.0 opens this regex needs updating in two
places (`ci.yml` setup job and `docker-build.yml` params step).

## When a Gramps minor release lands on PyPI

The hybrid Dockerfile auto-detects PyPI availability:

- `pip install "gramps==X.Y.*"` succeeds → image installs the tagged
  PyPI release (`::notice::` log line).
- pip reports "No matching distribution found" → image falls back to a
  SHA-pinned `git clone` of `gramps-project/gramps@maintenance/grampsNN`
  at the SHA captured by `docker-build.yml`'s params step
  (`::warning::` log line).

When `gramps==6.1.0` is finally published to PyPI, the next image
rebuild on `maintenance/gramps61` silently switches from "git tip" to
"PyPI release" — no maintainer action needed.

To **immediately** rebuild against the new PyPI release without
waiting for the next push:

1. Open the `Build Docker Images` workflow in the Actions tab.
2. "Run workflow" → select `maintenance/grampsNN` → Run.

The `::notice::` line in the build log confirms the switch.

## Diagnostic log markers

When investigating a CI failure, the install-step output in
`Build Docker Images` carries these annotations:

| Annotation | Meaning |
| --- | --- |
| `::notice::installed gramps==X.Y.* from PyPI` | Released-path install. CI is testing against a tagged release. |
| `::warning::no gramps==X.Y.* on PyPI; installing from gramps-project/gramps@maintenance/grampsNN at <sha>` | Unreleased-branch fallback. CI is testing against the upstream branch tip at `<sha>`. Visible to contributors via the CONTRIBUTING.md note. |
| `::error::no gramps==X.Y.* on PyPI and GRAMPS_FALLBACK_SHA is unset` | `git ls-remote` in `docker-build.yml`'s params step returned no SHA for `maintenance/grampsNN` on `gramps-project/gramps`. The matching upstream branch is missing, or the addons-source branch is misnamed. |
| `::error::pip install gramps failed (non-version reason)` | pip failed for a network/registry reason, not because the version is missing. Captured stderr is dumped after the line. The build does **not** fall back to git in this case — by design, so a transient PyPI hiccup cannot silently flip a released branch into "git tip" mode. |

Other useful entry points:

- `ci.yml` setup job log shows the derived `branch_suffix` and
  `ci_image`. A failure here means the branch name doesn't match
  `maintenance/gramps[0-9][0-9]`.
- `docker-build.yml` params step log shows the captured
  `fallback_sha`. An empty value means upstream `gramps-project/gramps`
  has no matching maintenance branch (warning issued; image build will
  fail iff the fallback is needed).

## Optional future-proofing knobs

Not needed today; record here in case they ever come up.

### Upstream gramps repo URL

The Dockerfile hardcodes `https://github.com/gramps-project/gramps.git`
as the fallback source. If the project ever reorgs or renames, this
URL must change in one place (`.github/docker/gramps-ci/Dockerfile`).
It could be parameterised as a build arg (`ARG GRAMPS_UPSTREAM_REPO`)
with the current URL as default, but a hardcoded value keeps the
Dockerfile simpler and a rename is a sufficiently large event that
editing one string is not the bottleneck.

### GHCR tag retention

`docker-build.yml` pushes both a moving `gramps-ci:<suffix>` tag (e.g.
`gramps60`) and a per-commit `gramps-ci:<suffix>-<short-sha>` tag.
The moving tag is always overwritten; the SHA tags accumulate over
time. Set a retention policy on the GHCR package settings page if
the count becomes inconvenient — the moving tags are what CI consumes.
