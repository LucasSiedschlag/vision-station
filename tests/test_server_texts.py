"""The server speaks Portuguese and English (TD-30, UI-C3): the catalog is complete, and the API renders each
request's texts in the language it asks for, the station's when it asks for none."""

import json
import re
from types import SimpleNamespace

import pytest
from babel.messages.pofile import read_po

from test_api import env, login  # noqa: F401
from test_station import scene_with_object
from test_verification import inspect_code, make_bundle as job_bundle
from vision_station.core.errors import CATALOG, REASON_CODES, ErrorCode
from vision_station.core.i18n import CATALOG_FILE, Msg, choose, english, join, negotiate, render, render_schema, tr, using
from vision_station.core.i18n_extract import wanted
from vision_station.verification import verify_job

EN = {"Accept-Language": "en"}
FIELD = re.compile(r"\{[^{}]*\}")


# --- the catalog -----------------------------------------------------------------


def test_every_text_the_code_marks_has_an_english_translation_and_none_is_left_over():
    texts, problems = wanted()
    assert problems == []
    with CATALOG_FILE.open("rb") as f:
        have = {m.id: m.string for m in read_po(f) if m.id}
    assert sorted(t for t in texts if not have.get(t)) == [], "run: uv run python -m vision_station.core.i18n_extract --update, then translate"
    assert sorted(set(have) - texts) == [], "texts no longer in the code: run the same command to drop them"


def test_a_translation_keeps_the_fields_of_the_text_it_translates():
    for msgid, text in english().items():
        assert sorted(FIELD.findall(msgid)) == sorted(FIELD.findall(text)), msgid


def test_every_error_code_and_reason_code_reads_in_both_languages():
    for info in CATALOG.values():
        assert render(info.text, "en") != str(info.text) or info.text in english().values()
        assert info.text in english() or str(info.text) in english()
    assert all(text in english() for text in REASON_CODES.values())


# --- rendering -----------------------------------------------------------------------


def test_a_message_reads_as_portuguese_and_carries_what_it_needs_to_be_translated():
    message = tr("Região '{name}' fora da imagem", name="topo")
    assert message == "Região 'topo' fora da imagem" and isinstance(message, Msg)
    assert render(message, "en") == "Region 'topo' outside the image"
    assert render(message, "pt-BR") == "Região 'topo' fora da imagem"


def test_parameters_that_are_messages_are_rendered_too_and_a_list_joins_in_the_language():
    inner = tr("sem imagem da câmera")
    outer = tr("{image}: {what}", image="a.png", what=join([inner, tr("recusado")]))
    assert str(outer) == "a.png: sem imagem da câmera; recusado"
    assert render(outer, "en") == "a.png: no image from the camera; refused"


def test_a_plain_text_is_looked_up_and_left_alone_when_the_catalog_does_not_know_it():
    assert render("Dados inválidos", "en") == "Invalid data"
    assert render("Texto escrito no job", "en") == "Texto escrito no job"  # a job's own text is not ours to translate
    assert render("Dados inválidos", "pt-BR") == "Dados inválidos"


def test_the_language_of_a_request_is_negotiated_from_its_header():
    assert negotiate("en-US,en;q=0.9", "pt-BR") == "en"
    assert negotiate("pt", "en") == "pt-BR" and negotiate("pt-PT, en;q=0.5", "en") == "pt-BR"
    assert negotiate("en;q=0.4, pt-BR;q=0.9", "en") == "pt-BR"
    assert negotiate("fr-FR, de;q=0.5", "en") == "en" and negotiate("*", "pt-BR") == "pt-BR"  # none of ours: the default
    assert negotiate(None, "en") == "en" and negotiate("en;q=0, pt", "en") == "pt-BR"
    assert choose("en", "pt-BR") == "en" and choose("xx", "pt-BR") == "pt-BR" and choose(None, "en") == "en"


def test_a_schema_is_translated_on_a_copy_and_its_validation_is_untouched():
    schema = {"title": "Modo", "type": "string", "properties": {"mode": {"title": "Modo", "x-enum-labels": {"range": "faixa (HSV)"}, "enum": ["range"]}}}
    out = render_schema(schema, "en")
    assert out["properties"]["mode"]["title"] == "Mode" and out["properties"]["mode"]["x-enum-labels"] == {"range": "range (HSV)"}
    assert out["properties"]["mode"]["enum"] == ["range"] and schema["title"] == "Modo"
    with using("en"):
        assert render_schema(schema)["title"] == "Mode"


