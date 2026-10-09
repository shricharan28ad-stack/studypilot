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
