# syntax=docker/dockerfile:1.6
#
# Cross-build flow:
#   docker buildx build --platform=linux/arm/v7 \
#     --tag ghcr.io/bdherouville/vdsensor-rs:latest --push .
#
# Native dev build:
#   docker build -t vdsensor-rs:dev .
#
# Image strategy: rust:alpine builder produces a static musl ELF, scratch
# runtime ships only that single binary. Templates and static assets are
# baked into the binary at compile-time via include_str! / include_bytes!.

ARG RUST_VERSION=1.95

# --- builder ---------------------------------------------------------------

FROM rust:${RUST_VERSION}-alpine AS builder

# musl-dev gets us a libc + linker for static linking on alpine.
# build-base has cc/ar/etc. for libsqlite3-sys's bundled C build.
RUN apk add --no-cache musl-dev build-base

WORKDIR /build

# Copy Cargo manifests first so dep resolution caches even when src changes.
COPY Cargo.toml Cargo.lock ./

# Touch a placeholder src so cargo can resolve and pre-build deps.
RUN mkdir -p src && \
    echo "fn main() {}" > src/main.rs && \
    echo "// placeholder" > src/lib.rs

# Pre-build dependencies in a cached layer. Strip the placeholder afterwards.
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/target \
    cargo build --release && \
    rm -rf src

# Now the real source.
COPY src ./src

RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/target \
    cargo build --release && \
    cp target/release/vdsensor /vdsensor && \
    strip /vdsensor

# --- runtime ---------------------------------------------------------------

FROM scratch AS runtime

COPY --from=builder /vdsensor /vdsensor

ENV VDSENSOR_DB_PATH=/data/vdsensor.db
ENV VDSENSOR_HTTP_PORT=8080
ENV VDSENSOR_LOG=info

EXPOSE 8080

# /data is created by the docker-compose volume mount at runtime. The
# Rust binary creates the SQLite file inside it on first boot.
VOLUME ["/data"]

ENTRYPOINT ["/vdsensor"]
CMD ["serve"]
