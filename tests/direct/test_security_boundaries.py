import asyncio
import json
import httpx
import pytest
from prism2api.direct.bootstrap import import_curl
from prism2api.direct.engine import DirectEngine
from prism2api.direct.errors import DirectError
from prism2api.direct.server import create_app
from .helpers import curl,Upstream


def test_runtime_cannot_be_written_inside_git_checkout(tmp_path):
    (tmp_path/'.git').mkdir()
    with pytest.raises(DirectError,match='outside a Git checkout'):
        import_curl(curl(),tmp_path/'runtime')
    assert not (tmp_path/'runtime'/'bootstrap.json').exists()


def test_secret_server_message_never_reaches_local_client(tmp_path):
    async def run():
        import_curl(curl(),tmp_path)
        wire={'status':'completed','request_id':'fixture-request-1','response':{'status':'error','payload':{'message':'PRIVATE_SENTINEL_DO_NOT_RETURN','httpStatus':401}}}
        u=Upstream(start=wire);e=DirectEngine(tmp_path,http_client=u.client())
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(e)),base_url='http://127.0.0.1',headers={'Authorization':'Bearer '+e.key}) as c:
                r=await c.post('/v1/chat/completions',json={'model':'prism-default','messages':[{'role':'user','content':'test'}]})
                assert r.status_code==502
                assert r.json()['error']['code']=='sandbox_unauthorized'
                assert 'PRIVATE_SENTINEL' not in r.text
                assert 'fixture-request' not in r.text
        finally:await e.close()
    asyncio.run(run())


def test_credential_key_file_requires_private_permissions(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);(tmp_path/'gateway.key').write_text('fake-local-key-not-a-real-key-value')
        (tmp_path/'gateway.key').chmod(0o644)
        with pytest.raises(DirectError):DirectEngine(tmp_path)
        # Constructor failure has released process ownership.
        (tmp_path/'gateway.key').chmod(0o600)
        u=Upstream();e=DirectEngine(tmp_path,http_client=u.client())
        await e.close()
    asyncio.run(run())
