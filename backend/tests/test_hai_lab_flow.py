import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.services.analytics_service import sanitize_csv_cell

client = TestClient(app)


def test_health_endpoint() -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "connected"}


def test_anonymous_researcher_routes_rejected() -> None:
    res = client.get("/api/v1/experiments")
    assert res.status_code == 401


def test_csv_formula_injection_escaping() -> None:
    assert sanitize_csv_cell("=SUM(A1:A5)") == "'=SUM(A1:A5)"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-2+3") == "'-2+3"
    assert sanitize_csv_cell("@evil") == "'@evil"
    assert sanitize_csv_cell(None) == ""
    assert sanitize_csv_cell("normal text") == "normal text"


def test_end_to_end_researcher_and_participant_journey() -> None:
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"researcher_{unique_suffix}@hailab.org"
    password = "StrongPassword123!"

    # 1. Register and login researcher
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test Researcher", "password": password},
    )
    assert reg.status_code == 201

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    r_headers = {"Authorization": f"Bearer {token}"}

    # 2. Create draft experiment with 2 conditions & 1 task each
    exp = client.post(
        "/api/v1/experiments",
        headers=r_headers,
        json={
            "title": f"Trust & Explanation Study {unique_suffix}",
            "description": "Automated integration test study",
            "participant_information": "Read carefully before consenting.",
            "consent_statement": "I agree to participate.",
        },
    )
    assert exp.status_code == 201
    exp_id = exp.json()["id"]

    # Publishing before 2 conditions fails validation
    premature_pub = client.post(f"/api/v1/experiments/{exp_id}/publish", headers=r_headers)
    assert premature_pub.status_code == 422

    cond_a = client.post(
        f"/api/v1/experiments/{exp_id}/conditions",
        headers=r_headers,
        json={
            "name": "Condition A",
            "ai_answer_template": "Answer: Approve request.",
            "condition_order": 1,
        },
    ).json()
    cond_b = client.post(
        f"/api/v1/experiments/{exp_id}/conditions",
        headers=r_headers,
        json={
            "name": "Condition B",
            "ai_answer_template": "Answer: Approve request.",
            "ai_explanation_template": "Explanation: All 4 criteria satisfied.",
            "condition_order": 2,
        },
    ).json()

    questions = [
        {"id": "trust", "label": "Trust", "type": "likert", "min": 1, "max": 7, "required": True}
    ]
    for cid in (cond_a["id"], cond_b["id"]):
        t_res = client.post(
            f"/api/v1/experiments/{exp_id}/tasks",
            headers=r_headers,
            json={
                "condition_id": cid,
                "title": "Decision Task",
                "instructions": "Ask AI and rate trust.",
                "task_order": 1,
                "questions_json": questions,
            },
        )
        assert t_res.status_code == 201

    # 3. Publish immutable version snapshot & generate invitation
    pub = client.post(f"/api/v1/experiments/{exp_id}/publish", headers=r_headers)
    assert pub.status_code == 201
    assert pub.json()["version_number"] == 1

    inv = client.post(
        f"/api/v1/experiments/{exp_id}/invitations",
        headers=r_headers,
        json={"label": "Test Batch", "expires_in_hours": 24},
    ).json()
    raw_invite_token = inv["raw_token"]

    # 4. Participant opens session; consent gate blocks assignment beforehand
    sess = client.post(
        "/api/v1/participant/session", json={"invite_token": raw_invite_token}
    ).json()
    p_headers = {"X-Participant-Token": sess["session_token"]}

    blocked_assign = client.post("/api/v1/participant/assign", headers=p_headers)
    assert blocked_assign.status_code == 403

    # 5. Grant consent & confirm persistent assignment across retries
    consent_res = client.post(
        "/api/v1/participant/consent", headers=p_headers, json={"consented": True}
    )
    assert consent_res.status_code == 200

    assign_1 = client.post("/api/v1/participant/assign", headers=p_headers).json()
    assign_2 = client.post("/api/v1/participant/assign", headers=p_headers).json()
    assert assign_1["condition_id"] == assign_2["condition_id"]
    assigned_task_id = assign_1["condition"]["tasks"][0]["id"]

    # 6. Send chat message & verify deterministic mock AI response
    chat = client.post(
        "/api/v1/participant/messages",
        headers=p_headers,
        json={"task_id": assigned_task_id, "content": "What should I decide?"},
    )
    assert chat.status_code == 201
    assert "Answer: Approve request." in chat.json()["assistant_message"]["content"]

    # 7. Reject out-of-range rating, then submit valid rating & complete
    bad_resp = client.post(
        "/api/v1/participant/responses",
        headers=p_headers,
        json={"task_id": assigned_task_id, "answers": [{"question_id": "trust", "value": 99}]},
    )
    assert bad_resp.status_code == 422

    good_resp = client.post(
        "/api/v1/participant/responses",
        headers=p_headers,
        json={"task_id": assigned_task_id, "answers": [{"question_id": "trust", "value": 6}]},
    )
    assert good_resp.status_code == 201

    comp = client.post("/api/v1/participant/complete", headers=p_headers)
    assert comp.status_code == 200
    assert comp.json()["completed"] is True

    # 8. Researcher inspects analytics & exports CSVs without secrets
    analytics = client.get(f"/api/v1/experiments/{exp_id}/analytics", headers=r_headers).json()
    assert analytics["funnel"]["completed_count"] == 1
    assert len(analytics["rating_summaries"]) == 1
    assert analytics["rating_summaries"][0]["mean"] == 6.0

    for ds in ("participants", "assignments", "responses", "messages", "events", "experiment_summary"):
        csv_res = client.get(
            f"/api/v1/experiments/{exp_id}/export?dataset={ds}", headers=r_headers
        )
        assert csv_res.status_code == 200
        assert "password_hash" not in csv_res.text
        assert "token_hash" not in csv_res.text