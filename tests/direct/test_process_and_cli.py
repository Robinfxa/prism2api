import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx
import pytest
from prism2api.direct.bootstrap import import_curl,START_PATH,STATUS_PATH
from prism2api.direct.cli import main
from prism2api.direct.engine import DirectEngine
from prism2api.direct.errors import DirectError
from .helpers import curl,Upstream,success

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
HELPER=Path(__file__).with_name('subprocess_helper.py')

def environment():
    e=dict(os.environ)
    e['PYTHONPATH']=str(REPO/'src')+os.pathsep+str(ROOT)
    return e


def test_cli_stdin_import_does_not_print_secrets(tmp_path,capsys,monkeypatch):
    from io import StringIO
    monkeypatch.setattr(sys,'stdin',StringIO(curl()))
    assert main(['import-curl','--home',str(tmp_path)])==0
    out=capsys.readouterr().out
    assert 'fixture-session' not in out and 'fixture-sandbox' not in out and 'fixture-project' not in out
    assert json.loads(out)['status']=='imported'
    assert main(['doctor-http','--home',str(tmp_path),'--offline'])==0
    assert json.loads(capsys.readouterr().out)['upstream']=='not_contacted'


def test_cli_rejects_unsafe_bind_without_network():
    cp=subprocess.run([sys.executable,'-m','prism2api.direct','serve-http','--host','0.0.0.0'],capture_output=True,text=True,env=environment(),timeout=5)
    assert cp.returncode!=0 and 'invalid choice' in cp.stderr


def test_actual_process_crash_saved_receipt_and_no_resubmit(tmp_path):
    import_curl(curl(),tmp_path)
    p=subprocess.run([sys.executable,str(HELPER),'crash',str(tmp_path)],env=environment(),capture_output=True,text=True,timeout=10)
    assert p.returncode==23, p.stderr
    async def recover():
        u=Upstream(statuses=[success('CRASH_FIXTURE')]);e=DirectEngine(tmp_path,http_client=u.client())
        try:
            row=e.journal.pending();assert row['state']=='uncertain' and row['start_count']==1 and row['status_count']==0
            assert row['receipt_json']
            with pytest.raises(DirectError):await e.generate('do not send')
            result=await e.reconcile(row['run_id'])
            assert result['text']=='CRASH_FIXTURE'
            assert u.count(START_PATH)==0 and u.count(STATUS_PATH)==1
        finally:await e.close()
    asyncio.run(recover())

@pytest.mark.loopback
def test_real_loopback_api_ten_requests_with_fake_prism(tmp_path):
    # Real TCP/uvicorn/client path; ONLY upstream is a named deterministic fake.
    import_curl(curl(),tmp_path)
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    p=subprocess.Popen([sys.executable,str(HELPER),'serve',str(tmp_path),str(port)],env=environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(trust_env=False,timeout=3) as c:
            ready=False
            for _ in range(60):
                try:
                    r=c.get(f'http://127.0.0.1:{port}/healthz')
                    if r.status_code==200:ready=True;break
                except httpx.HTTPError:pass
                time.sleep(.05)
            assert ready
            key=(tmp_path/'gateway.key').read_text()
            for i in range(10):
                prompt=f'LOOPBACK_FIXTURE_{i:03d}'
                r=c.post(f'http://127.0.0.1:{port}/v1/chat/completions',headers={'Authorization':'Bearer '+key,'Idempotency-Key':f'fixture-{i}'},json={'model':'prism-default','messages':[{'role':'user','content':prompt}]})
                assert r.status_code==200
                assert r.json()['choices'][0]['message']['content']==prompt
                state=c.get(f'http://127.0.0.1:{port}/v1/runs/'+r.headers['x-prism2api-run'],headers={'Authorization':'Bearer '+key}).json()
                assert state['start_count']==1 and state['status_count']==1
                assert state['heartbeat_count']==1 and state['state']=='succeeded'
    finally:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
