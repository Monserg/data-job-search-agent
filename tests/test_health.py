"""Здоров'я джерел: лічильник нульових днів і попередження."""
import health


def test_zero_streak_grows_per_day_and_resets_on_result():
    state = {}
    state = health.update(state, {"dou": 0, "djinni": 5}, "2026-09-01")
    state = health.update(state, {"dou": 0, "djinni": 0}, "2026-09-02")
    state = health.update(state, {"dou": 0, "djinni": 0}, "2026-09-02")  # повторний запуск того ж дня
    state = health.update(state, {"dou": 2, "djinni": 0}, "2026-09-03")
    assert state["dou"]["zero_streak"] == 0 and state["dou"]["last_nonzero"] == "2026-09-03"
    assert state["djinni"]["zero_streak"] == 2 and state["djinni"]["last_nonzero"] == "2026-09-01"


def test_warnings_respect_per_source_thresholds():
    state = {
        "dou": {"zero_streak": 3, "last_nonzero": "2026-08-30", "last_run": "2026-09-02"},
        "work_ua_email": {"zero_streak": 3, "last_nonzero": "", "last_run": "2026-09-02"},
        "indeed": {"zero_streak": 99, "last_nonzero": "", "last_run": "2026-09-02"},
    }
    out = health.warnings(state, {"dou": 3, "work_ua_email": 7})
    assert len(out) == 1 and out[0].startswith("Джерело dou дає 0 вакансій уже 3 дн.")


def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(health, "DATA_PATH", str(tmp_path / "h.json"))
    assert health.load_state() == {}
    health.save_state({"x": {"zero_streak": 1}})
    assert health.load_state() == {"x": {"zero_streak": 1}}
