# syntax=docker/dockerfile:1.6
#
# Cross-build flow:
#   docker buildx build --platform=linux/arm/v7 \
#     --tag ghcr.io/bdherouville/vdsensor-rs:latest --push .
#
# Native dev build:
#   docker build -t vdsensor-rs:dev .
#
# Image strategy:
#   Builder = rust:1.95-slim-bookworm — multi-arch, includes linux/arm/v7
#            (rust:alpine does NOT publish an armv7 variant).
#   Runtime = gcr.io/distroless/cc-debian12:nonroot — multi-arch, ~22 MB,
#            has glibc + libgcc which the dynamically-linked Rust binary
#            needs.
#
# Templates and static assets are baked into the binary at compile-time via
# include_str! / include_bytes!, so the runtime container ships only the
# binary itself.

ARG RUST_VERSION=1.95

# --- builder ---------------------------------------------------------------

FROM rust:${RUST_VERSION}-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        pkg-config \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy Cargo manifests first so dep resolution caches even when src changes.
COPY Cargo.toml Cargo.lock ./

# Placeholder src so cargo can resolve + pre-build deps in a cached layer.
RUN mkdir -p src && \
    echo "fn main() {}" > src/main.rs && \
    echo "// placeholder" > src/lib.rs

RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/target \
    cargo build --release && \
    rm -rf src

# Real source.
COPY src ./src

RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/target \
    cargo build --release && \
    cp target/release/vdsensor /vdsensor && \
    strip /vdsensor

# --- runtime ---------------------------------------------------------------

FROM gcr.io/distroless/cc-debian12:nonroot AS runtime

COPY --from=builder /vdsensor /vdsensor

ENV VDSENSOR_DB_PATH=/data/vdsensor.db
ENV VDSENSOR_HTTP_PORT=8080
ENV VDSENSOR_LOG=info

EXPOSE 8080

# /data is created by the docker-compose volume mount at runtime. The Rust
# binary creates the SQLite file inside it on first boot.
VOLUME ["/data"]

ENTRYPOINT ["/vdsensor"]
CMD ["serve"]
