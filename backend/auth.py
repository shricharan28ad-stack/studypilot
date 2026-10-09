import os,hashlib,secrets,time,sqlite3,json
from uuid import uuid4
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,Field,model_validator
from .storage import db
router=APIRouter()
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password):
    salt=secrets.token_hex(16)
    value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return salt+':'+value
def password_matches(password,stored):
    salt,value=stored.split(':')
    candidate=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return secrets.compare_digest(value,candidate)
DUMMY_HASH=password_hash('timing-only-unusable-password')
def consume_limits(entries):
    exceeded=False
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DELETE FROM rate_limits WHERE expires<?',(time.time(),))
        for key,maximum,seconds in entries:
            row=conn.execute('SELECT count FROM rate_limits WHERE key=?',(key,)).fetchone()
            if row and row['count']>=maximum:exceeded=True
        if not exceeded:
            for key,maximum,seconds in entries:
                conn.execute('INSERT INTO rate_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,time.time()+seconds))
    if exceeded:raise HTTPException(429,'Request limit reached. Please try again later.')
def reserve_generation(user):
    if os.getenv('REQUIRE_AI','true').lower()=='true' and not os.getenv('AI_API_KEY'):raise HTTPException(503,'The administrator must configure the AI provider before generation is available.')
    consume_limits([('ai:'+user['id'],int(os.getenv('AI_USER_DAILY_LIMIT','10')),86400),('ai:global',int(os.getenv('AI_GLOBAL_DAILY_LIMIT','100')),86400)])
def current_user(request:Request):
    with db() as conn:
        row=conn.execute('SELECT u.id,u.email,u.name FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(digest(request.cookies.get('sp_session','')),time.time())).fetchone()
    if not row:raise HTTPException(401,'Please sign in to your StudyPilot account.')
    return dict(row)
def create_session(user_id,response):
    token=secrets.token_urlsafe(32)
    with db() as conn:
        conn.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
        conn.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),user_id,time.time()+604800))
    response.set_cookie('sp_session',token,max_age=604800,httponly=True,secure=os.getenv('COOKIE_SECURE','true').lower()=='true',samesite='lax',path='/')
class AuthInput(BaseModel):
    email:str=Field(min_length=5,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password:str=Field(min_length=10,max_length=128)
class Registration(AuthInput):
    name:str=Field(min_length=1,max_length=40)
    @model_validator(mode='after')
    def name_required(self):
        if not self.name.strip():raise ValueError('Enter your name')
        return self
class Task(BaseModel):
    id:str=Field(max_length=100)
    title:str=Field(min_length=1,max_length=120)
    date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    done:bool
class Preferences(BaseModel):
    name:str=Field(min_length=1,max_length=40)
    known:list[str]=Field(default_factory=list,max_length=10000)
    tasks:list[Task]=Field(default_factory=list,max_length=500)
    minutes:int=Field(default=0,ge=0,le=10000000)
    fontScale:int=Field(default=100,ge=85,le=150)
def read_preferences(user):
    with db() as conn:row=conn.execute('SELECT payload FROM user_preferences WHERE user_id=?',(user['id'],)).fetchone()
    return json.loads(row['payload']) if row else {'known':[],'tasks':[],'minutes':0,'name':user['name'],'fontScale':100}
@router.post('/api/auth/register')
def register(body:Registration,request:Request,response:Response):
    if os.getenv('ALLOW_REGISTRATION','true').lower()!='true':raise HTTPException(403,'New registrations are currently closed.')
    ip=request.client.host if request.client else 'unknown'
    consume_limits([('register:'+digest(ip),5,3600)])
    user={'id':str(uuid4()),'email':body.email.strip().lower(),'name':body.name.strip()}
    hashed=password_hash(body.password)
    try:
        with db() as conn:conn.execute('INSERT INTO users VALUES(?,?,?,?,?)',(user['id'],user['email'],user['name'],hashed,datetime.now(timezone.utc).isoformat()))
    except sqlite3.IntegrityError:raise HTTPException(409,'Unable to create this account. Try signing in instead.')
    create_session(user['id'],response)
    return user
@router.post('/api/auth/login')
def login(body:AuthInput,request:Request,response:Response):
    email=body.email.strip().lower();ip=request.client.host if request.client else 'unknown'
    consume_limits([('login-ip:'+digest(ip),30,900),('login-email:'+digest(email),10,900)])
    with db() as conn:row=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    valid=password_matches(body.password,row['password_hash'] if row else DUMMY_HASH)
    if not row or not valid:raise HTTPException(401,'Incorrect email or password.')
    create_session(row['id'],response)
    return {k:row[k] for k in ['id','email','name']}
@router.get('/api/auth/me')
def me(user=Depends(current_user)):return user
@router.post('/api/auth/logout')
def logout(request:Request,response:Response):
    with db() as conn:conn.execute('DELETE FROM sessions WHERE token_hash=?',(digest(request.cookies.get('sp_session','')),))
    response.delete_cookie('sp_session',path='/',secure=os.getenv('COOKIE_SECURE','true').lower()=='true',httponly=True,samesite='lax')
    return {'signed_out':True}
@router.post('/api/preferences')
def preferences(body:Preferences,user=Depends(current_user)):
    with db() as conn:
        conn.execute('INSERT INTO user_preferences VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload',(user['id'],body.model_dump_json()))
        conn.execute('UPDATE users SET name=? WHERE id=?',(body.name,user['id']))
    return {'saved':True}
