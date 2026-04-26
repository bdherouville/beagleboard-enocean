# syntax=docker/dockerfile:1.6
# Multi-stage build. Stage 1 wheels everything; stage 2 is a slim runtime
# that pip-installs from /wheels with no network access.
#
# Cross-build for the BeagleBone Black (ARMv7):
#   docker buildx build --platform=linux/arm/v7 \
#     --tag ghcr.io/<user>/vdsensor:latest --push .
#
# Native dev build (the host's own architecture):
#   docker build -t vdsensor:dev .

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# Build deps. cargo is only needed if pip falls back to source for
# pydantic-core (which has no published armv7 wheel as of writing).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cargo \
        rustc \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src

# Build wheels for every dep + the project itself. BuildKit cache mounts make
# subsequent rebuilds cheap by preserving the pip + cargo registries across
# layer invalidations.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    --mount=type=cache,target=/root/.cargo/registry,sharing=locked \
    --mount=type=cache,target=/root/.cargo/git,sharing=locked \
    pip wheel --wheel-dir /wheels --prefer-binary .


FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Non-root user; supplementary 'dialout' group so /dev/ttyO4 is readable.
# GID 20 matches the default Debian-on-BBB dialout. Verify on the target with
# `getent group dialout` and adjust via `--group-add` at compose time if needed.
RUN groupadd --system --gid 20 dialout || true \
    && useradd --system --no-create-home --shell /usr/sbin/nologin \
       --gid users --groups dialout vdsensor \
    && install -d -o vdsensor -g users /data

COPY --from=builder /wheels /wheels
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --no-index --find-links=/wheels vdsensor \
    && rm -rf /wheels

USER vdsensor
WORKDIR /home/vdsensor

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VDSENSOR_DB_PATH=/data/vdsensor.db \
    VDSENSOR_HTTP_PORT=8080

EXPOSE 8080

# Single command: read settings from VDSENSOR_* env, run the FastAPI server.
# Settings → CLI flag mapping: serial port from $VDSENSOR_SERIAL_PORT (default
# /dev/ttyO4); MQTT from $VDSENSOR_MQTT_URL (omit to disable).
CMD ["python", "-m", "vdsensor.main"]
