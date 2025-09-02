# Stage 1: build caddy with caddy-l4
FROM caddy:builder AS builder
RUN xcaddy build \
  --with github.com/mholt/caddy-l4

# Stage 2: runtime
FROM caddy:latest
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
