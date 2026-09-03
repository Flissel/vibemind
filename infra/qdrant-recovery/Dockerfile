ARG BASE_IMAGE=qdrant/qdrant:v1.12.6@sha256:89d9d35757eb57c62973c193c96b5b50ca73bbaff7fa282ef81f7fd155a3747d
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="VibeMind Qdrant recovery image" \
      org.opencontainers.image.version="v1.18.0-recovery" \
      org.opencontainers.image.source="https://github.com/qdrant/qdrant/releases/tag/v1.18.0" \
      vibemind.recovery.base="qdrant-v1.12.6-pinned" \
      vibemind.recovery.asset-sha256="76c38c3859682776d2bef61bf6c23b593b7c06682578f7c9ff9eac79c87a4268"

COPY qdrant /qdrant/qdrant
RUN chmod 0755 /qdrant/qdrant
