import json
import os
from pathlib import Path
import shlex
import pytest
from prism2api.direct.bootstrap import Bootstrap,parse_curl,import_curl,ORIGIN,START_PATH
from prism2api.direct.errors import DirectError
from .helpers import payload,curl

@pytest.mark.parametrize('style',['-b','-H'])
@pytest.mark.parametrize('string_snapshot',[True,False])
def test_full_roundtrip_same_bundle(tmp_path,style,string_snapshot):
    body=payload(string_snapshot)
    b=import_curl(curl(body,style),tmp_path)
    saved=Bootstrap.load(tmp_path/'bootstrap.json')
    assert saved.import_id==b.import_id
    assert saved.metadata['codex_listen_snapshot']==body['metadata']['codex_listen_snapshot']
    assert type(saved.metadata['codex_listen_snapshot']) is type(body['metadata']['codex_listen_snapshot'])
    expected=body
    expected['input'][-1]['content'][0]['text']='New prompt Ω'
    assert saved.payload('New prompt Ω')==expected
    assert saved.template['input'][-1]['content'][0]['text']==''
    assert (tmp_path/'bootstrap.json').stat().st_mode & 0o777==0o600
    assert tmp_path.stat().st_mode & 0o777==0o700
    assert 'fixture-sandbox-not-a-real-token' not in repr(saved)

@pytest.mark.parametrize('prompt',["I'm here",'line1\nline2', '中文🙂', '\\ backslash " quote', "$(touch /tmp/SHOULD_NOT_EXIST_PRISM_TEST)"])
def test_posix_quotes_are_parsed_not_executed(prompt):
    b=payload();b['input'][-1]['content'][0]['text']=prompt
    h,got=parse_curl(curl(b))
    assert got==b
    assert not Path('/tmp/SHOULD_NOT_EXIST_PRISM_TEST').exists()


def test_ansi_quoted_data():
    b=payload();b['input'][-1]['content'][0]['text']="it's test"
    data=json.dumps(b).replace('\\','\\\\').replace("'","\\'")
    source='curl '+ORIGIN+START_PATH+' -b "c=fixture" -A FixtureUA --data-raw $\''+data+"'"
    assert parse_curl(source)[1]==b

@pytest.mark.parametrize('extra',['--output /tmp/result','--config /tmp/x','; echo dangerous','--proxy http://example.com','--insecure','--data @/tmp/secret','https://example.com','--retry 3'])
def test_unsupported_curl_never_executes(extra):
    with pytest.raises(DirectError):parse_curl(curl(extra=extra))

@pytest.mark.parametrize('bad_url',['http://prism.openai.com','https://evil.example','https://prism.openai.com.evil.example','https://user:pw@prism.openai.com','https://prism.openai.com:443'])
def test_wrong_origin_is_rejected(tmp_path,bad_url):
    with pytest.raises(DirectError):import_curl(curl().replace(ORIGIN,bad_url,1),tmp_path)

@pytest.mark.parametrize('field',['projectId','userId','sandbox_url','sandbox_token','codex_listen_snapshot'])
def test_no_metadata_fallbacks(tmp_path,field):
    b=payload();del b['metadata'][field]
    with pytest.raises(DirectError):import_curl(curl(b),tmp_path)
    assert not (tmp_path/'bootstrap.json').exists()

@pytest.mark.parametrize('case',['cookie','ua','conversation','body','snapshot_identity','snapshot_list','multiple_texts','invalid_json'])
def test_incomplete_import_does_not_overwrite(tmp_path,case):
    import_curl(curl(),tmp_path)
    old=(tmp_path/'bootstrap.json').read_bytes()
    b=payload();cmd=curl(b)
    if case=='cookie':cmd=cmd.replace("-b fixture-session=not-a-real-cookie",'')
    elif case=='ua':cmd=cmd.replace("-H 'User-Agent: FixtureUA/1.0'",'')
    elif case=='conversation':del b['conversationId'];cmd=curl(b)
    elif case=='body':cmd='curl '+ORIGIN+START_PATH
    elif case=='snapshot_identity':b['metadata']['codex_listen_snapshot']['project_id']='wrong';cmd=curl(b)
    elif case=='snapshot_list':b['metadata']['codex_listen_snapshot']=[];cmd=curl(b)
    elif case=='multiple_texts':b['input'][-1]['content']*=2;cmd=curl(b)
    elif case=='invalid_json':cmd='curl '+ORIGIN+START_PATH+' --data-raw notjson'
    with pytest.raises(DirectError):import_curl(cmd,tmp_path)
    assert (tmp_path/'bootstrap.json').read_bytes()==old


def test_original_headers_kept_hop_headers_removed(tmp_path):
    b=import_curl(curl(extra="-H 'sec-ch-ua: fixture' -H 'Content-Length: 999' -H 'Accept-Encoding: gzip'"),tmp_path)
    h=b.request_headers()
    assert h['user-agent']=='FixtureUA/1.0' and h['sec-ch-ua']=='fixture'
    assert 'content-length' not in h and 'accept-encoding' not in h


def test_private_file_refused_if_world_readable(tmp_path):
    import_curl(curl(),tmp_path);p=tmp_path/'bootstrap.json';p.chmod(0o644)
    with pytest.raises(DirectError,match='0600'):Bootstrap.load(p)


def test_symlink_profile_refused(tmp_path):
    home=tmp_path/'home';import_curl(curl(),home)
    link=tmp_path/'profile-link';link.symlink_to(home/'bootstrap.json')
    with pytest.raises(DirectError):Bootstrap.load(link)


def test_conflicting_duplicate_headers_rejected():
    with pytest.raises(DirectError):parse_curl(curl(extra="-H 'User-Agent: DifferentUA'"))


def test_json_duplicate_keys_rejected():
    cmd='curl '+ORIGIN+START_PATH+' --data-raw '+shlex.quote('{"input":[],"input":[]}')
    with pytest.raises(DirectError):parse_curl(cmd)
