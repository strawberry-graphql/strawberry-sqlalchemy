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


@session(python=PYTHON_VERSIONS, name="Tests", tags=["tests"])
def tests(session: Session) -> None:
    session.run_always(
        "poetry", "run", "pip", "install", "--upgrade", "pip", external=True
    )
    session.run_always("poetry", "install", external=True)

    session.run(
        "pytest",
        *COMMON_PYTEST_OPTIONS,
    )


@session(name="Mypy", tags=["lint"])
def mypy(session: Session) -> None:
    session.run_always("poetry", "install", external=True)

    session.run("mypy", "--config-file", "mypy.ini")
