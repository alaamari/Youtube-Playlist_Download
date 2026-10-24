import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {validate,sign,verify} from '../lib/security.mjs';
import {createHandler} from '../api/jobs.mjs';
import {AdmissionError,reserve,release} from '../lib/admission.mjs';
const origin='https://youtube-playlist-download.vercel.app';
const fixture={url:'https://open.spotify.com/album/3eZWAHSjyU30lfC89F2jnQ',format:'mp3'};
function response(){return {headers:{},setHeader(k,v){this.headers[k]=v;},status(n){this.code=n;return this;},json(v){this.body=v;return this;}};}
function env(){process.env.MEDIAFLOW_SIGNING_SECRET='test-signing-secret-only';process.env.MEDIAFLOW_SNAPSHOT_ID='test-snapshot';process.env.KV_REST_API_URL='https://fixture.invalid';process.env.KV_REST_API_TOKEN='fixture-only';}
function request(body=fixture){return {method:'POST',headers:{origin,'x-vercel-forwarded-for':'192.0.2.1'},body};}
test('strict sources and credentials are rejected before resource allocation',()=>{
 for(const url of ['https://youtube.com/redirect?q=http://127.0.0.1','https://youtube.com/watch?v=bad','https://open.spotify.com.evil.test/album/3eZWAHSjyU30lfC89F2jnQ','http://youtu.be/cq5EnKIIpxk','https://www.youtube.com/watch?v=cq5EnKIIpxk&v=cq5EnKIIpxk'])assert.throws(()=>validate({...fixture,url}));
 assert.throws(()=>validate({...fixture,youtubeCookies:'not accepted'}));
 assert.equal(validate({...fixture,url:fixture.url+'?si=tracking'}).url,fixture.url);
 assert.equal(validate({url:'https://youtu.be/cq5EnKIIpxk?si=tracking',format:'mp4'}).provider,'youtube');
});
test('bots, invalid origins and denied budgets create no worker',async()=>{
 env();let creates=0;const Worker={create:async()=>{creates++;throw new Error('must not create');}};
 for(const scenario of ['bot','origin','budget','validation']){
  const handler=createHandler({Worker,botCheck:async()=>({isBot:scenario==='bot',isHuman:scenario!=='bot'}),admit:async()=>{throw new AdmissionError('Allowance reached.',429,60);}});
  const req=request(scenario==='validation'?{...fixture,url:'https://evil.test'}:fixture);if(scenario==='origin')req.headers.origin='https://evil.test';
  const res=response();await handler(req,res);assert.ok([400,403,429].includes(res.code),scenario);
 }
 assert.equal(creates,0);
});
test('shared rolling quotas survive the stale-lock recovery migration',async()=>{
 env();const calls=[];const req=request();
 await reserve(req,'fixture-owner',async(...args)=>{calls.push(args);return [1,9,0];});
 assert.equal(calls[0][3],'mediaflow:{v2}:active-v4');assert.equal(calls[0][4],'mediaflow:{v2}:sessions');
 assert.match(calls[0][5],/^mediaflow:\{v2\}:client:[a-f0-9]{64}$/);
 await release('fixture-owner',async(...args)=>{calls.push(args);return 1;});
 assert.equal(calls[1][3],'mediaflow:{v2}:active-v4');
});
test('atomic admission owns concurrency; workers are ephemeral, bounded and scoped',async()=>{
 env();let active=false,creates=0,options,files,commands=[],stopped=0;
 const Worker={async create(o){creates++;options=o;return {async writeFiles(value){files=value;},async runCommand(value){commands.push(value);return {exitCode:0};},domain(){return 'https://fixture-worker.vercel.run';},async stop(){stopped++;}};},async get(){return {async stop(){stopped++;}};}};
 const handler=createHandler({Worker,botCheck:async()=>({isBot:false,isHuman:true}),admit:async()=>{if(active)throw new AdmissionError('Busy.',409);active=true;return {remaining:9};},free:async()=>{active=false;},command:async()=> 'PONG'});
 const replies=await Promise.all(Array.from({length:20},async()=>{const res=response();await handler(request(),res);return res;}));
 assert.equal(creates,1);assert.equal(replies.filter(r=>r.code===202).length,1);assert.equal(replies.filter(r=>r.code===409).length,19);
 const started=replies.find(r=>r.code===202).body;
 assert.equal(options.persistent,false);assert.equal(options.runtime,'node22');assert.equal(options.resources.vcpus,1);assert.equal(options.timeout,1200000);assert.ok(options.networkPolicy.subnets.deny.includes('169.254.0.0/16'));
 assert.equal(options.source.snapshotId,'test-snapshot');assert.ok(commands.every(c=>c.cmd==='/vercel/mediaflow-venv/bin/python'));
 assert.ok(files.some(f=>f.path==='/vercel/spotdl_cli.py'));assert.ok(files.every(f=>!f.path.includes('cookie')));
 assert.ok(options.env.FILE_KEY);assert.equal(started.fileKey,undefined);assert.equal(started.domain.includes('key='),false);
 const ticket=verify(started.ticket,process.env.MEDIAFLOW_SIGNING_SECRET);assert.equal(ticket.p,'cancel');assert.throws(()=>verify(started.ticket+'x',process.env.MEDIAFLOW_SIGNING_SECRET));
 const cancel=response();await handler(request({action:'cancel',ticket:started.ticket}),cancel);assert.equal(cancel.code,200);assert.equal(active,false);assert.equal(stopped,1);
});
test('Spotify playlist limits wrap spotDL’s actual song-list resolver',async()=>{
 const source=await readFile('cloud/spotdl_cli.py','utf8');
 assert.match(source,/spotdl\.utils\.search/);assert.match(source,/get_simple_songs/);assert.match(source,/len\(songs\)>20/);
 assert.doesNotMatch(source,/spotdl\.console\.download|\.parse_query/);
});
test('failed worker setup stops the worker before releasing admission',async()=>{
 env();const order=[];const worker={async writeFiles(){throw new Error('upload failed');},async stop(){order.push('stop');}};
 const h=createHandler({Worker:{create:async()=>worker},botCheck:async()=>({isBot:false,isHuman:true}),admit:async()=>({remaining:9}),free:async()=>order.push('release')});
 const r=response();await h(request(),r);assert.equal(r.code,502);assert.deepEqual(order,['stop','release']);
});
test('failed sandbox creation releases the lease when SDK reports 404 in response.status',async()=>{
 env();const order=[];
 const h=createHandler({Worker:{create:async()=>{throw new Error('create failed');},get:async()=>{throw Object.assign(new Error('not found'),{response:{status:404}});}},botCheck:async()=>({isBot:false,isHuman:true}),admit:async()=>({remaining:9}),free:async()=>order.push('release')});
 const r=response();await h(request(),r);assert.equal(r.code,502);assert.deepEqual(order,['release']);
});
test('static build publishes an allowlist and keeps cookies and credentials out of forms',async()=>{
 assert.deepEqual((await readdir('public')).sort(),['cloud.js','index.html','privacy.html','style.css']);
 const html=await readFile('public/index.html','utf8');assert.doesNotMatch(html,/type="file"|youtubeCookies|Cloud downloads are paused/);assert.match(html,/id="form"/);assert.match(html,/v1\.3\.0/);
 const cfg=JSON.parse(await readFile('vercel.json','utf8'));assert.equal(cfg.outputDirectory,'public');const csp=cfg.headers[0].headers.find(x=>x.key==='Content-Security-Policy').value;assert.match(csp,/default-src 'none'/);assert.match(csp,/https:\/\/\*\.vercel\.run/);
});
