"""Embedded/daemon SDK. No daemon-to-embedded fallback and no POST retries."""
from enum import Enum
from pathlib import Path
from urllib.parse import urlsplit
import os
import time
import httpx
from prism2api.config import Settings
from prism2api.api.models import NativeRunResponse
from prism2api.storage.journal import StorageJournal, GenerationResult
from prism2api.runtime.supervisor import RunSupervisor,RunRecord,RunState
from prism2api.runtime.context import ContextPolicy
from prism2api.runtime.locking import SingleInstanceLockError
from prism2api.errors import PrismError,OutcomeError,WaitTimeoutError,AdmissionBlockedError

class ClientMode(str,Enum):
    EMBEDDED='embedded'
    DAEMON='daemon'

class SDKClient:
    def __init__(self,mode=ClientMode.EMBEDDED,settings=None,*,adapter=None,base_url='http://127.0.0.1:8765',http_client=None):
        self.mode=ClientMode(mode)
        self.settings=settings or Settings()
        self.journal=self.supervisor=self.http=None
        self._owns_http=False
        if self.mode==ClientMode.EMBEDDED:
            self.journal=StorageJournal(self.settings)
            try:
                self.supervisor=RunSupervisor(self.settings,self.journal,adapter)
                self.supervisor.start_worker()
            except BaseException:
                self.journal.close()
                raise
        else:
            if adapter is not None:
                raise ValueError('Daemon mode cannot instantiate a local adapter')
            parsed=urlsplit(base_url)
            if parsed.scheme not in ('http','https') or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
                raise ValueError('Daemon base URL must be a bare loopback HTTP(S) origin')
            # Read only. Never create runtime directories/DB or take the home lock.
            key=self.settings.api_key
            if not key:
                path=self.settings.credentials_dir/'gateway.key'
                if not path.is_file() or path.is_symlink():
                    raise AdmissionBlockedError('Daemon API key not configured')
                key=path.read_text().strip()
            self.http=http_client or httpx.Client(base_url=base_url,headers={'X-API-Key':key},
                timeout=self.settings.timeouts.total_run_seconds,trust_env=False,follow_redirects=False)
            self._owns_http=http_client is None

    def _request(self,method,path,**kwargs):
        response=self.http.request(method,path,**kwargs)
        data=response.json()
        if response.status_code>=400:
            err=data.get('error',{})
            exc=PrismError(err.get('code','daemon_error'),run_id=err.get('run_id'))
            exc.code=err.get('code','daemon_error');exc.http_status=response.status_code
            raise exc
        return data,response.status_code

    def submit(self,input_text,model_alias='prism-default',context_policy=ContextPolicy.ISOLATED,idempotency_key=None,context_id=None,expected_context_revision=None):
        if self.mode==ClientMode.EMBEDDED:
            return self.supervisor.enqueue_run('default_principal',input_text,model_alias,context_policy,idempotency_key,context_id,expected_context_revision)
        data,_=self._request('POST','/prism/v1/runs',json=dict(input_text=input_text,model_alias=model_alias,
            context_policy=ContextPolicy(context_policy).value,idempotency_key=idempotency_key,context_id=context_id,expected_context_revision=expected_context_revision))
        return NativeRunResponse.model_validate(data)

    def wait(self,run_id,timeout=None):
        if self.mode==ClientMode.EMBEDDED:
            return self.supervisor.wait(run_id,timeout,'default_principal')
        deadline=time.monotonic()+(timeout if timeout is not None else self.settings.timeouts.total_run_seconds+self.settings.timeouts.queue_wait_seconds)
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise WaitTimeoutError(run_id=run_id)
            try:
                data,code=self._request('GET',f'/prism/v1/runs/{run_id}/result',timeout=remaining)
            except httpx.TimeoutException as exc:
                raise WaitTimeoutError(run_id=run_id) from exc
            if code==200:
                return GenerationResult.model_validate(data)
            if time.monotonic()>=deadline:
                raise WaitTimeoutError(run_id=run_id)
            time.sleep(min(0.1,max(0,deadline-time.monotonic())))

    def execute_and_wait(self,input_text,model_alias='prism-default',*,idempotency_key=None):
        run=self.submit(input_text,model_alias,idempotency_key=idempotency_key)
        return self.wait(run.run_id)

    def get_run(self,run_id):
        if self.mode==ClientMode.EMBEDDED:
            return self.supervisor.get_run(run_id,'default_principal')
        return self._request('GET',f'/prism/v1/runs/{run_id}')[0]

    def cancel(self,run_id):
        if self.mode==ClientMode.EMBEDDED:
            return self.supervisor.cancel_run(run_id,'default_principal')
        return self._request('POST',f'/prism/v1/runs/{run_id}/cancel')[0]

    def reconcile(self,run_id):
        if self.mode==ClientMode.EMBEDDED:
            return self.supervisor.reconcile_run(run_id,'default_principal')
        return self._request('POST',f'/prism/v1/runs/{run_id}/reconcile')[0]

    def capabilities(self):
        if self.mode==ClientMode.EMBEDDED:
            return self.supervisor.adapter.inspect_capabilities()
        return self._request('GET','/prism/v1/capabilities')[0]

    def close(self):
        if self.journal:
            self.journal.close()
        if self.http and self._owns_http:
            self.http.close()

    def __enter__(self):
        return self

    def __exit__(self,*exc):
        self.close()
