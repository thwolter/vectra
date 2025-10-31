import pytest

from core.utils import ValidatedModel, ValidatedSettings


class DummySettings(ValidatedSettings):
    required_keys = ['required_value']
    required_value: str | None = None


class DummyModel(ValidatedModel):
    required_keys = ['required_field']
    required_field: str | None = None
    optional_field: str | None = None


def test_missing_required_value_warns_in_testing_env(monkeypatch):
    monkeypatch.setenv('ENV', 'testing')

    settings = DummySettings()

    with pytest.warns(UserWarning, match='Missing required environment keys: REQUIRED_VALUE'):
        settings.check_missing_keys()

    monkeypatch.delenv('ENV', raising=False)


def test_missing_required_value_errors_outside_testing_env(monkeypatch):
    monkeypatch.setenv('ENV', 'production')

    settings = DummySettings()

    with pytest.raises(RuntimeError, match='Missing required environment keys: REQUIRED_VALUE'):
        settings.check_missing_keys()

    monkeypatch.delenv('ENV', raising=False)



def test_missing_required_field_warns_in_testing_env(monkeypatch):
    monkeypatch.setenv('ENV', 'testing')

    model = DummyModel()

    with pytest.warns(UserWarning, match='Missing required environment keys: REQUIRED_FIELD'):
        model.check_missing_keys()

    monkeypatch.delenv('ENV', raising=False)


def test_missing_required_field_errors_outside_testing_env(monkeypatch):
    monkeypatch.setenv('ENV', 'production')

    model = DummyModel()

    with pytest.raises(RuntimeError, match='Missing required environment keys: REQUIRED_FIELD'):
        model.check_missing_keys()

    monkeypatch.delenv('ENV', raising=False)


def test_set_required_field_passes(monkeypatch):
    monkeypatch.setenv('ENV', 'production')
    monkeypatch.setenv('REQUIRED_FIELD', 'value')

    model = DummySettings()
    model.required_value = 'value'

    assert model.check_missing_keys() == []

    monkeypatch.delenv('ENV', raising=False)
