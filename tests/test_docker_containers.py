import http


async def test_ping_endpoint(app_client):
    resp = await app_client.get('/ping')

    assert resp.status == http.HTTPStatus.OK

    data = await resp.text()
    assert data == "All OK"


