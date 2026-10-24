import {initBotId} from 'botid/client/core';
initBotId({protect:[{path:'/api/jobs',method:'POST',advancedOptions:{checkLevel:'basic'}},{path:'/api/jobs.mjs',method:'POST',advancedOptions:{checkLevel:'basic'}}]});
const $=id=>document.getElementById(id);
let job,folder,targetFolder,timer,saving=false,failures=0;
const savedFiles=new Set();
function trustedDomain(value){try{const u=new URL(value);return u.protocol==='https:'&&u.hostname.endsWith('.vercel.run')&&!u.username&&!u.password&&!u.port&&u.pathname==='/';}catch{return false;}}
try{const stored=JSON.parse(sessionStorage.getItem('mediaflow-cloud-v2')||'null');if(stored&&trustedDomain(stored.domain)&&stored.expiresAt>Date.now()&&typeof stored.jobKey==='string')job=stored;}catch{}
sessionStorage.removeItem('mediaflow-cloud-job');
async function api(body){
 const response=await fetch('/api/jobs',{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(125000)});
 let data;try{data=await response.json();}catch{throw new Error('The cloud connection did not respond. Please reload and try again.');}
 if(!response.ok)throw new Error(data.error||'Cloud connection failed.');return data;
}
function error(message){$('error').textContent=message;$('error').hidden=false;}
async function connect(){try{const health=await api();if(!health.cloudEnabled)throw new Error('The cloud service is unavailable. Please try again shortly.');$('connection').textContent='Cloud connected';$('connection').classList.add('connected');return true;}catch(e){$('connection').textContent='Cloud unavailable';error(e.message);return false;}}
$('browse').onclick=async()=>{
 if(!window.showDirectoryPicker){$('destinationHint').textContent='This browser saves each song using its link when ready. Chrome or Edge can save songs automatically to a chosen folder.';return;}
 try{folder=await window.showDirectoryPicker({mode:'readwrite'});$('destination').value=folder.name;$('destinationHint').textContent='Each finished song saves here while the remaining songs keep downloading.';}catch(e){if(e.name!=='AbortError')error(e.message);}
};
$('url').oninput=()=>{let spotify=false;try{spotify=new URL($('url').value).hostname==='open.spotify.com';}catch{}$('format').querySelector('[value="mp4"]').disabled=spotify;if(spotify&&$('format').value==='mp4')$('format').value='mp3';$('playlist').disabled=spotify;if(spotify)$('playlist').value='yes';$('providerHint').textContent=spotify?'Spotify supplies the track list. Matching audio comes from Bandcamp first, then YouTube. Each song is ready separately.':'Download one video or up to 20 playlist items. Converting a format does not improve source quality.';};
$('form').onsubmit=async event=>{
 event.preventDefault();$('error').hidden=true;$('start').disabled=true;$('start').textContent='Starting…';
 try{
  if(!await connect())return;
  const next=await api({url:$('url').value.trim(),format:$('format').value,playlist:$('playlist').value==='yes'});
  if(!trustedDomain(next.domain))throw new Error('The cloud returned an invalid session. Please try again.');
  job=next;targetFolder=null;savedFiles.clear();$('readyFiles').replaceChildren();sessionStorage.setItem('mediaflow-cloud-v2',JSON.stringify(job));
  $('form').hidden=true;$('job').hidden=false;$('jobState').textContent='Starting cloud worker';$('message').textContent='Reading your selection…';$('another').hidden=true;$('cancel').hidden=false;$('pause').hidden=false;$('pause').textContent='Pause';$('saveFolder').hidden=true;$('progress').removeAttribute('value');failures=0;poll();
 }catch(e){error(e.message);}finally{$('start').disabled=false;$('start').textContent='Download';}
};
function workerURL(path){if(!job||!trustedDomain(job.domain))throw new Error('Invalid session.');return job.domain.replace(/\/$/,'')+'/'+path;}
function workerFetch(path,options={}){return fetch(workerURL(path),{...options,headers:{...options.headers,Authorization:'Bearer '+job.jobKey}});}
function fileURL(file){return workerURL('file?name='+encodeURIComponent(file.name)+'&token='+encodeURIComponent(file.token));}
async function poll(){
 if(!job||job.ended)return;
 if(Date.now()>job.expiresAt){$('message').textContent='This session has expired. Files already saved stay in your folder.';$('another').hidden=false;$('cancel').hidden=true;$('pause').hidden=true;sessionStorage.removeItem('mediaflow-cloud-v2');return;}
 try{
  const response=await workerFetch('status',{signal:AbortSignal.timeout(15000)});if(!response.ok)throw new Error('Worker unavailable');
  const state=await response.json();if(!Array.isArray(state.files)||!Array.isArray(state.log))throw new Error('Invalid worker response');job.state=state;failures=0;
  $('jobState').textContent=({running:'Downloading',paused:'Paused',complete:'Ready to save',partial:'Some files ready',cancelled:'Cancelled',error:'Download failed'})[state.state]||state.state;
  $('count').textContent=state.files.length?`${savedFiles.size} saved · ${state.files.length} ready`:'';
  renderFiles(state.files);$('message').textContent=state.message;$('logs').textContent=state.log.join('\n');
  $('savedFolder').textContent=`Save before ${new Date(job.expiresAt).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}. Temporary cloud files are removed when the session ends.`;
  const active=['running','paused'].includes(state.state);$('pause').hidden=!active;$('pause').textContent=state.state==='paused'?'Resume':'Pause';$('another').hidden=active;$('cancel').hidden=!active;$('saveFolder').hidden=!state.files.length||!window.showDirectoryPicker;
  if(folder&&state.files.some(file=>!savedFiles.has(file.name)))await saveToFolder();
  if(!active){$('progress').max=1;$('progress').value=state.state==='complete'?1:0;return;}
 }catch(e){failures++;$('message').textContent=failures<5?'Waiting for the cloud worker…':'The cloud worker is not responding. End this session and try again.';if(failures>=5){$('another').hidden=false;return;}}
 timer=setTimeout(poll,2000);
}
async function stop(){if(job&&!job.ended){await api({action:'cancel',ticket:job.ticket});job.ended=true;sessionStorage.removeItem('mediaflow-cloud-v2');}}
async function workerControl(action){
 const response=await workerFetch('control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action}),signal:AbortSignal.timeout(15000)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not update the download.');job.state=data;return data;
}
$('pause').onclick=async()=>{try{const state=await workerControl(job.state?.state==='paused'?'resume':'pause');$('pause').textContent=state.state==='paused'?'Resume':'Pause';$('message').textContent=state.message;$('jobState').textContent=state.state==='paused'?'Paused':'Downloading';}catch(e){$('message').textContent=e.message;}};
$('cancel').onclick=async()=>{try{await workerControl('cancel');clearTimeout(timer);$('pause').hidden=true;$('cancel').hidden=true;$('another').hidden=false;await poll();}catch(e){$('message').textContent=e.message;}};
$('another').onclick=async()=>{try{await stop();clearTimeout(timer);job=null;$('job').hidden=true;$('form').hidden=false;}catch(e){$('message').textContent=e.message;}};
function renderFiles(files){
 const list=$('readyFiles');list.replaceChildren();
 for(const file of files){const row=document.createElement('p');row.className='hint';
  if(savedFiles.has(file.name)){row.textContent='✓ Saved: '+file.name;}
  else{const link=document.createElement('a');link.textContent='↓ Save song: '+file.name;link.href=fileURL(file);link.download=file.name;link.rel='noreferrer';row.append(link);}
  list.append(row);
 }
}
async function saveToFolder(){
 if(saving||!job||job.ended)return;
 saving=true;const current=job;
 try{
  if(!folder)folder=await window.showDirectoryPicker({mode:'readwrite'});if(!targetFolder)targetFolder=folder;$('saveFolder').disabled=true;
  for(const file of current.state.files){
   if(savedFiles.has(file.name)||job!==current)continue;
   $('message').textContent=`Saving ${file.name}…`;
   const response=await fetch(fileURL(file));if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error||'This file is unavailable. The session may have expired.');}
   const handle=await targetFolder.getFileHandle(file.name.replace(/[\x00-\x1f/\\]/g,'_'),{create:true});const output=await handle.createWritable();await response.body.pipeTo(output);savedFiles.add(file.name);renderFiles(current.state.files);
  }
  $('count').textContent=`${savedFiles.size} saved · ${current.state.files.length} ready`;
  $('message').textContent=`Saved ${savedFiles.size} songs to ${folder.name}.`+(['running','paused'].includes(current.state.state)?' The session is still open.':'');
  if(!['running','paused'].includes(current.state.state)&&current.state.files.length&&current.state.files.every(file=>savedFiles.has(file.name))){await stop();$('savedFolder').textContent='Cloud session closed. Your saved files remain in your folder.';$('another').textContent='Download another';}
 }catch(e){if(e.name!=='AbortError')$('message').textContent=e.message;}finally{saving=false;$('saveFolder').disabled=false;}
}
$('saveFolder').onclick=saveToFolder;
connect();if(job){$('form').hidden=true;$('job').hidden=false;poll();}
