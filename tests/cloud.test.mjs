import test from 'node:test';
import assert from 'node:assert/strict';
import handler from '../api/jobs.mjs';
import {readFile,readdir} from 'node:fs/promises';
function response(){return {headers:{},setHeader(k,v){this.headers[k]=v;},status(n){this.code=n;return this;},json(v){this.body=v;return this;}};}
test('anonymous and concurrent callers cannot provision cloud workers',async()=>{
 const replies=await Promise.all(Array.from({length:100},async(_,i)=>{const r=response();await handler({method:'POST',body:i%2?null:{url:'https://youtu.be/cq5EnKIIpxk',youtubeCookies:'must never be processed'}},r);return r;}));
 assert.ok(replies.every(r=>r.code===503&&r.headers['Cache-Control']==='no-store'));
 const r=response();await handler({method:'GET'},r);assert.equal(r.code,200);assert.equal(r.body.cloudEnabled,false);
 for(const method of ['DELETE','PUT','PATCH','OPTIONS']){const r=response();await handler({method},r);assert.equal(r.code,405);}
});
test('public build is an explicit static allowlist with no cookie upload',async()=>{
 assert.deepEqual((await readdir('public')).sort(),['cloud.js','index.html','privacy.html','style.css']);
 const html=await readFile('public/index.html','utf8');assert.doesNotMatch(html,/type="file"|youtubeCookies|<form/);
 const cfg=JSON.parse(await readFile('vercel.json','utf8'));assert.equal(cfg.outputDirectory,'public');
 const csp=cfg.headers[0].headers.find(h=>h.key==='Content-Security-Policy').value;assert.match(csp,/default-src 'none'/);assert.match(csp,/frame-ancestors 'none'/);
});
