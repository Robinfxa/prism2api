import asyncio
from copy import deepcopy
import json
import httpx
import pytest
from prism2api.direct.bootstrap import import_curl, START_PATH, STATUS_PATH, HEARTBEAT_PATH
from prism2api.direct.engine import DirectEngine
from prism2api.direct.errors import DirectError
from .helpers import curl,payload,success,pending,Upstream


def test_complete_http_cycle_and_rolling_turn_state(tmp_path):
    async def run():
        original=payload(True);import_curl(curl(original),tmp_path)
        server=Upstream(statuses=[pending(2),success('EXACT')])
        e=DirectEngine(tmp_path,http_client=server.client(),poll_interval=.001)
        try:
            result=await e.generate('EXACT')
            assert result['text']=='EXACT' and result['usage'] is None and result['provider_model_id_confirmed'] is None
            assert [r.url.path for r in server.requests]==[HEARTBEAT_PATH,START_PATH,STATUS_PATH,STATUS_PATH]
            start=json.loads(server.requests[1].content)
            assert start['metadata']==original['metadata']
            assert start['input'][0]==original['input'][0]
            assert start['input'][1]['content'][0]['text']=='EXACT'
            assert server.requests[1].headers['user-agent']=='FixtureUA/1.0'
            assert server.requests[0].headers['x-crixet-sandbox-token']=='fixture-sandbox-not-a-real-token'
            assert json.loads(server.requests[2].content)['turn_state']['cursor']==1
            assert json.loads(server.requests[3].content)['turn_state']['cursor']==2
            row=e.journal.get(result['run_id'])
            assert row['start_count']==1 and row['status_count']==2 and row['state']=='succeeded'
        finally:await e.close()
    asyncio.run(run())

@pytest.mark.parametrize('text',['','  leading and trailing \n','你好🌍'])
def test_text_exactly_preserved(tmp_path,text):
    async def run():
        import_curl(curl(),tmp_path);s=Upstream(start=success(text));e=DirectEngine(tmp_path,http_client=s.client())
        try:
            assert (await e.generate('prompt'))['text']==text
            assert s.count(STATUS_PATH)==0
        finally:await e.close()
    asyncio.run(run())


def test_inline_failure_no_turn_state_is_failure_not_success(tmp_path):
    async def run():
        import_curl(curl(),tmp_path)
        wire={'status':'completed','request_id':'fixture-request-1','response':{'status':'error','payload':{'httpStatus':401,'message':'DO_NOT_ECHO_SECRET'}}}
        s=Upstream(start=wire);e=DirectEngine(tmp_path,http_client=s.client())
        try:
            with pytest.raises(DirectError) as exc:await e.generate('test')
            assert exc.value.code=='sandbox_unauthorized'
            assert 'DO_NOT_ECHO_SECRET' not in str(exc.value)
            assert e.journal.get(exc.value.run_id)['state']=='failed'
            assert e.journal.pending() is None and s.count(START_PATH)==1
        finally:await e.close()
    asyncio.run(run())

@pytest.mark.parametrize('mutation',['no_request','bad_request','bad_conversation','bad_project','bad_job','missing_output','no_text','text_null','unknown_status','terminal_conflict'])
def test_status_conflicts_never_become_answer(tmp_path,mutation):
    async def run():
        import_curl(curl(),tmp_path);wire=success('should not return')
        if mutation=='no_request':wire.pop('request_id')
        elif mutation=='bad_request':wire['request_id']='wrong'
        elif mutation=='bad_conversation':wire['response']['payload']['conversationId']='wrong'
        elif mutation=='bad_project':wire['project_id']='wrong'
        elif mutation=='bad_job':wire['codex_async_job_id']='wrong'
        elif mutation=='missing_output':wire['response']['payload'].pop('output')
        elif mutation=='no_text':wire['response']['payload']['output']=[]
        elif mutation=='text_null':wire['response']['payload']['output'][0]['content'][0]['text']=None
        elif mutation=='unknown_status':wire['status']='what_is_this'
        elif mutation=='terminal_conflict':wire['status']='failed'
        s=Upstream(statuses=[wire]);e=DirectEngine(tmp_path,http_client=s.client())
        try:
            with pytest.raises(DirectError) as exc:await e.generate('prompt')
            assert e.journal.get(exc.value.run_id)['state']=='uncertain'
            with pytest.raises(DirectError,match='prior task'):await e.generate('different')
            assert s.count(START_PATH)==1
        finally:await e.close()
    asyncio.run(run())


