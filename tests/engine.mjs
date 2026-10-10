import {build} from 'esbuild';
import assert from 'node:assert/strict';
await build({entryPoints:['src/engine.ts'],bundle:true,platform:'node',format:'esm',outfile:'/tmp/studypilot-engine.mjs',external:['pdfjs-dist','mammoth'],define:{'import.meta.env.VITE_API_URL':'""'}});
const {createKit,sample,questionsFrom,topicStats,factsFrom,splitStudyNotes}=await import('/tmp/studypilot-engine.mjs');
const kit=createKit('Test',sample);
assert.equal(kit.facts.length,10);
assert.equal(kit.questions.length,10);
assert.ok(kit.questions.every(q=>q.options[q.correct]&&sample.includes(q.explanation)));
const retest=questionsFrom(kit.facts,true);
assert.ok(retest.every(q=>!kit.questions.some(old=>old.prompt===q.prompt)));
assert.throws(()=>factsFrom('too short'));
assert.deepEqual(topicStats([]),[]);
assert.equal(topicStats([{results:[{topic:'A',correct:true},{topic:'A',correct:false}]}])[0].score,50);
console.log('Frontend engine checks passed: extraction, answer validity, retest uniqueness, empty evidence and scoring.');

for(const length of [80,42000,42001,53661,84001,300000]){const text=('Paragraph with complete explanatory notes.\n'.repeat(8000)).slice(0,length);const parts=splitStudyNotes(text);assert.equal(parts.join(''),text);assert.ok(parts.every(p=>p.length<=42000&&p.length>=80));}
assert.throws(()=>splitStudyNotes('x'.repeat(300001)));
console.log('Upload section checks passed: size bounds and no lost text.');
