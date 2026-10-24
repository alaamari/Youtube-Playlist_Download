import test from 'node:test';import assert from 'node:assert/strict';import {validate,sign,verify,youtubeCookies} from '../lib/security.mjs';
test('strict provider validation',()=>{for(const url of ['https://open.spotify.com.evil.test/x','http://youtube.com/watch?v=x','https://youtube.com@evil.test/x'])assert.throws(()=>validate({url,format:'mp3'}));assert.equal(validate({url:'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M',format:'mp3'}).provider,'spotify');assert.throws(()=>validate({url:'https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT',format:'mp4'}));});
test('signed job tickets reject tampering and expiration',()=>{const ticket=sign({name:'test',exp:Date.now()+10000},'secret');assert.equal(verify(ticket,'secret').name,'test');assert.throws(()=>verify(ticket,'other'));assert.throws(()=>verify(sign({exp:0},'secret'),'secret'));});

test('cloud health and download start work without an access key',async()=>{
  const {Sandbox}=await import('@vercel/sandbox');
  const {mock}=await import('node:test');
  const {default:handler}=await import('../api/jobs.mjs');
  const previous={secret:process.env.MEDIAFLOW_SIGNING_SECRET,snapshot:process.env.MEDIAFLOW_SNAPSHOT_ID};
  process.env.MEDIAFLOW_SIGNING_SECRET='test-internal-signing-secret';
  process.env.MEDIAFLOW_SNAPSHOT_ID='test-snapshot';
  const result=()=>({statusCode:0,body:null,setHeader(){},status(code){this.statusCode=code;return this;},json(body){this.body=body;return this;}});
  const list=mock.method(Sandbox,'list',async()=>({async *[Symbol.asyncIterator](){}}));
  let uploaded=[];
  const create=mock.method(Sandbox,'create',async()=>({writeFiles:async files=>{uploaded=files;},runCommand:async()=>{},domain:()=> 'https://test-worker.invalid',stop:async()=>{}}));
  try{
    const health=result();await handler({method:'GET',headers:{}},health);
    assert.equal(health.statusCode,200);
    const start=result();await handler({method:'POST',headers:{host:'example.vercel.app'},body:{url:'https://youtu.be/test-video',format:'mp3',youtubeCookies:'# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tfixture-session-only\n.google.com\tTRUE\t/\tTRUE\t0\tSID\tremove-this-fixture\n'}},start);
    assert.equal(start.statusCode,202);assert.ok(start.body.ticket);assert.ok(start.body.jobKey);
    const cookies=uploaded.find(f=>f.path.endsWith('youtube-cookies.txt'));assert.equal(cookies.mode,0o600);assert.match(cookies.content.toString(),/fixture-session-only/);assert.doesNotMatch(cookies.content.toString(),/remove-this-fixture/);assert.doesNotMatch(JSON.stringify(start.body),/fixture-session-only/);assert.doesNotMatch(uploaded.find(f=>f.path.endsWith('config.json')).content.toString(),/fixture-session-only/);
    assert.equal(verify(start.body.ticket,process.env.MEDIAFLOW_SIGNING_SECRET).name.startsWith('mediaflow-download-'),true);
  }finally{
    list.mock.restore();create.mock.restore();
    for(const [name,value] of [['MEDIAFLOW_SIGNING_SECRET',previous.secret],['MEDIAFLOW_SNAPSHOT_ID',previous.snapshot]])if(value===undefined)delete process.env[name];else process.env[name]=value;
  }
});


test('session validation rejects unrelated, malformed and oversized files',()=>{
  assert.equal(youtubeCookies(undefined),null);
  assert.throws(()=>youtubeCookies('x'.repeat(262145)));
  assert.throws(()=>youtubeCookies('.youtube.com.evil.test\tTRUE\t/\tTRUE\t0\tSID\tfixture'));
  assert.throws(()=>youtubeCookies('not cookies format'));
  assert.throws(()=>youtubeCookies('.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tbad\x00value'));
  assert.match(youtubeCookies('#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tfixture'),/#HttpOnly_\.youtube.com/);
});
