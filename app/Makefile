# Helpers for build / push / local iteration.
# Override IMAGE on the command line:  make push IMAGE=ghcr.io/me/vdsensor

IMAGE   ?= ghcr.io/CHANGE-ME/vdsensor
TAG     ?= latest
GH_USER ?= $(shell gh api user --jq .login 2>/dev/null)
PYTHON  ?= .venv/bin/python

.PHONY: dev test lint serve-fake build-native build-armv7 push qemu-binfmt ghcr-login

dev:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

serve-fake:
	$(PYTHON) -m vdsensor.cli --fake -v serve --http-port 8080

# Build the native-architecture image — quick smoke check that the Dockerfile
# is well-formed. Use this before attempting the cross-build.
build-native:
	docker build -t vdsensor:dev .

# One-time host setup for cross-build: register QEMU binfmt handlers so that
# linux/arm/v7 binaries can run under emulation. Requires sudo / root.
qemu-binfmt:
	docker run --privileged --rm tonistiigi/binfmt --install arm

# Authenticate `docker login ghcr.io` using a short-lived token derived from
# the gh CLI's SSH-authenticated session — no PAT stored on disk. See
# docs/REGISTRY.md for the one-time `gh auth login -p ssh` setup.
ghcr-login:
	@if [ -z "$(GH_USER)" ]; then \
	  echo "gh CLI not logged in. Run: gh auth login -p ssh -s write:packages,read:packages" >&2; \
	  exit 1; \
	fi
	@gh auth token | docker login ghcr.io -u "$(GH_USER)" --password-stdin

# Cross-build for the BeagleBone (ARMv7); does not push.
build-armv7: qemu-binfmt
	docker buildx build --platform=linux/arm/v7 --tag $(IMAGE):$(TAG) --load .

# Cross-build + push to GHCR. Tags both :$(TAG) and :latest.
# Requires `make qemu-binfmt` to have been run once on the host.
push: ghcr-login
	docker buildx build --platform=linux/arm/v7 \
	    --tag $(IMAGE):$(TAG) \
	    --tag $(IMAGE):latest \
	    --push .
