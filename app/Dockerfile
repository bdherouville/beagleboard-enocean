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

# We run as root inside the container. Two reasons:
#   1. /sys/class/gpio/export is owned by root and we need to write it for
#      the daughter-board status LEDs (and the GPIO identification button).
#      `privileged: true` in docker-compose makes /sys writable but doesn't
#      change file ownership, so a non-root container user still couldn't
#      write the export file.
#   2. The container is single-purpose, behind a LAN, and the host's docker
#      daemon already isolates it from the rest of the system.
# Keep the data dir owned by root.
RUN install -d /data

COPY --from=builder /wheels /wheels
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --no-index --find-links=/wheels vdsensor \
    && rm -rf /wheels

WORKDIR /root

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VDSENSOR_DB_PATH=/data/vdsensor.db \
    VDSENSOR_HTTP_PORT=8080

EXPOSE 8080

# Single command: read settings from VDSENSOR_* env, run the FastAPI server.
# Settings → CLI flag mapping: serial port from $VDSENSOR_SERIAL_PORT (default
# /dev/ttyS4); MQTT from $VDSENSOR_MQTT_URL (omit to disable).
CMD ["python", "-m", "vdsensor.main"]
