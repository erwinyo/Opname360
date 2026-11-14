from fastapi.testclient import TestClient

URL = "/api/v1/items/"


def test_create_and_read_item(client: TestClient) -> None:
    response = client.post(URL, json={"name": "Widget", "quantity": 3})
    assert response.status_code == 201
    created = response.json()
    assert created == {"id": 1, "name": "Widget", "description": None, "quantity": 3}

    assert client.get(f"{URL}{created['id']}").json() == created
    assert client.get(URL).json() == [created]


def test_update_item_only_changes_sent_fields(client: TestClient) -> None:
    item_id = client.post(URL, json={"name": "Widget", "quantity": 3}).json()["id"]

    response = client.patch(f"{URL}{item_id}", json={"quantity": 10})

    assert response.status_code == 200
    assert response.json()["name"] == "Widget"
    assert response.json()["quantity"] == 10


def test_delete_item(client: TestClient) -> None:
    item_id = client.post(URL, json={"name": "Widget"}).json()["id"]

    assert client.delete(f"{URL}{item_id}").status_code == 204
    assert client.get(f"{URL}{item_id}").status_code == 404


def test_missing_item_returns_404(client: TestClient) -> None:
    assert client.get(f"{URL}999").status_code == 404


def test_negative_quantity_is_rejected(client: TestClient) -> None:
    assert client.post(URL, json={"name": "Widget", "quantity": -1}).status_code == 422
