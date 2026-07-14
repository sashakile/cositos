# BinderHub entrypoint — thin image pinned to a deterministic GHCR digest.
#
# BinderHub builds this file. It starts from a published Binder image (which is
# Dockerfile.binder built on top of Dockerfile.binder-base) and adds the labextension
# assets + start scripts.
#
# The base image is pinned to an immutable digest so Binder builds are deterministic.
# Update the digest below after a successful publish workflow run.
#
# How to update:
#   1. Push to main (or run the publish workflow manually).
#   2. Find the new digest at https://github.com/sashakile/cositos/pkgs/container/cositos-binder
#   3. Replace the digest below.
#
# For local testing without a published image:
#   mise run binder-local

ARG BINDER_IMAGE=ghcr.io/sashakile/cositos-binder@sha256:0000000000000000000000000000000000000000000000000000000000000000
FROM ${BINDER_IMAGE}

USER root

# Copy start script
COPY --chown=1000:100 .binder/start.sh /home/jovyan/.binder/start.sh
RUN chmod +x /home/jovyan/.binder/start.sh

USER 1000
WORKDIR /home/jovyan