def test_start_timeout_no_retry_and_restart_blocks(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);s=Upstream(start=httpx.ReadTimeout('DO_NOT_ECHO'));e=DirectEngine(tmp_path,http_client=s.client())
        with pytest.raises(DirectError) as exc:await e.generate('hello')
        rid=exc.value.run_id
        assert e.journal.get(rid)['state']=='uncertain' and s.count(START_PATH)==1
        await e.close()
        s2=Upstream();e2=DirectEngine(tmp_path,http_client=s2.client())
        try:
            with pytest.raises(DirectError):await e2.generate('again')
            with pytest.raises(DirectError,match='No usable remote receipt'):await e2.reconcile(rid)
            assert len(s2.requests)==0
        finally:await e2.close()
    asyncio.run(run())


def test_status_timeout_then_only_read_reconcile(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);s=Upstream(statuses=[httpx.ReadTimeout('secret')]);e=DirectEngine(tmp_path,http_client=s.client())
        with pytest.raises(DirectError) as exc:await e.generate('RESULT')
        rid=exc.value.run_id;await e.close()
        s2=Upstream(statuses=[success('RESULT')]);e2=DirectEngine(tmp_path,http_client=s2.client())
        try:
            result=await e2.reconcile(rid)
            assert result['text']=='RESULT'
            assert s2.count(START_PATH)==0 and s2.count(STATUS_PATH)==1 and s2.count(HEARTBEAT_PATH)==0
        finally:await e2.close()
    asyncio.run(run())


def test_changed_import_does_not_reconcile_wrong_chat(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);s=Upstream(statuses=[httpx.ReadTimeout('oops')]);e=DirectEngine(tmp_path,http_client=s.client())
        with pytest.raises(DirectError) as exc:await e.generate('X')
        rid=exc.value.run_id;await e.close()
        b=payload();b['conversationId']='fixture-chat-B';b['metadata']['codex_listen_snapshot']['conversation_id']='fixture-chat-B'
        import_curl(curl(b),tmp_path);s2=Upstream();e=DirectEngine(tmp_path,http_client=s2.client())
        try:
            with pytest.raises(DirectError,match='different user'):await e.reconcile(rid)
            assert not s2.requests
        finally:await e.close()
    asyncio.run(run())


def test_opaque_turn_state_preserved_as_string(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);p=pending();p['turn_state']='opaque-fixture-state'
        s=Upstream(start=p);e=DirectEngine(tmp_path,http_client=s.client())
        try:
            await e.generate('hi')
            assert json.loads(s.requests[-1].content)['turn_state']=='opaque-fixture-state'
        finally:await e.close()
    asyncio.run(run())


def test_heartbeat_failure_does_not_submit(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);s=Upstream(heartbeat_status=401);e=DirectEngine(tmp_path,http_client=s.client())
        try:
            with pytest.raises(DirectError):await e.generate('hello')
            assert s.count(START_PATH)==0 and e.journal.pending() is None
        finally:await e.close()
    asyncio.run(run())


def test_idempotency_and_conflict(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);s=Upstream();e=DirectEngine(tmp_path,http_client=s.client())
        try:
            first=await e.generate('A',idempotency_key='key1')
            second=await e.generate('A',idempotency_key='key1')
            assert first['run_id']==second['run_id'] and second['cached']
            with pytest.raises(DirectError) as exc:await e.generate('B',idempotency_key='key1')
            assert exc.value.code=='idempotency_conflict' and s.count(START_PATH)==1
        finally:await e.close()
    asyncio.run(run())


def test_deadline_covers_hanging_submit_and_second_request_is_busy(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);entered=asyncio.Event();count=0
        async def handler(req):
            nonlocal count
            if req.url.path==HEARTBEAT_PATH:return httpx.Response(200,json={})
            count+=1;entered.set();await asyncio.sleep(10)
            return httpx.Response(200,json=success())
        e=DirectEngine(tmp_path,http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),timeout=.05)
        task=asyncio.create_task(e.generate('A'));await entered.wait()
        try:
            with pytest.raises(DirectError) as exc:await e.generate('B')
            assert exc.value.code=='busy'
            with pytest.raises(DirectError) as exc:await task
            assert exc.value.status==504 and e.journal.pending()['state']=='uncertain' and count==1
        finally:await e.close()
    asyncio.run(run())


def test_second_writer_and_import_are_blocked(tmp_path):
    async def run():
        import_curl(curl(),tmp_path);e=DirectEngine(tmp_path,http_client=Upstream().client())
        try:
            with pytest.raises(DirectError,match='Another'):DirectEngine(tmp_path)
            with pytest.raises(DirectError,match='Another'):import_curl(curl(),tmp_path)
        finally:await e.close()
    asyncio.run(run())
