"""Asynchronous pure-HTTP execution. Single chat, single writer, submit once.

Unknown upstream outcomes block further generation. This does not claim provider
idempotency or unattended recovery without valid current credentials.
"""
import asyncio
import json
import time
from pathlib import Path
import httpx
from .bootstrap import Bootstrap, ORIGIN, START_PATH, STATUS_PATH, HEARTBEAT_PATH, strict_json
from .errors import DirectError, invalid
from .journal import Journal
from .secure import ProcessLock, gateway_key, private_dir
from .wire import identity, terminal, protocol, state_object

MAX_PROMPT = 256 * 1024
MAX_RESPONSE = 8 * 1024 * 1024


class DirectEngine:
    def __init__(self, home: Path, *, http_client: httpx.AsyncClient | None = None,
                 timeout: float = 180.0, poll_interval: float = 1.2):
        if not 0 < timeout <= 900 or not 0 < poll_interval <= 30:
            raise invalid('invalid_timeout', 'Timeout or poll interval is outside supported bounds.')
        self.home = private_dir(home)
        self.owner = ProcessLock(self.home)
        self.journal = None
        self.closed = False
        self.successful_runs = 0
        try:
            self.bundle = Bootstrap.load(self.home / 'bootstrap.json')
            self.key = gateway_key(self.home)
            self.journal = Journal(self.home)
            self.http = http_client or httpx.AsyncClient(http1=True, http2=False, trust_env=False,
                follow_redirects=False, timeout=httpx.Timeout(timeout, connect=min(10, timeout)),
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1))
            self.timeout, self.poll_interval = timeout, poll_interval
            self.lock = asyncio.Lock()
        except BaseException:
            if self.journal: self.journal.close()
            self.owner.close()
            raise

    async def _request(self, path, *, payload=None, heartbeat=False):
        headers = self.bundle.request_headers()
        if heartbeat:
            headers['x-crixet-sandbox-token'] = self.bundle.metadata['sandbox_token']
            headers.pop('content-type', None)
        method = 'GET' if heartbeat else 'POST'
        params = {'prism_cache_bust': str(int(time.time()*1000))} if heartbeat else None
        # All URLs are fixed to Prism; imported URLs cannot redirect/exfiltrate cookies.
        async with self.http.stream(method, ORIGIN+path, headers=headers, json=payload,
                                    params=params, follow_redirects=False) as response:
            parts, size = [], 0
            async for piece in response.aiter_bytes():
                size += len(piece)
                if size > MAX_RESPONSE: raise protocol('response_too_large')
                parts.append(piece)
            if response.status_code != 200:
                code = {401:'upstream_unauthorized',403:'upstream_forbidden',429:'upstream_rate_limited'}.get(response.status_code, 'upstream_http_error')
                raise DirectError(code, 'Prism rejected the request or returned an HTTP error. Refresh the captured bundle if appropriate; no automatic retry.')
            if heartbeat: return {}
            try:
                data = strict_json(b''.join(parts).decode('utf-8'))
            except (DirectError, UnicodeError):
                raise protocol('invalid_response_json') from None
            if not isinstance(data, dict): raise protocol()
            return data

    async def doctor(self) -> dict:
        if self.lock.locked(): raise DirectError('busy','A request is active.',409)
        async with self.lock:
            try:
                async with asyncio.timeout(min(30, self.timeout)):
                    await self._request(HEARTBEAT_PATH, heartbeat=True)
            except DirectError: raise
            except (httpx.HTTPError, TimeoutError):
                raise DirectError('heartbeat_unavailable','Sandbox heartbeat could not be confirmed. No generation was submitted.',503) from None
        return {'bootstrap_loaded':True, 'snapshot_present':True, 'heartbeat':'ok',
                'generation':'not_tested', 'browser_required_by_client':False}

    async def _poll(self, rid: str, receipt: dict):
        while True:
            self.journal.count(rid,'status_count')
            data = await self._request(STATUS_PATH, payload={'request_id': receipt['request_id'], 'turn_state': receipt['turn_state']})
            identity(data, receipt)
            # Preserve BOTH value and original JSON type. Never reconstruct/sign turn_state.
            if 'turn_state' in data and data['turn_state'] is not None:
                ts = data['turn_state']
                if not isinstance(ts,(str,dict)) or not ts: raise protocol('turn_state_schema')
                receipt = {**receipt, 'turn_state':ts}
                self.journal.save_receipt(rid, receipt)
            state, value = terminal(data)
            if state != 'running':
                return self._finish(rid, state, value)
            await asyncio.sleep(self.poll_interval)

    def _finish(self, rid, state, value):
        if state == 'succeeded':
            self.journal.update(rid,state=state,text=value,error_code=None)
            self.successful_runs += 1
            return {'run_id':rid, 'text':value, 'model':'prism-default', 'usage':None,
                    'provider_model_id_confirmed':None, 'context_mode':'fixed-shared'}
        self.journal.update(rid,state=state,error_code=value)
        raise DirectError(value or 'upstream_failed', 'Prism returned an explicit unsuccessful outcome. No answer was fabricated.',502,run_id=rid)

    def _previous(self, row):
        if row['state'] == 'succeeded':
            return {'run_id':row['run_id'],'text':row['text'],'model':'prism-default','usage':None,
                    'provider_model_id_confirmed':None,'context_mode':'fixed-shared','cached':True}
        raise DirectError(row['error_code'] or 'previous_outcome', 'This idempotency key already has an unsuccessful or unresolved run; it will not be resubmitted.',409,run_id=row['run_id'])

    async def generate(self, prompt: str, *, idempotency_key: str | None = None):
        if self.closed: raise DirectError('closed','Runtime is closed.',503)
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode('utf-8')) > MAX_PROMPT:
            raise invalid('invalid_prompt','Expected nonempty text of at most 256 KiB.')
        if idempotency_key is not None and (not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=256):
            raise invalid('idempotency_key','Idempotency key must contain 1–256 characters.')
        if self.lock.locked(): raise DirectError('busy','This fixed chat already has a request in progress.',409)
        async with self.lock:
            row, fresh = self.journal.accept(prompt,self.bundle.import_id,self.bundle.scope,idempotency_key)
            if not fresh: return self._previous(row)
            rid, submitted = row['run_id'], False
            try:
                # Includes heartbeat, submit, body reads, polling AND sleep: no unbounded await.
                async with asyncio.timeout(self.timeout):
                    self.journal.count(rid,'heartbeat_count')
                    await self._request(HEARTBEAT_PATH, heartbeat=True)
                    self.journal.update(rid,state='submitting')
                    self.journal.count(rid,'start_count')
                    submitted = True
                    data = await self._request(START_PATH,payload=self.bundle.payload(prompt))
                    req_id = data.get('request_id')
                    if not isinstance(req_id,str) or not req_id: raise protocol('missing_request_id')
                    receipt = {'request_id':req_id,'conversation_id':self.bundle.conversation,
                               'project_id':self.bundle.metadata['projectId'], 'turn_state': data.get('turn_state')}
                    # Store any received receipt BEFORE interpreting terminal/schema details.
                    self.journal.save_receipt(rid,receipt)
                    identity(data,receipt)
                    state, value = terminal(data)
                    if state != 'running': return self._finish(rid,state,value)
                    if not isinstance(receipt['turn_state'],(dict,str)) or not receipt['turn_state']:
                        raise protocol('missing_turn_state')
                    self.journal.update(rid,state='running')
                    return await self._poll(rid,receipt)
            except BaseException as exc:
                current = self.journal.get(rid)
                if current['state'] not in ('succeeded','failed','cancelled'):
                    state = 'uncertain' if submitted else 'failed'
                    code = exc.code if isinstance(exc,DirectError) else 'deadline_exceeded' if isinstance(exc,TimeoutError) else 'transport_interrupted'
                    self.journal.update(rid,state=state,error_code=code)
                if isinstance(exc,asyncio.CancelledError): raise
                if not isinstance(exc,Exception): raise
                if isinstance(exc,DirectError):
                    exc.run_id = rid
                    raise
                raise DirectError('deadline_exceeded' if isinstance(exc,TimeoutError) else 'transport_interrupted',
                    'The request did not reach a confirmed outcome. Inspect the run; do not blindly resubmit.',
                    504 if isinstance(exc,TimeoutError) else 502, run_id=rid) from None

    async def reconcile(self, rid: str):
        if self.lock.locked(): raise DirectError('busy','A request is active.',409)
        async with self.lock:
            row = self.journal.get(rid)
            if row['state'] == 'succeeded': return self._previous(row)
            if row['state'] != 'uncertain': raise DirectError('not_uncertain','Only uncertain runs need reconciliation.',409,run_id=rid)
            if row['scope'] != self.bundle.scope:
                raise DirectError('context_mismatch','Current import belongs to a different user/project/chat. No lookup sent.',409,run_id=rid)
            receipt = json.loads(row['receipt_json']) if row['receipt_json'] else None
            if not receipt or not receipt.get('request_id') or not receipt.get('turn_state'):
                raise DirectError('missing_receipt','No usable remote receipt. Check the original chat manually; do not resubmit.',409,run_id=rid)
            try:
                async with asyncio.timeout(self.timeout):
                    return await self._poll(rid,receipt)
            except DirectError as exc:
                exc.run_id=rid; raise
            except (httpx.HTTPError,TimeoutError):
                raise DirectError('lookup_unconfirmed','Read-only reconciliation did not confirm an outcome.',504,run_id=rid) from None

    def acknowledge(self, rid: str):
        if self.lock.locked(): raise DirectError('busy','A request is active.',409)
        row=self.journal.get(rid)
        if row['state']!='uncertain': raise DirectError('not_uncertain','Run is not uncertain.',409)
        # Human assertion, NOT provider confirmation and NOT a successful generation.
        self.journal.update(rid,state='abandoned',error_code='operator_confirmed_remote_stopped')
        return self.journal.public(rid)

    async def close(self):
        if self.lock.locked(): raise DirectError('busy','Cannot release ownership during an active request.',409)
        if not self.closed:
            self.closed=True
            try: await self.http.aclose()
            finally:
                self.journal.close(); self.owner.close()
