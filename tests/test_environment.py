import importlib
import sys

import pytest


RUNTIME_MODULES = (
    "confluent_kafka",
    "dotenv",
    "openai",
    "pydantic",
    "requests",
)


def test_supported_python_version() -> None:
    assert sys.version_info[:2] == (3, 11)


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_dependency_imports_without_openai_key(
    module_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    importlib.import_module(module_name)
