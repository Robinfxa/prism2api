"""Test-only fake upstream. This file is not packaged as production code."""
import asyncio
import os
from pathlib import Path
import sys
import httpx
import uvicorn
from prism2api.direct.engine import DirectEngine
from prism2api.direct.server import create_app
from direct.helpers import Upstream

async def main():
    home=Path(sys.argv[2]);e=DirectEngine(home,http_client=Upstream().client())
    if sys.argv[1]=='crash':
        async def crash_before_status(*args):
            os._exit(23)  # No finally blocks: tests the on-disk receipt boundary.
        e._poll=crash_before_status
        await e.generate('CRASH_FIXTURE',idempotency_key='fixture-crash')
    else:
        config=uvicorn.Config(create_app(e),host='127.0.0.1',port=int(sys.argv[3]),access_log=False,log_level='error',ws='none')
        try:await uvicorn.Server(config).serve()
        finally:
            if not e.closed:await e.close()
asyncio.run(main())
