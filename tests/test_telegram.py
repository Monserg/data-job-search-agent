"""Telegram: невідправлені картки повертаються, причина помилки читабельна, check_connection."""
import pytest

import telegram_client


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self.ok = status < 400
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def _fake_post(replies):
    """replies: функція(json_payload) -> _Resp. Записує всі payload'и."""
    calls = []

    def post(url, json=None, timeout=None):
        calls.append((url, json))
        return replies(url, json)

    return post, calls


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(telegram_client.time, "sleep", lambda *_: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", " -1001 \n")


PROFILE = {"name": "AI Junior", "hashtag": "#AI"}
JOB_A = {"title": "Junior AI Engineer", "company": "Acme", "url": "https://a/1", "source": "Djinni"}
JOB_B = {"title": "AI Developer", "company": "Beta", "url": "https://b/2", "source": "DOU"}


def test_all_sent(monkeypatch):
    post, calls = _fake_post(lambda u, j: _Resp(200, {"ok": True}))
    monkeypatch.setattr(telegram_client.requests, "post", post)
    failed, delivered = telegram_client.send_report([(PROFILE, [JOB_A, JOB_B])])
    assert failed == [] and delivered == 3  # заголовок + 2 картки
    assert all(c[1]["chat_id"] == "-1001" for c in calls)  # chat_id обрізано


def test_failed_cards_are_returned_not_lost(monkeypatch):
    def replies(url, j):
        if "b/2" in j["text"]:
            return _Resp(400, {"ok": False, "description": "Bad Request: chat not found"})
        return _Resp(200, {"ok": True})
    post, _ = _fake_post(replies)
    monkeypatch.setattr(telegram_client.requests, "post", post)
    failed, delivered = telegram_client.send_report([(PROFILE, [JOB_A, JOB_B])])
    assert failed == [JOB_B] and delivered == 2


def test_nothing_delivered_when_chat_is_wrong(monkeypatch, caplog):
    post, _ = _fake_post(lambda u, j: _Resp(403, {"ok": False,
                                                  "description": "Forbidden: bot is not a member of the channel chat"}))
    monkeypatch.setattr(telegram_client.requests, "post", post)
    failed, delivered = telegram_client.send_report([(PROFILE, [JOB_A])])
    assert failed == [JOB_A] and delivered == 0
    assert "bot is not a member of the channel chat" in caplog.text


def test_empty_report_sends_nothing_new_message(monkeypatch):
    post, calls = _fake_post(lambda u, j: _Resp(200, {"ok": True}))
    monkeypatch.setattr(telegram_client.requests, "post", post)
    failed, delivered = telegram_client.send_report([(PROFILE, [])])
    assert failed == [] and delivered == 1 and "нових вакансій" in calls[0][1]["text"]


def test_check_connection_reports_missing_admin_rights(monkeypatch, caplog):
    def replies(url, j):
        if url.endswith("getMe"):
            return _Resp(200, {"ok": True, "result": {"username": "bot", "id": 1}})
        if url.endswith("getChat"):
            return _Resp(200, {"ok": True, "result": {"type": "channel", "title": "Jobs", "id": -1001}})
        return _Resp(400, {"ok": False, "description": "Bad Request: need administrator rights in the channel chat"})
    post, _ = _fake_post(replies)
    monkeypatch.setattr(telegram_client.requests, "post", post)
    assert telegram_client.check_connection("t", "-1001") is False
    assert "need administrator rights" in caplog.text


def test_check_connection_ok(monkeypatch):
    post, _ = _fake_post(lambda u, j: _Resp(200, {"ok": True, "result": {"username": "bot", "id": 1, "type": "channel"}}))
    monkeypatch.setattr(telegram_client.requests, "post", post)
    assert telegram_client.check_connection("t", "-1001") is True
