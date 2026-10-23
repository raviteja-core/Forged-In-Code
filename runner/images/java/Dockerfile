# ForgeRun Java Sandbox Runner Image
FROM eclipse-temurin:21-jdk-jammy

RUN groupadd -g 10001 runner && \
    useradd -u 10001 -g runner -m -s /sbin/nologin runner && \
    mkdir -p /workspace /tmp && \
    chown -R runner:runner /workspace /tmp && \
    chmod 700 /workspace /tmp

RUN rm -rf /var/lib/apt/lists/* /root/.cache /usr/bin/chfn /usr/bin/chsh /usr/bin/passwd

WORKDIR /workspace
USER 10001:10001

ENV PATH="/opt/java/openjdk/bin:/usr/local/bin:/usr/bin:/bin"

ENTRYPOINT ["/bin/sh", "-c"]
