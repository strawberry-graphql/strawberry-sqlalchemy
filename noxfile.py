import nox
from nox_poetry import Session, session

nox.options.reuse_existing_virtualenvs = True
nox.options.error_on_external_run = True

PYTHON_VERSIONS = ["3.12", "3.11", "3.10", "3.9", "3.8"]


COMMON_PYTEST_OPTIONS = [
    "--cov=.",
    "--cov-append",
    "--cov-report=xml",
    "-n",
    "auto",
    "--showlocals",
    "-vv",
]


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
    session.run_always("poetry", "install", external=True)

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
    session.run_always("poetry", "install", external=True)
    session._session.install("sqlalchemy~=1.4")

    session.run(
        "pytest",
        *COMMON_PYTEST_OPTIONS,
    )


@session(name="Mypy", tags=["lint"])
def mypy(session: Session) -> None:
    session.run_always("poetry", "install", external=True)

    session.run(
        "mypy",
        "--install-types",
        "--non-interactive",
        "--cache-dir=.mypy_cache/",
        "--config-file", 
        "mypy.ini"
    )


@session(name="Black", tags=["lint"])
def black(session: Session) -> None:
    session.run_always("poetry", "install", external=True)

    session.run(
        "black",
        "--check",
        "--diff",
        ".",
        success_codes=[0, 1]
    )


@session(name="Ruff", tags=["lint"])
def ruff(session: Session) -> None:
    session.run_always("poetry", "install", external=True)

    session.run(
        "ruff",
        "check",
        "--diff",
        ".",
        success_codes=[0, 1]
    )