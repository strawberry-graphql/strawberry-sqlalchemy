ARG VARIANT=3.8
FROM mcr.microsoft.com/vscode/devcontainers/python:${VARIANT}


# Install Poetry and pre-commit
RUN pip3 install poetry pre-commit

ARG PGVERSION=14
ARG TARGETPLATFORM

# Setup Postgres repo and install packages

# Add PostgreSQL APT repository and key (only if PGVERSION is not "none")
RUN if [ "${PGVERSION}" != "none" ]; then \
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    | gpg --dearmor --yes -o /usr/share/keyrings/postgresql.gpg; \
    fi

# Install PostgreSQL packages using APT cache mount
RUN --mount=type=cache,target=/var/cache/apt,id=apt-${TARGETPLATFORM} \
    if [ "${PGVERSION}" != "none" ]; then \
    apt-get update && \
    apt-get -y install --no-install-recommends \
    postgresql-${PGVERSION} \
    postgresql-client-${PGVERSION} \
    postgresql-server-dev-${PGVERSION} && \
    apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

# Configure Postgres to trust local connections
RUN if [ "${PGVERSION}" != "none" ]; then \
    sed -i -E 's/local(\s+)all(\s+)postgres(\s+)peer/local\1all\2all\3trust/g' \
    /etc/postgresql/${PGVERSION}/main/pg_hba.conf && \
    sed -i -E 's/host(\s+)all(\s+)all(\s+)(\S+)(\s+)(\S+)/host\1all\2all\3\4\5trust/g' \
    /etc/postgresql/${PGVERSION}/main/pg_hba.conf; \
    fi
