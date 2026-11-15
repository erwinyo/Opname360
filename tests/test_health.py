from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    response = client.get('/api/v1/health/')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_unknown_api_path_is_a_json_404_not_the_frontend(
    client: TestClient,
) -> None:
    response = client.get('/api/v1/no-such-thing')

    assert response.status_code == 404
    assert response.headers['content-type'] == 'application/json'
