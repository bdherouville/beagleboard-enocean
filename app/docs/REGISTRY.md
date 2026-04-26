# Building & pushing the ARMv7 image to GHCR

The dev host is x86_64; the BBB is ARMv7 (Cortex-A8 @ 1 GHz). The image is
**cross-built somewhere with QEMU emulation, pushed to GHCR, pulled by the
BBB** — the BBB never builds.

Two equivalent build paths are wired:

1. **GitHub Actions** (`.github/workflows/build-and-push.yml`) — recommended
   for anything past prototype. The hosted runners come with QEMU
   pre-registered, `GITHUB_TOKEN` already has `packages:write`, and BuildKit
   GHA cache survives between runs. **Zero auth plumbing on your machines.**
2. **Local cross-build** (`make push`) — for one-off iteration when you need
   the result faster than a CI round-trip. Auth uses `gh auth login -p ssh`
   so `docker login ghcr.io` consumes a token derived from the
   SSH-authenticated GitHub CLI session instead of a long-lived PAT on disk.

## Path 1 — GitHub Actions (recommended)

The workflow at `.github/workflows/build-and-push.yml` triggers on:

| Trigger | Tags applied |
|---|---|
| push to `main` | `:latest` + `:sha-XXXXXXX` |
| push of a `v*` git tag | `:vX.Y.Z` + `:sha-XXXXXXX` |
| pull request to `main` | builds only, does not push |
| `workflow_dispatch` (manual) | `:sha-XXXXXXX` |

Setup once:

1. Push the repo to GitHub.
2. Settings → Actions → General → "Workflow permissions" → check
   *Read and write permissions* (so `GITHUB_TOKEN` can push to GHCR).
3. (Optional) Settings → Packages → switch the `vdsensor` package
   visibility to *public* if you want anonymous pulls; otherwise the BBB
   needs to log in (`gh auth login -s read:packages` then
   `gh auth token | docker login ghcr.io -u <user> --password-stdin`).

Then a `git push` is the whole release loop. Watch the run in the Actions
tab; on success, GHCR has the new image.

The first run of a fresh repo takes ~10 min (pydantic-core compiles from
source under QEMU). Subsequent runs hit the GitHub Actions cache and finish
in 1–2 min.

## Path 2 — Local cross-build (when CI is too slow)

### Prerequisites on the build host

#### 1. QEMU binfmt for cross-arch builds

Cross-arch builds need the kernel to know how to execute ARMv7 binaries
under emulation:

```bash
make qemu-binfmt
# Fedora alternative:  sudo dnf install qemu-user-static && sudo systemctl restart systemd-binfmt
```

Verify:

```bash
ls /proc/sys/fs/binfmt_misc/ | grep arm    # expect 'qemu-arm'
docker buildx ls                            # builder lists 'linux/arm/v7'
```

#### 2. SSH-based GitHub authentication

Use the `gh` CLI (`dnf install gh` on Fedora, `apt install gh` on Debian).
On first use, log in over SSH and grant the package scopes the
build needs:

```bash
gh auth login --hostname github.com --git-protocol ssh \
              --scopes write:packages,read:packages
# (Opens a browser once to confirm; afterwards your SSH key is what GitHub
#  trusts. No PAT is stored.)
```

Verify the token actually carries the package scopes:

```bash
gh auth status                              # shows the active scopes
```

If you already had `gh` set up without `write:packages`, add it without
re-logging-in:

```bash
gh auth refresh --hostname github.com --scopes write:packages,read:packages
```

## Build & push

The Makefile drives both steps. `make push` runs `gh auth token | docker
login ghcr.io ...` and then `docker buildx build --push`.

```bash
make push IMAGE=ghcr.io/<your-gh-user>/vdsensor TAG=$(git rev-parse --short HEAD)
```

The first build is **slow** (~5–10 min) because `pydantic-core` (Rust)
doesn't publish a `linux/arm/v7` wheel and recompiles from source under
QEMU emulation. BuildKit cache mounts (`/root/.cache/pip`, `/root/.cargo/*`)
make subsequent builds fast as long as the cache survives.

After push, verify the manifest carries the right platform:

```bash
docker buildx imagetools inspect ghcr.io/<your-gh-user>/vdsensor:latest
# Expect:    Platform: linux/arm/v7
```

## Image visibility

GHCR packages are **private by default**. Either:

- Flip the package to public via the GitHub web UI (Settings → Packages →
  Change visibility), or
- Keep it private and have the BBB log in the same SSH-derived way.

## On the BBB

```bash
# One-time: install gh and authenticate using the same SSH key flow.
sudo apt install gh
gh auth login --hostname github.com --git-protocol ssh --scopes read:packages
gh auth token | docker login ghcr.io -u <your-gh-user> --password-stdin

cd /opt/vdsensor                            # holds docker-compose.yml + .env
docker compose pull
docker compose up -d
```

The `docker login` credential is stored in `~/.docker/config.json`. To
refresh after `gh auth login` rotates: re-run the
`gh auth token | docker login` line.

## Why this is safer than a PAT

- The token is short-lived (gh session) — no stale long-lived secret on disk.
- It rotates whenever you `gh auth login` again, no calendar reminder needed.
- The trust chain is your SSH key, which you already manage; nothing extra
  to revoke when a laptop is decommissioned.

## Path 3 — Build natively on the BBB (no cross, no registry)

`git pull && docker build -t local/vdsensor app/` right on the device. Slow
(~15 min the first time, faster on rebuilds thanks to layer cache) but
needs zero infrastructure. Suitable when releases are infrequent and you
don't want a registry at all. Update `docker-compose.yml` to reference
`local/vdsensor:latest` instead of the GHCR image.
