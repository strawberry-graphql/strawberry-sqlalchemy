import nox
from nox_poetry import Session, session

nox.options.reuse_existing_virtualenvs = True
nox.options.error_on_external_run = True

PYTHON_VERSIONS = ["3.13", "3.12", "3.11", "3.10", "3.9", "3.8"]


COMMON_PYTEST_OPTIONS = [
    "--cov=.",
    "--cov-append",
    "--cov-report=xml",
    "-n",
    "auto",
    "--showlocals",
    "-vv",
]


def poetry_install_run_always(session: Session) -> None:
    session.run_always("poetry", "install", external=True)


@session(python=PYTHON_VERSIONS, name="SQLAlchemy 2.0 Tests", tags=["tests"])
def tests_sqlalchemy_latest(session: Session) -> None:
    session.run_always(
        "poetry",
        "run",
        "pip",
        "install",
        "--upgrade",
        "pip",
        "setuptools",
        "wheel",
        external=True,
    )
    poetry_install_run_always(session)

    session.run(
        "pytest",
        *COMMON_PYTEST_OPTIONS,
    )


# No need for now to run 1.4 against all 5 python versions.
@session(python="3.11", name="Sqlalchemy 1.4 Tests", tags=["tests"])
def tests_sqlalchemy_1_4(session: Session) -> None:
    session.run_always(
        "poetry",
        "run",
        "pip",
        "install",
        "--upgrade",
        "pip",
        "setuptools",
        "wheel",
        external=True,
    )
    poetry_install_run_always(session)
    session._session.install("sqlalchemy~=1.4")

    session.run(
        "pytest",
        *COMMON_PYTEST_OPTIONS,
    )


@session(name="Mypy", tags=["lint"])
def mypy(session: Session) -> None:
    poetry_install_run_always(session)

    session.run(
        "mypy",
        "--install-types",
        "--non-interactive",
        "--cache-dir=.mypy_cache/",
        "--config-file",
        "mypy.ini",
    )


@session(name="Ruff Lint", tags=["lint"])
def ruff_lint(session: Session) -> None:
    poetry_install_run_always(session)

    session.run(
        "ruff",
        "check",
        "--no-fix",
        ".",
        silent=False,
    )


@session(name="Ruff Format", tags=["format"])
def ruff_format(session: Session) -> None:
    poetry_install_run_always(session)

    session.run(
        "ruff",
        "format",
        "--check",
        "--diff",
        ".",
        silent=False,
    )
