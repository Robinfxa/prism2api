import asyncio
import json
import httpx
import pytest
from prism2api.direct.bootstrap import import_curl,START_PATH
from prism2api.direct.engine import DirectEngine
from prism2api.direct.server import create_app
from .helpers import curl,Upstream

VALID={'model':'prism-default','messages':[{'role':'user','content':'TEST EXACT'}]}


def scenario(tmp_path,body=None,*,authenticated=True,headers=None,method='POST',path='/v1/chat/completions'):
    async def run():
        import_curl(curl(),tmp_path);up=Upstream();e=DirectEngine(tmp_path,http_client=up.client())
        app=create_app(e);h={'Authorization':'Bearer '+e.key} if authenticated else {}
        h.update(headers or {})
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:8765',headers=h) as c:
                r=await c.request(method,path,json=body)
                return r,up.requests
        finally:await e.close()
    return asyncio.run(run())


def test_real_api_path_to_fake_upstream(tmp_path):
    r,requests=scenario(tmp_path,VALID)
    assert r.status_code==200 and r.json()['choices'][0]['message']['content']=='TEST EXACT'
    assert r.json()['usage'] is None and r.headers['x-prism2api-context']=='fixed-shared'
    assert sum(x.url.path==START_PATH for x in requests)==1

@pytest.mark.parametrize('body',[
    {**VALID,'model':'unknown'}, {**VALID,'stream':True}, {**VALID,'stream':0}, {**VALID,'n':True},
    {**VALID,'n':2}, {**VALID,'tools':[]},{**VALID,'temperature':.2},{**VALID,'max_tokens':10},
    {**VALID,'messages':[]}, {**VALID,'messages':VALID['messages']*2},
    {**VALID,'messages':[{'role':'system','content':'x'}]},
    {**VALID,'messages':[{'role':'user','content':'   '}]},
    {**VALID,'messages':[{'role':'user','content':'x','unknown':'y'}]},
    {**VALID,'messages':[{'role':'user','content':123}]},
])
def test_unsupported_input_sends_zero_requests(tmp_path,body):
    r,requests=scenario(tmp_path,body)
    assert r.status_code==400 and requests==[]


def test_authentication_required(tmp_path):
    r,requests=scenario(tmp_path,VALID,authenticated=False)
    assert r.status_code==401 and not requests

@pytest.mark.parametrize('headers',[{'Host':'evil.example'},{'Origin':'https://evil.example'}])
def test_host_and_origin_guard(tmp_path,headers):
    r,requests=scenario(tmp_path,VALID,headers=headers)
    assert r.status_code in (400,403) and not requests


def test_health_is_only_configuration_not_fake_live_readiness(tmp_path):
    r,_=scenario(tmp_path,method='GET',path='/healthz',authenticated=False)
    assert r.status_code==200
    b=r.json();assert b['status']=='configured' and b['upstream_generation_verified_this_startup'] is False
    assert 'project' not in r.text and 'conversation' not in r.text and 'cookie' not in r.text


def test_models_only_local_alias(tmp_path):
    r,_=scenario(tmp_path,method='GET',path='/v1/models')
    assert r.json()['data'][0]['id']=='prism-default'
