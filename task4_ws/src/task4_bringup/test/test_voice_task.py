"""Check that rejected audio cannot publish and that accepted audio is preserved."""

import hashlib
from io import BytesIO
import json
from unittest.mock import patch
import wave

import pytest

from task4_bringup import voice_task


def pcm_wav(channels=1):
    audio = BytesIO()
    with wave.open(audio, "wb") as stream:
        stream.setparams((channels, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(bytes(3200 * channels))
    return audio.getvalue()


def test_invalid_wav_rejected_before_loading_model(tmp_path):
    with pytest.raises(ValueError, match="单声道"):
        voice_task.recognize_wav(pcm_wav(channels=2), tmp_path / "unused-model")


def test_missing_room_does_not_publish(tmp_path, capsys):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(pcm_wav())
    results = tmp_path / "runs"
    with patch.object(voice_task, "recognize_wav", return_value=("有 几把 椅子", 0.1)):
        with patch.object(voice_task, "publish_task") as publish:
            assert voice_task.main(["--wav", str(audio), "--results-dir", str(results)]) == 1
            publish.assert_not_called()
    assert json.loads(capsys.readouterr().out)["error"] == "missing_room"
    assert not results.exists()


def test_keyword_mode_passes_configured_names_and_rejects_disabled_objects(tmp_path, capsys):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(pcm_wav())
    with patch.object(voice_task, "recognize_wav", return_value=("厨房 [unk] 杯子", 0.1)) as recognize:
        with patch.object(voice_task, "publish_task") as publish:
            assert voice_task.main(["--wav", str(audio), "--keyword-grammar"]) == 1
            publish.assert_not_called()
    keywords = recognize.call_args.kwargs["keywords"]
    assert {"客厅", "厨房", "卧室", "椅子", "凳子", "杯子"} <= keywords
    assert "kitchen" not in keywords
    assert json.loads(capsys.readouterr().out)["error"] == "object_disabled"


def test_synthetic_audio_evidence_exists_before_publish(tmp_path, capsys):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(pcm_wav())
    results = tmp_path / "runs"

    def verify_before_publish(payload, topic, *, node_name):
        task = json.loads(payload)
        assert (topic, node_name) == ("/task4/task", "task4_voice_task")
        assert (task["room"], task["object_class"], task["source"]) == ("kitchen", "chair", "voice")
        evidence = results / task["task_id"]
        assert (evidence / "voice.wav").read_bytes() == audio.read_bytes()
        info = json.loads((evidence / "voice.json").read_text())
        assert info["task_id"] == task["task_id"]
        assert info["input"] == "synthetic_wav"
        assert info["audio_sha256"] == hashlib.sha256(audio.read_bytes()).hexdigest()

    with patch.object(voice_task, "recognize_wav", return_value=("去 厨房 数 一下 椅子", 0.1)):
        with patch.object(voice_task, "publish_task", side_effect=verify_before_publish) as publish:
            assert voice_task.main(["--wav", str(audio), "--synthetic", "--results-dir", str(results)]) == 0
            publish.assert_called_once()
    assert json.loads(capsys.readouterr().out)["voice_input"] == "synthetic_wav"
