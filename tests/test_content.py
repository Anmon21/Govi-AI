from app.db import get_connection

INTERNAL_KEY_HEADER = {"X-Internal-Key": "test-internal-secret"}


def _seed_page(db_path, tenant_id, page_fb_id, page_name="Test Page", is_active=1) -> int:
    """Insert a page row for tenant_id; return lastrowid."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO pages (tenant_id, page_fb_id, page_name, is_active) VALUES (?, ?, ?, ?)",
            (tenant_id, page_fb_id, page_name, is_active),
        )
        page_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return page_id


def _seed_qa_item(db_path, page_id, type, title, body="", category_id=None, enabled=1) -> int:
    """Insert a qa_items row; return lastrowid."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO qa_items (page_id, type, title, body, category_id, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (page_id, type, title, body, category_id, enabled),
        )
        item_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return item_id


def _setup_page(db_client, page_fb_id="fb-content-page") -> int:
    """Seed an active page (owned by the super-admin tenant); return internal pages.id."""
    return _seed_page(db_client.db_path, db_client.super_admin_id, page_fb_id)


def test_list_categories_only(db_client):
    """QA-01: GET /content?type=category lists only category-type items, sorted by id."""
    client = db_client.client
    page_id = _setup_page(db_client)
    shipping_id = _seed_qa_item(db_client.db_path, page_id, "category", "Shipping")
    products_id = _seed_qa_item(db_client.db_path, page_id, "category", "Products")
    _seed_qa_item(db_client.db_path, page_id, "question", "Q1", "Answer A", category_id=shipping_id)

    resp = client.get(
        "/content?type=category&page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    ids = [item["id"] for item in data["items"]]
    assert ids == [str(shipping_id), str(products_id)]
    assert all(item["type"] == "category" for item in data["items"])
    assert all(set(item.keys()) == {"id", "type", "title"} for item in data["items"])


def test_list_questions_filtered_by_category(db_client):
    """QA-02: GET /content?type=question&category=X returns only questions tagged with that category."""
    client = db_client.client
    page_id = _setup_page(db_client)
    shipping_id = _seed_qa_item(db_client.db_path, page_id, "category", "Shipping")
    products_id = _seed_qa_item(db_client.db_path, page_id, "category", "Products")
    ship_1 = _seed_qa_item(db_client.db_path, page_id, "question", "Q ship 1", "ship answer 1", category_id=shipping_id)
    ship_2 = _seed_qa_item(db_client.db_path, page_id, "question", "Q ship 2", "ship answer 2", category_id=shipping_id)
    _seed_qa_item(db_client.db_path, page_id, "question", "Q prod 1", "prod answer 1", category_id=products_id)

    resp = client.get(
        f"/content?type=question&category={shipping_id}&page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 200
    ids = sorted(item["id"] for item in resp.json()["items"])
    assert ids == sorted([str(ship_1), str(ship_2)])


def test_list_unknown_category_returns_empty(db_client):
    """QA-02: Unknown category -> 200 with empty items, not 404."""
    client = db_client.client
    page_id = _setup_page(db_client)
    _seed_qa_item(db_client.db_path, page_id, "category", "Shipping")

    resp = client.get(
        "/content?type=question&category=does-not-exist&page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


def test_list_missing_type_returns_400(db_client):
    """Listing endpoint requires `type` query parameter; empty or missing -> 400 with our detail."""
    client = db_client.client
    _setup_page(db_client)

    # Empty type=
    resp = client.get(
        "/content?type=&page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "type query parameter is required"}

    # No type query string at all — must reach the same handler (route ordering)
    resp = client.get(
        "/content?page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "type query parameter is required"}


def test_get_content_returns_body(db_client):
    """GET /content/{id} returns matching item's {id, type, title, body}."""
    client = db_client.client
    page_id = _setup_page(db_client)
    q_id = _seed_qa_item(db_client.db_path, page_id, "question", "Test Title", "Answer body")

    resp = client.get(
        f"/content/{q_id}?page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(q_id)
    assert data["title"] == "Test Title"
    assert data["body"] == "Answer body"


def test_get_content_not_found_404(db_client):
    """GET /content/{unknown_id} returns 404."""
    client = db_client.client
    _setup_page(db_client)

    resp = client.get(
        "/content/999999?page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 404


def test_content_list_forbidden_without_key(db_client):
    """D-01: GET /content without a valid X-Internal-Key returns 403."""
    client = db_client.client
    _setup_page(db_client)

    # Missing header
    r_missing = client.get("/content?type=category&page_id=fb-content-page")
    assert r_missing.status_code == 403

    # Wrong secret
    r_wrong = client.get(
        "/content?type=category&page_id=fb-content-page",
        headers={"X-Internal-Key": "wrong-secret"},
    )
    assert r_wrong.status_code == 403


def test_content_get_forbidden_without_key(db_client):
    """D-01: GET /content/{id} without a valid X-Internal-Key returns 403."""
    client = db_client.client
    page_id = _setup_page(db_client)
    q_id = _seed_qa_item(db_client.db_path, page_id, "question", "T", "B")

    # Missing header
    r_missing = client.get(f"/content/{q_id}?page_id=fb-content-page")
    assert r_missing.status_code == 403

    # Wrong secret
    r_wrong = client.get(
        f"/content/{q_id}?page_id=fb-content-page",
        headers={"X-Internal-Key": "wrong-secret"},
    )
    assert r_wrong.status_code == 403


def test_unknown_page_id_returns_404(db_client):
    """A page_fb_id with no active page row -> 404, even with a valid X-Internal-Key."""
    client = db_client.client
    _setup_page(db_client)

    resp = client.get(
        "/content?type=category&page_id=does-not-exist",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 404


def test_disabled_qa_item_excluded(db_client):
    """A qa_item with enabled=0 does not appear in the list and 404s on direct GET."""
    client = db_client.client
    page_id = _setup_page(db_client)
    disabled_id = _seed_qa_item(db_client.db_path, page_id, "question", "Hidden", "B", enabled=0)

    resp = client.get(
        "/content?type=question&page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": []}

    resp_get = client.get(
        f"/content/{disabled_id}?page_id=fb-content-page",
        headers=INTERNAL_KEY_HEADER,
    )
    assert resp_get.status_code == 404
