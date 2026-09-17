"""Wire validation shared by submit, polling and exact-target reconciliation."""
import json
from .errors import DirectError

PENDING = {'pending','running','in_progress','accepted','queued'}


def protocol(code='wire_schema'):
    return DirectError(code, 'Prism returned an unrecognized or conflicting response. No automatic resubmit.')


def state_object(value):
    if isinstance(value, dict): return value
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            return {}
    return {}


def identity(data: dict, receipt: dict, *, require_request_id=True):
    if not isinstance(data, dict): raise protocol()
    rid = data.get('request_id')
    if require_request_id and not isinstance(rid, str): raise protocol('missing_request_id')
    if rid is not None and rid != receipt['request_id']: raise protocol('identity_mismatch')
    response = data.get('response')
    payload = response.get('payload') if isinstance(response, dict) else None
    locations = [data]
    if isinstance(payload, dict): locations.append(payload)
    if 'turn_state' in data:
        locations.append(state_object(data['turn_state']))
    expected_state = state_object(receipt.get('turn_state'))
    expected_job = expected_state.get('async_job_id') or receipt.get('async_job_id')
    for loc in locations:
        for name in ('conversationId','conversation_id'):
            if name in loc and loc[name] != receipt['conversation_id']: raise protocol('identity_mismatch')
        for name in ('projectId','project_id'):
            if name in loc and loc[name] != receipt['project_id']: raise protocol('identity_mismatch')
        if expected_job:
            for name in ('async_job_id','codex_async_job_id'):
                if name in loc and loc[name] != expected_job: raise protocol('identity_mismatch')


def failure_code(data: dict) -> str:
    response = data.get('response')
    payload = response.get('payload', {}) if isinstance(response, dict) else {}
    if not isinstance(payload, dict): return 'upstream_failed'
    debug = payload.get('codexRequestDebug', {})
    detail = debug.get('error', {}) if isinstance(debug, dict) else {}
    code = payload.get('httpStatus') or (detail.get('status') if isinstance(detail, dict) else None)
    if code == 401: return 'sandbox_unauthorized'
    if code == 403: return 'upstream_forbidden'
    if payload.get('reason') == 'sandbox_reconnecting': return 'sandbox_not_ready'
    if code == 504: return 'sandbox_sync_timeout'
    return 'upstream_failed'


def terminal(data: dict) -> tuple[str, str | None]:
    if not isinstance(data, dict): raise protocol()
    root = data.get('status')
    response = data.get('response')
    inner = response.get('status') if isinstance(response, dict) else None
    if root in ('failed','error','cancelled','canceled') and inner == 'success':
        raise protocol('terminal_conflict')
    if inner == 'error' or root in ('failed','error'):
        return 'failed', failure_code(data)
    if root in ('cancelled','canceled'):
        return 'cancelled', 'upstream_cancelled'
    if root == 'completed':
        if inner != 'success': raise protocol('terminal_schema')
        payload = response.get('payload')
        if not isinstance(payload, dict) or not isinstance(payload.get('output'), list): raise protocol('output_schema')
        texts = []
        for output in payload['output']:
            if not isinstance(output, dict): raise protocol('output_schema')
            if output.get('type') not in (None,'message'):
                # Upstream reasoning/tool traces are not client-side function calls.
                continue
            if output.get('role') not in (None, 'assistant'): continue
            content = output.get('content')
            if not isinstance(content, list): raise protocol('output_schema')
            for item in content:
                if not isinstance(item, dict): raise protocol('output_schema')
                if item.get('type') in ('output_text','text'):
                    if not isinstance(item.get('text'), str): raise protocol('output_schema')
                    texts.append(item['text'])
        if not texts: raise protocol('missing_output_text')
        return 'succeeded', ''.join(texts)
    if root in PENDING and inner in (None,'success','pending','running'):
        return 'running', None
    raise protocol('unknown_status')
