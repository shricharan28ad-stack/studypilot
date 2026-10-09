import importlib
import os
import pytest
from fastapi.testclient import TestClient

NOTES = '''Database foundations
A primary key uniquely identifies each row in a table.
A foreign key creates a relationship by referencing another table.
Normalization organizes data to reduce redundant information.
An inner join returns rows that match in both tables.
Transactions
Atomicity ensures that a transaction completes fully or has no effect.
Durability ensures that committed changes survive system failure.'''

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('STUDYPILOT_DB',str(tmp_path/'test.db'))
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.setenv('REQUIRE_AI','false')
    monkeypatch.delenv('AI_API_KEY',raising=False)
    import backend.main as module
    importlib.reload(module)
    with TestClient(module.app) as client:
        assert client.post('/api/auth/register',json={'name':'Student','email':'student@example.com','password':'correct-horse-battery'}).status_code==200
        yield client

def test_end_to_end(api):
    uploaded=api.post('/api/documents/upload',files={'file':('notes.txt',NOTES.encode(),'text/plain')})
    assert uploaded.status_code==200
    kit=api.post('/api/study-kit/generate',json={'document_id':uploaded.json()['id']}).json()
    assert kit['mode']=='Extractive demo'
    questions=kit['questions']
    assert len(questions)==6
    assert all(q['explanation'] in NOTES for q in questions)
    wrong=[(q['correct']+1)%len(q['options']) for q in questions]
    attempt=api.post('/api/quizzes/'+kit['id']+'/submit',json={'answers':wrong,'question_ids':[q['id'] for q in questions]})
    assert attempt.status_code==200
    assert attempt.json()['score']==0
    revision=api.post('/api/revision/generate',json={'kit_id':kit['id']}).json()
    assert len(revision['topics'])==2
    retest=api.post('/api/quizzes/retest',json={'kit_id':kit['id'],'topics':revision['topics']}).json()
    assert not set(q['prompt'] for q in questions)&set(q['prompt'] for q in retest['questions'])
    second=api.post('/api/quizzes/'+retest['id']+'/submit',json={'answers':[q['correct'] for q in retest['questions']],'question_ids':[q['id'] for q in retest['questions']]}).json()
    assert second['score']==100 and second['retest']
    assert all(t['score']==50 for t in api.get('/api/performance/topics').json())
    assert len(api.get('/api/state').json()['attempts'])==2
    assert api.post('/api/documents/delete',json={'kit_id':kit['id']}).status_code==200
    assert api.get('/api/state').json()['kits']==[]
    assert api.get('/api/state').json()['attempts']==[]

def test_auth_validation_and_documents(api):
    assert api.post('/api/documents/upload',files={'file':('bad.exe',b'test','application/octet-stream')}).status_code==415
    assert api.post('/api/documents/upload',files={'file':('scan.pdf',b'not a pdf','application/pdf')}).status_code==422
    assert api.post('/api/documents/text',json={'name':'n','text':'too short'}).status_code==422
    assert api.post('/api/documents/upload',files={'file':('big.txt',b'x'*(10*1024*1024+1),'text/plain')}).status_code==413
    import pymupdf
    document=pymupdf.open();page=document.new_page();page.insert_text((50,50),NOTES)
    assert api.post('/api/documents/upload',files={'file':('notes.pdf',document.tobytes(),'application/pdf')}).status_code==200
    from docx import Document
    from io import BytesIO
    doc=Document()
    for line in NOTES.splitlines(): doc.add_paragraph(line)
    buf=BytesIO();doc.save(buf)
    assert api.post('/api/documents/upload',files={'file':('notes.docx',buf.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}).status_code==200

def test_reject_manipulated_submission(api):
    doc=api.post('/api/documents/text',json={'name':'Test','text':NOTES}).json()
    kit=api.post('/api/study-kit/generate',json={'document_id':doc['id']}).json()
    endpoint='/api/quizzes/'+kit['id']+'/submit'
    assert api.post(endpoint,json={'answers':[999],'question_ids':[kit['questions'][0]['id']]}).status_code==422
    assert api.post(endpoint,json={'answers':[0],'question_ids':['made-up']}).status_code==422
    assert api.post(endpoint,json={'answers':[0,0],'question_ids':['q-0','q-0']}).status_code==422
    assert api.get('/api/state').json()['attempts']==[]
