# Stage 1: build caddy with caddy-l4
FROM caddy:2.11.9-builder AS builder
RUN xcaddy build \
  --with github.com/mholt/caddy-l4

# Stage 2: runtime
FROM caddy:2.11.9
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
