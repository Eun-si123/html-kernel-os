import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {verifyGrammar,matchingTags,loadGrammar,SCHEMA_URL,MAX_SCHEMA_BYTES} from '../site/live/grammar.mjs';

const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'htmlk-grammar-node-'));
const target=path.join(tmp,'htmlk-language.json');
try {execFileSync('python3',['scripts/build_public_language_grammar.py','--out',target],{cwd:process.cwd()});}
catch(e){fs.rmSync(tmp,{recursive:true,force:true});throw e;}
const source=fs.readFileSync(target,'utf8');
const schema=JSON.parse(source);

test('public grammar is produced from the exact compiler, not a JS second parser',()=>{
  assert.equal(verifyGrammar(schema),true);
  assert.equal(schema.schema_version,1);
  assert.equal(Object.keys(schema.tags).length,18);
  assert.ok(schema.tags.print.parents.includes('main'));
  assert.ok(schema.tags.halt.parents.includes('main'));
  assert.ok(schema.tags.print.attributes.includes('value'));
  assert.ok(schema.tags.let.required_attributes.includes('type'));
  assert.equal(SCHEMA_URL,'../htmlk-language.json');
  assert.ok(Buffer.byteLength(source)<MAX_SCHEMA_BYTES);
});

test('search tags, attributes and parent roles without changing native source',()=>{
  assert.deepEqual(matchingTags(schema,'<print>'),[]);
  assert.deepEqual(matchingTags(schema,'print').map(([name])=>name),['print']);
  assert.ok(matchingTags(schema,'main').some(([name])=>name==='print'));
  assert.ok(matchingTags(schema,'value').some(([name])=>name==='print'));
  assert.ok(matchingTags(schema,'').length===18);
  assert.ok(matchingTags(schema,'missing-attribute').length===0);
});

test('client rejects invalid schemas and unbounded fetched metadata',async()=>{
  const bad={...schema,tags:{...schema.tags}};
  bad.tags.print={...bad.tags.print,attributes:['too-large'.repeat(10)]};
  assert.equal(verifyGrammar(bad),false);
  assert.equal(verifyGrammar({tags:[]}),false);
  assert.equal(verifyGrammar(null),false);
  await assert.rejects(loadGrammar(async()=>({ok:true,text:async()=>'{'})),SyntaxError);
  await assert.rejects(loadGrammar(async()=>({ok:false,status:500})),/HTTP 500/);
  await assert.rejects(loadGrammar(async()=>({ok:true,text:async()=> 'X'.repeat(MAX_SCHEMA_BYTES+1)})),/16KiB/);
});

test('actual JSON fetch is read-only and grammar data stays intact',async()=>{
  const grammar=await loadGrammar(async(url,opts)=>{
    assert.equal(url,SCHEMA_URL);
    assert.equal(opts.credentials,'omit');
    return {ok:true,text:async()=>source};
  });
  assert.deepEqual(grammar,schema);
  assert.ok(grammar.compiler_source_sha256['compiler/language.py'].length===64);
});

fs.rmSync(tmp,{recursive:true,force:true});
