"""Explicit local launch; external transport factory is trusted operator code."""
import argparse
import importlib
from pathlib import Path
from prism2api.config import Settings
from prism2api.provider.adapter import PrismAdapter
from prism2api.transport.base import BaseTransport
from prism2api.client import SDKClient


def main():
    parser=argparse.ArgumentParser(prog='prism2api')
    parser.add_argument('command',choices=['serve','smoke'])
    parser.add_argument('--home',type=Path,default=None)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--mock',action='store_true')
    group.add_argument('--transport-factory',help='Trusted local module:factory(settings) returning BaseTransport')
    parser.add_argument('--host',choices=['127.0.0.1','::1'],default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not 1<=args.port<=65535:
        parser.error('port must be between 1 and 65535')
    settings=Settings(**({'home_dir':args.home} if args.home else {}),transport_mode='mock' if args.mock else 'unconfigured')
    adapter=None
    if args.transport_factory:
        module,sep,name=args.transport_factory.partition(':')
        if not sep or not module or not name:
            parser.error('factory must be module:callable')
        transport=getattr(importlib.import_module(module),name)(settings)
        if not isinstance(transport,BaseTransport):
            parser.error('factory must return BaseTransport')
        adapter=PrismAdapter(transport)
    if args.command=='smoke':
        if not args.mock:
            parser.error('smoke is offline-only; use --mock')
        with SDKClient(settings=settings) as client:
            result=client.execute_and_wait('synthetic offline smoke',idempotency_key='offline-smoke-v1')
            print(result.model_dump_json(indent=2))
    else:
        import uvicorn
        from prism2api.api.app import create_app
        app=create_app(settings,adapter=adapter)
        print('Mode:',app.state.supervisor.adapter.transport.kind)
        print('Local key path:',settings.credentials_dir/'gateway.key','(or PRISM2API_KEY override; value is not printed)')
        try:
            uvicorn.run(app,host=args.host,port=args.port,workers=1,access_log=False,ws='none')
        finally:
            app.state.close()

if __name__=='__main__':
    main()