# --- the API ------------------------------------------------------------------------------


def station_in(env, language):  # noqa: F811
    env.deps.system = SimpleNamespace(config=SimpleNamespace(station=SimpleNamespace(language=language, markings="on_fail", operator_markings=True)))


def test_state_follows_the_language_the_request_asks_for(env):  # noqa: F811
    assert env.client.get("/api/state").json()["message"] == "Aguardando objeto"
    assert env.client.get("/api/state", headers=EN).json()["message"] == "Waiting for a part"
    assert env.client.get("/api/state", headers={"Accept-Language": "pt-BR"}).json()["message"] == "Aguardando objeto"


def test_a_request_without_a_language_gets_the_station_language(env):  # noqa: F811
    station_in(env, "en")
    assert env.client.get("/api/state").json()["message"] == "Waiting for a part"
    assert env.client.get("/api/state", headers={"Accept-Language": "pt-BR"}).json()["message"] == "Aguardando objeto"
    assert env.client.get("/api/state", headers={"Accept-Language": "fr"}).json()["message"] == "Waiting for a part"


def test_an_error_answer_is_in_the_language_of_the_request_with_the_same_code(env):  # noqa: F811
    pt, en = env.client.get("/api/result/last"), env.client.get("/api/result/last", headers=EN)
    assert pt.json() == {"detail": "Ainda não há resultado", "code": "no_result"}
    assert en.json() == {"detail": "There is no result yet", "code": "no_result"}
    assert env.client.get("/api/nada", headers=EN).json()["detail"] == "This API path does not exist"


def test_a_message_with_details_keeps_them_in_the_translation(env):  # noqa: F811
    headers = login(env, "maintainer")
    r = env.client.post("/api/jobs/validate", json={"job": {}, "profile": {}}, headers={**headers, **EN})
    assert r.status_code == 200
    r = env.client.post("/api/camera/apply", json={"nada": 1}, headers={**headers, **EN})
    assert r.json()["detail"] == "Invalid camera settings"


def without_texts(node):
    if isinstance(node, dict):
        return {k: without_texts(v) for k, v in node.items() if k not in ("title", "description", "x-enum-labels")}
    return [without_texts(v) for v in node] if isinstance(node, list) else node


def test_the_parameter_forms_of_the_tools_come_in_the_language_asked_for(env):  # noqa: F811
    headers = login(env, "maintainer")
    pt = env.client.get("/api/tools", headers=headers).json()
    en = env.client.get("/api/tools", headers={**headers, **EN}).json()
    color = lambda body: next(t for t in body["tools"] if t["name"] == "color")  # noqa: E731
    assert color(pt)["description"] == "Mede quanto de uma região tem uma cor."
    assert color(en)["description"] == "Measures how much of a region has a colour."
    assert color(en)["params_schema"]["properties"]["min_fraction"]["title"] == "Minimum fraction of the area"
    assert color(pt)["params_schema"]["properties"]["min_fraction"]["title"] == "Fração mínima da área"
    assert without_texts(color(en)["params_schema"]) == without_texts(color(pt)["params_schema"])  # only the texts change


def test_the_live_socket_speaks_the_language_in_its_url_and_defaults_to_the_stations(env):  # noqa: F811
    with env.client.websocket_connect("/api/live?lang=en") as ws:
        assert ws.receive_json()["message"] == "Waiting for a part"
    with env.client.websocket_connect("/api/live") as ws:
        assert ws.receive_json()["message"] == "Aguardando objeto"
    with env.client.websocket_connect("/api/live", headers=EN) as ws:  # another program can use the header
        assert ws.receive_json()["message"] == "Waiting for a part"
    with env.client.websocket_connect("/api/live?lang=en", headers={"Accept-Language": "pt-BR"}) as ws:  # the page's choice wins
        assert ws.receive_json()["message"] == "Waiting for a part"


