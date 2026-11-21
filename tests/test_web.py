import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src" / "ledgerforge" / "web.py"


@pytest.fixture
def app():
    test = AppTest.from_file(APP, default_timeout=20).run()
    assert not test.exception
    yield test
    if "audit" in test.session_state:
        test.session_state["audit"].env.close()


def metric(app, label):
    return next(item.value for item in app.metric if item.label == label)


def table_html(app):
    return app.get("html")[0].value


def test_inspection_counts_only_new_pages_and_explicit_lookups(app):
    assert metric(app, "Steps remaining") == "99"
    app.selectbox(key="evidence_table").select("ledger").run()
    first_page = table_html(app)
    assert first_page.count("<tr>") == 51
    record_id = app.selectbox(key="record_id").options[0]
    assert metric(app, "Steps remaining") == "98"

    app.selectbox(key="record_id").select(record_id).run()
    app.button(key="open_record").click().run()
    assert any(json.loads(view.value).get("row_id") == record_id for view in app.json)
    assert metric(app, "Steps remaining") == "97"

    app.button(key="next_page").click().run()
    assert table_html(app) != first_page
    assert metric(app, "Steps remaining") == "96"
    app.button(key="previous_page").click().run()
    assert table_html(app) == first_page
    assert metric(app, "Steps remaining") == "96"


def test_invalid_draft_can_be_corrected_and_scored(app):
    app.selectbox(key="scenario").select("Clean books")
    app.button(key="load_episode").click().run()
    app.button(key="add_finding").click().run()
    assert len(app.error) == 1
    assert metric(app, "Steps remaining") == "99"

    app.text_input(key="affected_ids").set_value("INV-DEMO")
    app.text_input(key="amount").set_value("1")
    app.button(key="add_finding").click().run()
    assert not app.error
    app.button(key="submit_audit").click().run()
    assert not app.exception
    assert metric(app, "F1") == "0.000"
    assert metric(app, "False positives") == "1"


def test_score_audit_validates_and_includes_the_open_draft(app):
    app.selectbox(key="scenario").select("Clean books")
    app.button(key="load_episode").click().run()
    app.text_input(key="affected_ids").set_value("INV-DEMO")
    app.button(key="submit_audit").click().run()
    assert app.error
    assert app.text_input(key="affected_ids").value == "INV-DEMO"
    assert metric(app, "Steps remaining") == "99"

    app.text_input(key="amount").set_value("1")
    app.button(key="submit_audit").click().run()
    assert not app.error
    assert metric(app, "False positives") == "1"


def test_clean_submission_and_new_episode_reset_the_workspace(app):
    app.selectbox(key="scenario").select("Clean books")
    app.button(key="load_episode").click().run()
    app.button(key="submit_audit").click().run()
    assert metric(app, "F1") == "1.000"
    assert metric(app, "Reward") == "0.998"
    assert metric(app, "Steps remaining") == "98"

    app.button(key="load_episode").click().run()
    assert not app.exception
    assert "F1" not in [item.label for item in app.metric]
    assert metric(app, "Steps remaining") == "99"


def test_final_inspection_displays_truncated_score(app):
    app.session_state["audit"].env.steps = 99
    app.selectbox(key="evidence_table").select("ledger").run()
    assert not app.exception
    assert metric(app, "Steps remaining") == "0"
    assert "step limit" in app.warning[0].value
    assert metric(app, "F1") == "0.000"


def test_russian_keeps_evidence_filter_and_queued_findings(app):
    app.selectbox(key="evidence_table").select("ledger").run()
    record_id = app.selectbox(key="record_id").options[0]
    app.text_input(key="evidence_filter").set_value(record_id).run()
    assert table_html(app).count("<tr>") == 2
    app.text_input(key="affected_ids").set_value("INV-DEMO")
    app.text_input(key="amount").set_value("1")
    app.button(key="add_finding").click().run()

    app.selectbox(key="language").select("ru").run()
    assert not app.exception
    assert app.selectbox(key="evidence_table_ru").value == "ledger"
    assert "Главная книга" in app.selectbox(key="evidence_table_ru").options
    assert app.button(key="submit_audit").label == "Оценить аудит"
    assert "Счёт" in table_html(app)
    assert table_html(app).count("<tr>") == 2
    assert metric(app, "Осталось шагов") == "98"
    assert any("1 из 30" in caption.value for caption in app.caption)
    app.button(key="submit_audit").click().run()
    assert metric(app, "Ложные срабатывания") == "1"

    app.selectbox(key="language").select("en").run()
    assert app.selectbox(key="evidence_table").value == "ledger"
    assert metric(app, "False positives") == "1"
