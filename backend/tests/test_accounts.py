from .test_workflow import api, NOTES

def test_private_data_and_logout(api):
    document=api.post('/api/documents/text',json={'name':'Private notes','text':NOTES}).json()
    kit=api.post('/api/study-kit/generate',json={'document_id':document['id']}).json()
    assert api.post('/api/preferences',json={'name':'A','fontScale':145,'tasks':[],'known':[],'minutes':25}).status_code==200
    old_cookie=api.cookies.get('sp_session')
    assert api.post('/api/auth/logout').status_code==200
    assert api.get('/api/state').status_code==401
    assert api.post('/api/auth/register',json={'name':'Other','email':'other@example.com','password':'another-long-password'}).status_code==200
    assert api.get('/api/state').json()['kits']==[]
    assert api.get('/api/state').json()['preferences']['fontScale']==100
    assert api.get('/api/documents').json()==[]
    for path in ['/api/study-kit/'+kit['id'],'/api/documents/'+document['id']+'/topics']:
        assert api.get(path).status_code==404
    for path,body in [('/api/study-kit/generate',{'document_id':document['id']}),('/api/revision/generate',{'kit_id':kit['id']}),('/api/quizzes/retest',{'kit_id':kit['id']}),('/api/documents/delete',{'kit_id':kit['id']}),('/api/quizzes/'+kit['id']+'/submit',{'answers':[0],'question_ids':['q-0']})]:
        assert api.post(path,json=body).status_code==404
    api.post('/api/auth/logout')
    assert api.post('/api/auth/login',json={'email':'STUDENT@example.com','password':'correct-horse-battery'}).status_code==200
    restored=api.get('/api/state').json()
    assert restored['kits'][0]['id']==kit['id']
    assert restored['preferences']['fontScale']==145
    assert 'HttpOnly' in api.post('/api/auth/login',json={'email':'student@example.com','password':'correct-horse-battery'}).headers['set-cookie']
    from backend.storage import db
    from backend.auth import digest
    with db() as conn:
        assert conn.execute('SELECT * FROM sessions WHERE token_hash=?',(digest(old_cookie),)).fetchone() is None
        assert 'correct-horse-battery' not in conn.execute('SELECT password_hash FROM users WHERE email=?',('student@example.com',)).fetchone()[0]

def test_ai_required_and_limits(api,monkeypatch):
    document=api.post('/api/documents/text',json={'name':'Notes','text':NOTES}).json()
    monkeypatch.setenv('REQUIRE_AI','true')
    assert api.post('/api/study-kit/generate',json={'document_id':document['id']}).status_code==503
    monkeypatch.setenv('REQUIRE_AI','false')
    monkeypatch.setenv('AI_USER_DAILY_LIMIT','1')
    assert api.post('/api/study-kit/generate',json={'document_id':document['id']}).status_code==200
    assert api.post('/api/study-kit/generate',json={'document_id':document['id']}).status_code==200
    another=api.post('/api/documents/text',json={'name':'More notes','text':NOTES+' Extra source sentence.'}).json()
    assert api.post('/api/study-kit/generate',json={'document_id':another['id']}).status_code==429

def test_wrong_password_csrf_and_preferences(api):
    assert api.post('/api/auth/login',json={'email':'student@example.com','password':'wrong-password-123'}).status_code==401
    assert api.post('/api/auth/logout',headers={'Origin':'https://evil.example'}).status_code==403
    assert api.post('/api/preferences',json={'name':'Student','fontScale':999}).status_code==422
