ARG VARIANT=3.8
FROM mcr.microsoft.com/vscode/devcontainers/python:${VARIANT}

RUN pip3 install poetry pre-commit
RUN poetry config virtualenvs.in-project true
ARG PGVERSION=14

# Setup apt repo for Postgres
RUN if [ "${PGVERSION}" != "none"  ]; then \
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main"  \
    | tee /etc/apt/sources.list.d/pgdg.list \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    | gpg --dearmor --yes -o /usr/share/keyrings/postgresql.gpg; \
    fi

# Install Postgres packages
ARG TARGETPLATFORM
RUN --mount=type=cache,target=/var/cache/apt,id=apt-${TARGETPLATFORM} \
    export DEBIAN_FRONTEND=noninteractive \
    && export PGPACKAGES=$(if [ "${PGVERSION}" != "none" ]; then echo "postgresql-${PGVERSION} postgresql-client-${PGVERSION} postgresql-server-dev-${PGVERSION}"; fi) \
    && apt-get remove man-db --purge -y \
    && apt-get update \
    && apt-get -y install --no-install-recommends ${PGPACKAGES}

# Trust postgres connections from localhost and local port.
RUN if [ "$PGVERSION" != "none" ]; then \
        sed -i -E 's/local(\s+)all(\s+)postgres(\s+)peer/local\1all\2all\3trust/g' /etc/postgresql/${PGVERSION}/main/pg_hba.conf && \
        sed -i -E 's/host(\s+)all(\s+)all(\s+)(\S+)(\s+)(\S+)/host\1all\2all\3\4\5trust/g' /etc/postgresql/${PGVERSION}/main/pg_hba.conf; \
    fi
