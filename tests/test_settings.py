from entregacerta.settings import load_settings
import pytest


def test_missing_llm_key_does_not_block_environment_and_repr_hides_secret(tmp_path):
    settings = load_settings(tmp_path, {"ENTREGACERTA_LLM_API_KEY": "technical-test-secret"})
    assert "technical-test-secret" not in repr(settings)
    assert load_settings(tmp_path, {}).llm_api_key == ""


def test_environment_overrides_local_file_without_changing_process(tmp_path):
    (tmp_path / ".env").write_text("ENTREGACERTA_API_PORT=8005\n", encoding="utf-8")
    assert load_settings(tmp_path, {"ENTREGACERTA_API_PORT": "8006"}).api_port == 8006


@pytest.mark.parametrize("values", [
    {"ENTREGACERTA_API_PORT": "0"},
    {"ENTREGACERTA_API_PORT": "8502"},
    {"ENTREGACERTA_LLM_TIMEOUT_SECONDS": "0"},
])
def test_invalid_configuration_is_rejected(tmp_path, values):
    with pytest.raises(ValueError):
        load_settings(tmp_path, values)
