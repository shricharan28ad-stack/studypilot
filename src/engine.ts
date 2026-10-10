export type Fact={topic:string,text:string};
export type Question={id:string,topic:string,prompt:string,options:string[],correct:number,explanation:string,difficulty:string,level:string};
export type Kit={id:string,name:string,date:string,text:string,facts:Fact[],questions:Question[],mode:string};
export type Attempt={id:string,kitId:string,date:string,score:number,results:{topic:string,correct:boolean,difficulty:string,level:string}[],retest:boolean};
export type Task={id:string,title:string,date:string,done:boolean};
export type State={kits:Kit[],attempts:Attempt[],known:string[],tasks:Task[],minutes:number,name:string,fontScale?:number};
export const uid=()=>crypto.randomUUID();
export const sample=`Relational databases\nA primary key uniquely identifies each row in a table.\nA foreign key creates a relationship by referencing a key in another table.\nNormalization organizes data to reduce redundancy and improve data integrity.\nAn inner join returns rows with matching values in both tables.\nA left join returns all rows from the left table and matching rows from the right table.\nTransactions\nAtomicity ensures that a transaction either completes fully or does not take effect.\nConsistency ensures that a transaction preserves database constraints.\nIsolation prevents concurrent transactions from interfering with one another.\nDurability ensures that committed changes survive a system failure.\nAn index speeds up data retrieval but adds overhead to write operations.`;
export function factsFrom(text:string):Fact[]{
 const parts=text.replace(/\r/g,'').split(/\n+|(?<=[.!?])\s+(?=[A-Z])/).map(s=>s.trim()).filter(Boolean);let topic='Key concepts';const facts:Fact[]=[];
 for(const line of parts){if(line.length<55&&!/[.!?]$/.test(line)){topic=line.replace(/^#+\s*/,'');continue;}if(line.length>=30&&line.length<800)facts.push({topic,text:line});}
 if(facts.length<4)throw Error('Please add at least four complete explanatory sentences. Definition-rich notes work best in demo mode.');return facts.slice(0,80);
}
export function questionsFrom(facts:Fact[],retest=false):Question[]{return facts.map((f,i)=>{
 const words=f.text.replace(/[.!?]$/,'').split(' ');const cut=Math.max(2,Math.min(6,Math.floor(words.length*.35)));const head=words.slice(0,cut).join(' '),tail=words.slice(cut).join(' ');
 const answer=retest?head:tail;const others=facts.filter(x=>x.text!==f.text).map(x=>{const w=x.text.replace(/[.!?]$/,'').split(' ');const c=Math.max(2,Math.min(6,Math.floor(w.length*.35)));return retest?w.slice(0,c).join(' '):w.slice(c).join(' ')}).filter(x=>x!==answer);
 const options=[...new Set([answer,...others])].slice(0,4);const shift=i%options.length;options.push(...options.splice(0,shift));return {id:`${retest?'r':'q'}-${i}`,topic:f.topic,prompt:retest?`Complete the statement from your notes: “_____ ${tail}.”`:`According to your notes, complete: “${head} _____.”`,options,correct:options.indexOf(answer),explanation:f.text,difficulty:'Foundational',level:'Recall'};
 }).filter(q=>q.options.length>=2)}
export function createKit(name:string,text:string):Kit{const facts=factsFrom(text);return{id:uid(),name,date:new Date().toISOString(),text,facts,questions:questionsFrom(facts),mode:'Extractive demo'};}
export const initial:State={kits:[{...createKit('Database essentials',sample),id:'sample-db',mode:'Example · extractive demo'}],attempts:[],known:[],tasks:[],minutes:0,name:'Student',fontScale:100};
export function topicStats(attempts:Attempt[]){const map:Record<string,{n:number,c:number}>= {};attempts.forEach(a=>a.results.forEach(r=>{map[r.topic]??={n:0,c:0};map[r.topic].n++;map[r.topic].c+=Number(r.correct)}));return Object.entries(map).map(([topic,v])=>({topic,attempted:v.n,score:Math.round(v.c/v.n*100)}));}
export async function extractFile(file:File){if(file.size>10*1024*1024)throw Error('Your file is over 10 MB. Please upload a smaller document.');const ext=file.name.split('.').pop()?.toLowerCase();if(ext==='txt')return file.text();if(ext==='docx'){const mammoth=await import('mammoth');return (await mammoth.extractRawText({arrayBuffer:await file.arrayBuffer()})).value;}if(ext==='pdf'){const pdf=await import('pdfjs-dist');pdf.GlobalWorkerOptions.workerSrc=new URL('pdfjs-dist/build/pdf.worker.min.mjs',import.meta.url).href;const doc=await pdf.getDocument({data:await file.arrayBuffer()}).promise;if(doc.numPages>150)throw Error('Please split PDFs longer than 150 pages.');let text='';for(let n=1;n<=doc.numPages;n++){const content=await(await doc.getPage(n)).getTextContent();text+=content.items.map(x=>'str'in x?x.str+('hasEOL'in x&&x.hasEOL?'\n':' '):'').join('')+'\n';}if(text.trim().length<80)throw Error('This PDF has no readable text. Scanned notes need OCR before uploading.');return text;}throw Error('Choose a PDF, DOCX or TXT file.');}
const configuredApi=(import.meta as unknown as {env:Record<string,string>}).env.VITE_API_URL||'';
export const apiBase=configuredApi==='same-origin'?window.location.origin:configuredApi.replace(/\/$/,'');
export async function api(path:string,body?:unknown){const res=await fetch(apiBase+path,{method:body?'POST':'GET',credentials:'include',headers:{...(body instanceof FormData?{}:{'Content-Type':'application/json'})},body:body?(body instanceof FormData?body:JSON.stringify(body)):undefined});if(res.status===401&&!path.includes('/auth/'))window.dispatchEvent(new Event('session-expired'));if(!res.ok){const error=await res.json().catch(()=>({detail:'Server unavailable'}));throw Error(typeof error.detail==='string'?error.detail:'The request was invalid. Please check your input.');}return res.json();}

export function splitStudyNotes(text:string,limit=42000):string[]{
 if(text.length>300000)throw Error('Please split documents larger than 300,000 characters.');
 const sections:string[]=[];let remaining=text;
 while(remaining.length>limit){
  const target=Math.ceil(remaining.length/Math.ceil(remaining.length/limit));
  const boundary=remaining.lastIndexOf('\n',target);
  const cut=boundary>target*.75?boundary+1:target;
  sections.push(remaining.slice(0,cut));remaining=remaining.slice(cut);
 }
 if(remaining)sections.push(remaining);
 return sections;
}
