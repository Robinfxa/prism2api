"""CLI for manually imported credentials; never opens/scans a browser or shell."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
import uuid
import httpx
from . import __version__
from .bootstrap import Bootstrap, import_curl
from .engine import DirectEngine
from .errors import DirectError
from .secure import MAX_FILE, read_private

COMMANDS={'import-curl','serve-http','probe-http','doctor-http','smoke-http','reconcile-http','run-status','acknowledge-run'}


def output(data): print(json.dumps(data,ensure_ascii=False,indent=2))


def parser():
    p=argparse.ArgumentParser(prog='prism2api',description='Direct HTTP, fixed shared chat, manual cURL bootstrap. No browser automation.')
    p.add_argument('command',choices=sorted(COMMANDS))
    p.add_argument('--home',type=Path,default=Path.home()/'.prism2api'/'direct')
    p.add_argument('--file',type=Path,help='Private UTF-8 cURL file (or prompt file for probe-http).')
    p.add_argument('--prompt',help='Plain user prompt for probe-http; never supply credentials here.')
    p.add_argument('--host',choices=['127.0.0.1','::1'],default='127.0.0.1')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--timeout',type=float,default=180,help='Entire upstream turn deadline, 1–900 seconds.')
    p.add_argument('--count',type=int,default=3,help='Smoke generation count, 1–10; stops on first failure.')
    p.add_argument('--run',help='Local run_... identifier, not a remote Prism identifier.')
    p.add_argument('--remote-stopped',action='store_true',help='Operator confirms the uncertain task is no longer active in Prism UI.')
    p.add_argument('--offline',action='store_true',help='doctor-http only: check bundle format without network I/O.')
    p.add_argument('--idempotency-key')
    return p


async def operate(args):
    engine=DirectEngine(args.home,timeout=args.timeout)
    try:
        if args.command=='doctor-http': output(await engine.doctor())
        elif args.command=='probe-http':
            prompt=args.prompt
            if args.file: prompt=read_private(args.file,MAX_FILE).decode('utf-8')
            if prompt is None: raise DirectError('prompt_missing','Provide --prompt or --file.',400)
            result=await engine.generate(prompt,idempotency_key=args.idempotency_key)
            output({'result':result,'run':engine.journal.public(result['run_id'])})
        elif args.command=='reconcile-http':
            if not args.run: raise DirectError('run_missing','Provide --run.',400)
            output(await engine.reconcile(args.run))
        elif args.command=='run-status':
            if not args.run: raise DirectError('run_missing','Provide --run.',400)
            output(engine.journal.public(args.run))
        elif args.command=='acknowledge-run':
            if not args.run or not args.remote_stopped:
                raise DirectError('confirmation_required','First inspect the original Prism chat. Only after confirming the task has stopped, use --run and --remote-stopped. This does not mark success.',400)
            output(engine.acknowledge(args.run))
        elif args.command=='serve-http':
            import uvicorn
            from .server import create_app
            print(f'prism2api {__version__}: direct HTTP / fixed shared context / loopback only')
            print(f'API: http://{args.host if args.host=="127.0.0.1" else "[::1]"}:{args.port}/v1/chat/completions')
            print('Local API key file:', args.home/'gateway.key', '(value not printed)')
            print('Configured locally; upstream generation is not yet verified.')
            # Do not log untrusted upstream body or HTTPX request metadata.
            server=uvicorn.Server(uvicorn.Config(create_app(engine),host=args.host,port=args.port,
                access_log=False,log_level='warning',ws='none',timeout_graceful_shutdown=int(args.timeout)+5))
            await server.serve()
    finally:
        if not engine.closed: await engine.close()


def smoke(args):
    key=read_private(args.home/'gateway.key',512).decode().strip()
    host='[::1]' if args.host=='::1' else args.host
    url=f'http://{host}:{args.port}'
    rows=[]
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=args.timeout+10,
                      headers={'Authorization':'Bearer '+key}) as client:
        for i in range(args.count):
            marker='PRISM_HTTP_'+uuid.uuid4().hex[:16]
            t=time.monotonic()
            try:
                r=client.post(url+'/v1/chat/completions',json={'model':'prism-default','messages':[{'role':'user','content':'Reply exactly: '+marker}]},headers={'Idempotency-Key':'smoke-'+uuid.uuid4().hex})
                obj=r.json()
                text=obj.get('choices',[{}])[0].get('message',{}).get('content')
                ok=r.status_code==200 and text==marker
                rid=r.headers.get('x-prism2api-run') or obj.get('error',{}).get('run_id')
                row={'index':i+1,'http_status':r.status_code,'exact_match':ok,'run_id':rid,'latency_ms':round((time.monotonic()-t)*1000)}
                if rid:
                    s=client.get(url+'/v1/runs/'+rid)
                    if s.status_code==200:
                        row['counts']={k:s.json().get(k) for k in ('start_count','status_count','heartbeat_count')}
                        ok=ok and row['counts']['start_count']==1
                        row['exact_match']=ok
                rows.append(row)
            except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError):
                rows.append({'index':i+1,'exact_match':False,'error':'local_request_unconfirmed','latency_ms':round((time.monotonic()-t)*1000)})
                ok=False
            if not ok: break  # Never send a ten-request queue after an ambiguous failure.
    result={'mode':'LIVE local API test (requires valid Prism capture)','requested':args.count,
            'attempted':len(rows),'passed':sum(bool(x['exact_match']) for x in rows),'runs':rows,
            'remaining':'not_run' if len(rows)<args.count else None}
    output(result)
    return 0 if result['passed']==args.count else 1


def main(argv=None):
    p=parser();args=p.parse_args(argv)
    if not 1<=args.port<=65535 or not 1<=args.count<=10 or not 1<=args.timeout<=900:
        p.error('Invalid port, count or timeout.')
    args.home=args.home.expanduser().absolute()
    try:
        if args.command=='import-curl':
            if args.file:
                text=read_private(args.file).decode('utf-8')
            elif not sys.stdin.isatty():
                text=sys.stdin.read(MAX_FILE+1)
            else:
                raise DirectError('input_required','Pipe Copy-as-cURL via stdin or use --file with mode 0600. Never paste a secret into shell arguments.',400)
            bundle=import_curl(text,args.home)
            output({'status':'imported','schema_version':1,'import_id':bundle.import_id,
                'fields':{k:'present' for k in ['cookie','user_agent','metadata','codex_listen_snapshot','project','conversation','sandbox_token']},
                'saved_to':str(args.home/'bootstrap.json'),'permissions':'0600','upstream_generation':'not_tested'})
        elif args.command=='doctor-http' and args.offline:
            bundle=Bootstrap.load(args.home/'bootstrap.json')
            output({'bootstrap':'valid_format','import_id':bundle.import_id,'upstream':'not_contacted','generation':'not_tested'})
        elif args.command=='smoke-http': return smoke(args)
        else: asyncio.run(operate(args))
        return 0
    except DirectError as exc:
        output(exc.public());return 1
    except (OSError,UnicodeError,ValueError):
        output({'error':{'code':'local_io_error','message':'Local input/file error. No secret details are printed.'}});return 1
    except KeyboardInterrupt:
        return 130


def entry_point():
    raise SystemExit(main())
