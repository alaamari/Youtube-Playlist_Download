import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
test('each ready song saves during processing exactly once; controls use headers, not URL credentials',async()=>{
 const elements=new Map(),saved=[],requests=[];
 function element(){return {style:{},classList:{add(){}},replaceChildren(){},append(){},removeAttribute(){},querySelector(){return element();}};}
 const directory={name:'Chosen folder',async getFileHandle(name){return {async createWritable(){return {name};}};}};
 let files=[{name:'first.mp3',token:'first-file-token'}],state='running';
 const context=vm.createContext({console,Date,Set,URL,Headers,AbortSignal,encodeURIComponent,sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}},document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element},window:{showDirectoryPicker:async()=>directory},setTimeout(){return 1;},clearTimeout(){},directory,
  fetch:async(url,options={})=>{
   requests.push({url,options});
   if(url==='/api/jobs')return {ok:true,json:async()=>({status:'ready',cloudEnabled:true})};
   if(url.includes('/control')){const action=JSON.parse(options.body).action;state=action==='pause'?'paused':action==='resume'?'running':'cancelled';return {ok:true,json:async()=>({state,files,log:[],message:state})};}
   if(url.includes('/status'))return {ok:true,json:async()=>({state,files,log:[],message:'Downloading next song'})};
   return {ok:true,body:{async pipeTo(output){saved.push(output.name);}}};
  }
 });
 let source=await readFile(new URL('../cloud.js',import.meta.url),'utf8');source=source.split('\n').slice(2).join('\n');vm.runInContext(source,context);
 vm.runInContext("folder=directory;job={domain:'https://worker.vercel.run',jobKey:'temporary-control-secret',expiresAt:Date.now()+60000};",context);
 await vm.runInContext('poll()',context);assert.deepEqual(saved,['first.mp3']);
 files=[...files,{name:'second.mp3',token:'second-file-token'}];await vm.runInContext('poll()',context);await vm.runInContext('poll()',context);assert.deepEqual(saved,['first.mp3','second.mp3']);
 await vm.runInContext("$('pause').onclick()",context);assert.equal(state,'paused');await vm.runInContext("$('pause').onclick()",context);assert.equal(state,'running');
 const privateRequests=requests.filter(r=>r.url.includes('/status')||r.url.includes('/control'));
 assert.ok(privateRequests.every(r=>r.options.headers.Authorization==='Bearer temporary-control-secret'&&!r.url.includes('key=')));
 assert.ok(requests.filter(r=>r.url.includes('/file')).every(r=>r.url.includes('token=')&&!r.url.includes('temporary-control-secret')));
});
