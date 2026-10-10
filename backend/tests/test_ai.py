import json
import httpx
import pytest
from .test_workflow import api, NOTES

@pytest.mark.parametrize('grounded',[True,False])
def test_validated_ai_generation(api,monkeypatch,grounded):
    import backend.main as module
    monkeypatch.setattr(module,'AI_KEY','fake-test-key')
    monkeypatch.setenv('AI_API_KEY','fake-test-key')
    monkeypatch.setenv('REQUIRE_AI','true')
    facts=module.extract_facts(NOTES)
    output={'facts':facts,'questions':module.demo_questions(facts)}
    output['questions'][0]['source_quote']=facts[0]['text'] if grounded else 'A claim absent from the notes.'
    class Provider:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            assert kwargs['headers']['Authorization']=='Bearer fake-test-key'
            assert kwargs['json']['max_tokens']==6000
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(output)}}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(module.httpx,'AsyncClient',Provider)
    doc=api.post('/api/documents/text',json={'name':'AI notes','text':NOTES}).json()
    response=api.post('/api/study-kit/generate',json={'document_id':doc['id']})
    if grounded:
        assert response.status_code==200
        assert response.json()['mode']=='AI generated'
    else:
        assert response.status_code==502
        assert api.get('/api/state').json()['kits']==[]

@pytest.mark.parametrize('status,expected',[(400,'rejected the request'),(401,'rejected the API key'),(403,'denied access'),(404,'model or endpoint'),(429,'quota or rate limit'),(503,'temporarily unavailable')])
def test_provider_error_messages(monkeypatch,status,expected):
    import asyncio
    from fastapi import HTTPException
    import backend.main as module
    monkeypatch.setattr(module,'AI_KEY','private-test-key')
    class Provider:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            return httpx.Response(status,json={'error':{'message':'private-test-key confidential notes'}},request=httpx.Request('POST',url))
    monkeypatch.setattr(module.httpx,'AsyncClient',Provider)
    with pytest.raises(HTTPException) as error:asyncio.run(module.generate(NOTES))
    assert expected in error.value.detail
    assert 'private-test-key' not in error.value.detail
    assert 'confidential' not in error.value.detail

@pytest.mark.parametrize('finish_reason,valid',[('stop',True),('length',False)])
def test_gemini_schema_and_pdf_line_breaks(monkeypatch,finish_reason,valid):
    import asyncio
    from fastapi import HTTPException
    import backend.main as module
    monkeypatch.setattr(module,'AI_KEY','test')
    monkeypatch.setattr(module,'AI_URL','https://generativelanguage.googleapis.com/v1beta/openai')
    facts=module.extract_facts(NOTES)
    output={'facts':facts,'questions':module.demo_questions(facts)}
    # PDF whitespace may differ from the quotation without changing its words.
    text=NOTES.replace(' ', ' \n ')
    class Provider:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            assert kwargs['json']['response_format']['type']=='json_schema'
            assert 'properties' in kwargs['json']['response_format']['json_schema']['schema']
            return httpx.Response(200,json={'choices':[{'finish_reason':finish_reason,'message':{'content':'```json\n'+json.dumps(output)+'\n```'}}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(module.httpx,'AsyncClient',Provider)
    if valid:
        result=asyncio.run(module.generate(text))
        assert result[2]=='AI generated'
        assert len(result[1])==len(output['questions'])
    else:
        with pytest.raises(HTTPException,match='cut short'):asyncio.run(module.generate(text))
