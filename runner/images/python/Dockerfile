# ForgeRun Python Sandbox Runner Image
FROM python:3.10-slim-bookworm

# Create non-root execution user and directories
RUN groupadd -g 10001 runner && \
    useradd -u 10001 -g runner -m -s /sbin/nologin runner && \
    mkdir -p /workspace /tmp && \
    chown -R runner:runner /workspace /tmp && \
    chmod 700 /workspace /tmp

# Remove extraneous tools to minimize attack surface
RUN rm -rf /var/lib/apt/lists/* /root/.cache /usr/bin/chfn /usr/bin/chsh /usr/bin/passwd

WORKDIR /workspace
USER 10001:10001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/usr/local/bin:/usr/bin:/bin"

ENTRYPOINT ["python3"]
