# BinderHub entrypoint — pinned to a published GHCR digest for fast, deterministic builds.
#
# Built from the CI publish workflow. The digest below is the latest published
# image of ghcr.io/sashakile/cositos-binder. Update it after each publish run.
#
# How to update:
#   1. Run the publish workflow (or push to main).
#   2. Find the new digest: docker pull ghcr.io/sashakile/cositos-binder:sha-<commit>
#   3. Replace the digest below.

ARG BINDER_IMAGE=ghcr.io/sashakile/cositos-binder@sha256:c14aaa09a984e915ffa8270d156ac7c684602c8ea5cc0cdde880e435bf12276a
FROM ${BINDER_IMAGE}

USER root

# Copy start script (must be done here since the pinned image is a frozen snapshot)
COPY --chown=1000:100 .binder/start.sh /home/jovyan/.binder/start.sh
RUN chmod +x /home/jovyan/.binder/start.sh

USER 1000
WORKDIR /home/jovyan