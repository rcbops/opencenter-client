#!/usr/bin/env bash

# override default endpoint
# OPENCENTER_ENDPOINT=http://localhost:8080

for d in {1..9}; do
    r2 node create --hostname="test-host-${d}" --backend="unprovisioned" --backend_state="unknown"
done

for d in {1..3}; do
    r2 cluster create --name="test-cluster-${d}"
done

r2 node create --hostname="chef-server" --backend="chef-server" --backend_state="ready"
