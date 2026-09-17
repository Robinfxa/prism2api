import json
import shlex
import httpx
from prism2api.direct.bootstrap import ORIGIN, START_PATH, STATUS_PATH, HEARTBEAT_PATH


def payload(snapshot_string=False):
    snap={'project_id':'fixture-project-A','conversation_id':'fixture-chat-A','user_id':'fixture-user-A','files':[{'path':'main.tex','version':1}]}
    return {'input':[{'type':'message','role':'system','content':[{'type':'input_text','text':'Preserve this context.'}]},
                     {'type':'message','role':'user','content':[{'type':'input_text','text':'Original captured prompt, must be removed.'}]}],
            'metadata':{'projectId':'fixture-project-A','userId':'fixture-user-A','sandbox_url':ORIGIN+'/s/sandboxes/proxy/',
                        'sandbox_token':'fixture-sandbox-not-a-real-token','model':'fixture-captured-model',
                        'reasoning_effort':'medium','codex_listen_snapshot':json.dumps(snap) if snapshot_string else snap,
                        'unknown_wire_extension':{'keep':True}},'conversationId':'fixture-chat-A'}


def curl(body=None, cookie_style='-b', extra=''):
    body=payload() if body is None else body
    cookie='fixture-session=not-a-real-cookie'
    cookiearg=('-H '+shlex.quote('Cookie: '+cookie)) if cookie_style=='-H' else '-b '+shlex.quote(cookie)
    return 'curl '+shlex.quote(ORIGIN+START_PATH)+' '+cookiearg+' -H '+shlex.quote('User-Agent: FixtureUA/1.0')+' -H '+shlex.quote('Content-Type: application/json')+' --data-raw '+shlex.quote(json.dumps(body,ensure_ascii=False))+(' '+extra if extra else '')


def success(text='fixture-answer',request_id='fixture-request-1'):
    return {'status':'completed','request_id':request_id,'conversation_id':'fixture-chat-A',
            'codex_async_job_id':'fixture-job-1','response':{'status':'success','payload':{
                'conversationId':'fixture-chat-A','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}]}}}


def pending(cursor=1):
    return {'status':'pending','request_id':'fixture-request-1','conversation_id':'fixture-chat-A',
            'turn_state':{'async_job_id':'fixture-job-1','conversation_id':'fixture-chat-A','project_id':'fixture-project-A','cursor':cursor}}


class Upstream:
    def __init__(self, *, start=None, statuses=None, heartbeat_status=200):
        self.start=start
        self.statuses=list(statuses or [])
        self.heartbeat_status=heartbeat_status
        self.requests=[]
        self.last_prompt=None

    async def __call__(self, request):
        self.requests.append(request)
        if request.url.path==HEARTBEAT_PATH:
            return httpx.Response(self.heartbeat_status,json={'healthy':True})
        if request.url.path==START_PATH:
            body=json.loads(request.content)
            self.last_prompt=body['input'][-1]['content'][0]['text']
            if isinstance(self.start,Exception): raise self.start
            result=self.start if self.start is not None else pending()
            return httpx.Response(200,json=result)
        if request.url.path==STATUS_PATH:
            result=self.statuses.pop(0) if self.statuses else success(self.last_prompt)
            if isinstance(result,Exception): raise result
            return httpx.Response(200,json=result)
        raise AssertionError('Unexpected upstream path')

    def client(self):return httpx.AsyncClient(transport=httpx.MockTransport(self))
    def count(self,path):return sum(r.url.path==path for r in self.requests)