def test_each_socket_gets_its_events_in_its_own_language(env):  # noqa: F811
    with env.client.websocket_connect("/api/live?lang=en") as english_ws, env.client.websocket_connect("/api/live") as portuguese_ws:
        english_ws.receive_json(), portuguese_ws.receive_json()
        env.rig.camera.scene = scene_with_object(40)
        env.rig.tick(10)
        seen = {}
        for key, ws in (("en", english_ws), ("pt", portuguese_ws)):
            seen[key] = []
            for _ in range(200):
                message = ws.receive()
                if not message.get("text"):
                    continue  # a camera frame
                body = json.loads(message["text"])
                if body["type"] == "state":
                    seen[key].append(body["message"])
                if body["type"] == "result":
                    break
    assert "Inspecting…" in seen["en"] and "Inspecionando…" in seen["pt"]
    assert "Inspecionando…" not in seen["en"] and "Inspecting…" not in seen["pt"]


def test_an_error_result_reads_in_the_language_of_the_screen_asking(env):  # noqa: F811
    env.rig.tick(2)
    env.rig.controller._finish(env.rig.controller._error(ErrorCode.TOO_DARK), None)
    pt = env.client.get("/api/state").json()["last_result"]["reason"]
    en = env.client.get("/api/state", headers=EN).json()["last_result"]["reason"]
    assert pt == "Imagem escura demais, verificar a iluminação" and en == "Image too dark, check the lighting"


def test_why_a_verification_failed_is_in_the_language_of_the_request_and_the_check_stays_in_portuguese(env):  # noqa: F811
    ref = env.jobs.save(job_bundle())
    bad = job_bundle().__class__(
        job=job_bundle().job.model_copy(update={"job": job_bundle().job.job.model_copy(update={"version": 2, "parent_version": 1})}),
        profile=job_bundle().profile,
        extra={**job_bundle().extra, "tests/expected.yaml": b"cases:\n- {image: tests/images/blank.png, outcome: PASS}\n"},
    )
    broken = env.jobs.save(bad)
    url = f"/api/jobs/{ref.job_id}/versions/{broken.version}/activate"
    pt = env.client.post(url, headers=login(env), json={}).json()["problems"]
    en = env.client.post(url, headers={**login(env), **EN}, json={}).json()["problems"]
    assert pt and len(pt) == len(en) and pt != en
    assert any("resultado" in p and "esperado" in p for p in pt) and any("result" in p and "expected" in p for p in en)
    report = verify_job(bad, inspect=inspect_code)  # the core compares in Portuguese whatever the station speaks (a job's reason_contains)
    assert all(isinstance(c.message, Msg) for c in report.failures()) and any("resultado" in str(c.message) for c in report.failures())


@pytest.mark.parametrize("language,expected", [("en", "Image too dark, check the lighting"), ("pt-BR", "Imagem escura demais, verificar a iluminação")])
def test_a_recorded_error_is_listed_in_the_language_of_the_request(env, language, expected):  # noqa: F811
    env.rig.tick(2)
    env.rig.controller._finish(env.rig.controller._error(ErrorCode.TOO_DARK), None)
    headers = {**login(env), "Accept-Language": language}
    listed = env.client.get("/api/results", headers=headers).json()
    assert any(item["reason"] == expected for item in listed["results"])


def test_a_message_raised_inside_an_exception_is_translated_with_the_text_around_it():
    from vision_station.models import ModelError

    inner = ModelError(tr("saída do modelo vazia ({what})", what=tr("caixas")))
    outer = tr("Ferramenta '{tool}' não pode rodar: {exc}", tool="forma", exc=inner)
    assert str(outer) == "Ferramenta 'forma' não pode rodar: saída do modelo vazia (caixas)"
    assert render(outer, "en") == "Tool 'forma' cannot run: the model output is empty (boxes)"
    assert render(tr("Ferramenta '{tool}' não pode rodar: {exc}", tool="forma", exc=ValueError("plain")), "en") == "Tool 'forma' cannot run: plain"


def test_a_reason_is_recorded_in_the_station_language_and_a_standard_one_reads_in_the_viewers(env):  # noqa: F811
    station_in(env, "en")
    env.recorder._language = lambda: "en"
    env.rig.tick(2)
    env.rig.controller._finish(env.rig.controller._error(ErrorCode.TOO_DARK), None)
    stored = env.results.get(env.recorder.last_record_id)
    assert stored.reason == "Image too dark, check the lighting"  # as recorded, in the language of the station at the time
    for language, expected in (("pt-BR", "Imagem escura demais, verificar a iluminação"), ("en", "Image too dark, check the lighting")):
        listed = env.client.get("/api/results", headers={**login(env), "Accept-Language": language}).json()["results"]
        assert listed[0]["reason"] == expected
