from datetime import datetime, timedelta, timezone
from backend.revision import revision_plan
from .test_workflow import api, NOTES

BASE=datetime(2026,1,1,tzinfo=timezone.utc)
KIT={'id':'k','facts':[{'topic':'Keys','text':'A key identifies a row.'}]}
def attempt(day,correct=True):
    return {'kitId':'k','date':(BASE+timedelta(days=day)).isoformat(),
        'results':[{'topic':'Keys','correct':correct,'difficulty':'Foundational','level':'Recall'}]}

def test_schedule_progresses_only_on_due_reviews():
    first=revision_plan(KIT,[attempt(0)],BASE)['topics'][0]
    assert first['difficulty']=='Intermediate' and first['intervalDays']==1 and not first['due']
    early=revision_plan(KIT,[attempt(0),attempt(.5)],BASE+timedelta(hours=12))['topics'][0]
    assert early['dueAt']==first['dueAt'] and early['streak']==1
    later=revision_plan(KIT,[attempt(0),attempt(1)],BASE+timedelta(days=1))['topics'][0]
    assert later['difficulty']=='Advanced' and later['intervalDays']==3
    assert later['dueAt']==(BASE+timedelta(days=4)).isoformat()

def test_mistakes_reduce_difficulty_and_reset_spacing():
    row=revision_plan(KIT,[attempt(0),attempt(1),attempt(4,False)],BASE+timedelta(days=4))['topics'][0]
    assert row['difficulty']=='Intermediate' and row['streak']==0 and row['mistakes']==1
    assert row['dueAt']==(BASE+timedelta(days=4,minutes=10)).isoformat()
    assert revision_plan(KIT,[attempt(0,False)],BASE+timedelta(minutes=11))['dueCount']==1

def test_unseen_topics_due_and_other_kits_ignored():
    other=attempt(0);other['kitId']='other'
    row=revision_plan(KIT,[other],BASE)['topics'][0]
    assert row['due'] and row['reviews']==0 and row['difficulty']=='Foundational'

def test_plan_uses_saved_answers_and_submission_is_idempotent(api):
    doc=api.post('/api/documents/text',json={'name':'Notes','text':NOTES}).json()
    kit=api.post('/api/study-kit/generate',json={'document_id':doc['id']}).json()
    plan=api.get('/api/revision/plan/'+kit['id']).json()
    assert plan['dueCount']==len(plan['topics'])
    body={'question_ids':[q['id'] for q in kit['questions']],'answers':[q['correct'] for q in kit['questions']]}
    url='/api/quizzes/'+kit['id']+'/submit'
    first=api.post(url,json=body).json()
    assert api.post(url,json=body).json()['id']==first['id']
    plan=api.get('/api/revision/plan/'+kit['id']).json()
    assert plan['dueCount']==0
    assert all(t['difficulty']=='Intermediate' and t['reviews']==1 for t in plan['topics'])
    assert api.get('/api/revision/plan/not-owned').status_code==404

def test_adaptive_request_enforces_target_difficulty(api,monkeypatch):
    import asyncio,json,httpx
    import backend.main as module
    monkeypatch.setattr(module,'AI_KEY','test')
    monkeypatch.setattr(module,'AI_URL','https://example.com/v1')
    facts=module.extract_facts(NOTES)
    questions=module.demo_questions(facts)
    targets={q['topic']:'Advanced' for q in questions}
    calls=[]
    class Provider:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            calls.append(kwargs['json'])
            assert 'target difficulties' in kwargs['json']['messages'][0]['content']
            if len(calls)>1:
                for q in questions:q['difficulty']='Advanced'
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'facts':facts,'questions':questions})}}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(module.httpx,'AsyncClient',Provider)
    result=asyncio.run(module.generate(NOTES,difficulty_targets=targets))
    assert len(calls)==2 and all(q['difficulty']=='Advanced' for q in result[1])

def test_question_topics_are_never_lost_when_fact_labels_differ():
    kit={'id':'k','facts':[{'topic':'General notes','text':'Source notes.'}],
        'questions':[{'topic':'Keys'}]}
    plan=revision_plan(kit,[attempt(0,False)],BASE)
    topic=next(t for t in plan['topics'] if t['topic']=='Keys')
    assert topic['mistakes']==1 and topic['reviews']==1
