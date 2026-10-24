import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

test('poll saves each ready song during processing without downloading it twice',async()=>{
  const elements=new Map(),saved=[],folders=[];
  function element(){return {style:{},classList:{add(){}},replaceChildren(){},append(){},removeAttribute(){},querySelector(){return element();}};}
  const directory={name:'Chosen folder',async getDirectoryHandle(name){folders.push(name);return this;},async getFileHandle(name){return {async createWritable(){return {name};}};}};
  let files=[{name:'first.mp3'}];
  const context=vm.createContext({console,Date,Set,URL,AbortSignal,encodeURIComponent,sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}},document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element},window:{showDirectoryPicker:async()=>directory},setTimeout(){return 1;},clearTimeout(){},directory,
    fetch:async url=>url==='/api/jobs'?{ok:true,json:async()=>({status:'ready'})}:url.includes('/status?')?{ok:true,json:async()=>({state:'running',files,log:[],message:'Downloading next song',archiveReady:false})}:{ok:true,body:{async pipeTo(output){saved.push(output.name);}}}
  });
  vm.runInContext(await readFile(new URL('../cloud.js',import.meta.url),'utf8'),context);
  vm.runInContext("folder=directory;job={domain:'https://worker.test',jobKey:'test',expiresAt:Date.now()+60000};",context);
  await vm.runInContext('poll()',context);
  assert.deepEqual(saved,['first.mp3']);
  files=[{name:'first.mp3'},{name:'second.mp3'}];
  await vm.runInContext('poll()',context);
  await vm.runInContext('poll()',context);
  assert.deepEqual(saved,['first.mp3','second.mp3']);
  assert.equal(folders.length,1);
});
