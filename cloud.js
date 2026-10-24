'use strict';
const $=id=>document.getElementById(id);
let job,folder,timer,failures=0;
const restored=sessionStorage.getItem('mediaflow-cloud-job');
try {if(restored)job=JSON.parse(restored);}catch{}
async function api(body) {
  const response=await fetch('/api/jobs',{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(125000)});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Cloud connection failed.');return data;
}
function error(message){$('error').textContent=message;$('error').hidden=false;}
async function connect(){try{await api();$('connection').textContent='Cloud connected';$('connection').classList.add('connected');return true;}catch(e){$('connection').textContent='Cloud unavailable';error(e.message);return false;}}
$('browse').onclick=async()=>{
  if(!window.showDirectoryPicker){$('destinationHint').textContent='This browser will save a ZIP after conversion. To choose a folder and save individual tracks, open this page in Chrome or Edge.';return;}
  try{folder=await window.showDirectoryPicker({mode:'readwrite'});$('destination').value=folder.name;$('destinationHint').textContent='Files will save automatically to a new MediaFlow subfolder after conversion.';}catch(e){if(e.name!=='AbortError')error(e.message);}
};
$('url').oninput=()=>{let spotify=false;try{spotify=new URL($('url').value).hostname==='open.spotify.com';}catch{}$('format').querySelector('[value="mp4"]').disabled=spotify;if(spotify&&$('format').value==='mp4')$('format').value='mp3';$('playlist').disabled=spotify;if(spotify)$('playlist').value='yes';$('providerHint').textContent=spotify?'Spotify tracks are matched with audio on YouTube; matches can differ from the original recording.':'Download one video or a full playlist. Conversion does not improve source quality.';};
$('form').onsubmit=async event=>{
  event.preventDefault();$('error').hidden=true;$('start').disabled=true;
  try{if(!await connect())throw new Error('The cloud downloader is unavailable. Please try again shortly.');job=await api({url:$('url').value.trim(),format:$('format').value,playlist:$('playlist').value==='yes'});sessionStorage.setItem('mediaflow-cloud-job',JSON.stringify(job));$('form').hidden=true;$('job').hidden=false;$('jobState').textContent='Starting cloud worker';$('message').textContent='Reading your playlist…';$('another').hidden=true;$('cancel').hidden=false;$('archive').hidden=true;$('saveFolder').hidden=true;$('progress').removeAttribute('value');failures=0;poll();}catch(e){error(e.message);}finally{$('start').disabled=false;}
};
function workerURL(path){return `${job.domain}/${path}${path.includes('?')?'&':'?'}key=${encodeURIComponent(job.jobKey)}`;}
async function poll(){
  if(Date.now()>job.expiresAt){$('message').textContent='This cloud session has expired. Start a new download.';$('another').hidden=false;$('cancel').hidden=true;return;}
  try{
    const response=await fetch(workerURL('status'),{signal:AbortSignal.timeout(15000)});if(!response.ok)throw new Error('Worker unavailable');const state=await response.json();failures=0;job.state=state;
    $('jobState').textContent=({running:'Downloading & converting',complete:'Ready to save',partial:'Some files ready',error:'Download failed'})[state.state]||state.state;
    $('count').textContent=state.files.length?`${state.files.length} files`:'';$('message').textContent=state.message;$('logs').textContent=state.log.join('\n');$('savedFolder').textContent=`Save before ${new Date(job.expiresAt).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}. Files are removed when this cloud session ends.`;
    const active=state.state==='running';$('another').hidden=active;$('cancel').hidden=!active;$('archive').hidden=!state.archiveReady;$('saveFolder').hidden=!state.archiveReady||!window.showDirectoryPicker;
    if(!active){$('progress').max=1;$('progress').value=state.state==='complete'?1:0;if(state.archiveReady&&folder&&!job.autoSaved){job.autoSaved=true;await saveToFolder();}return;}
  }catch(e){failures++;$('message').textContent=failures<5?'Waiting for the cloud worker…':'The cloud worker is not responding. You can cancel and start again.';if(failures>=5){$('another').hidden=false;return;}}
  timer=setTimeout(poll,2000);
}
async function stop(){if(job){await api({action:'cancel',ticket:job.ticket});sessionStorage.removeItem('mediaflow-cloud-job');job=null;}}
$('cancel').onclick=async()=>{try{await stop();clearTimeout(timer);$('jobState').textContent='Cancelled';$('message').textContent='Cloud worker stopped.';$('cancel').hidden=true;$('another').hidden=false;}catch(e){$('message').textContent=e.message;}};
$('another').onclick=async()=>{try{await stop();clearTimeout(timer);$('job').hidden=true;$('form').hidden=false;}catch(e){$('message').textContent=e.message;}};
async function saveToFolder(){
  try{if(!folder)folder=await window.showDirectoryPicker({mode:'readwrite'});const target=await folder.getDirectoryHandle('MediaFlow-'+new Date().toISOString().replace(/[:.]/g,'-'),{create:true});$('saveFolder').disabled=true;
    for(const file of job.state.files){$('message').textContent=`Saving ${file.name}…`;const response=await fetch(workerURL('file?name='+encodeURIComponent(file.name)));if(!response.ok)throw new Error('File is unavailable. The cloud session may have expired.');const handle=await target.getFileHandle(file.name.replace(/[\x00-\x1f/\\]/g,'_'),{create:true});const output=await handle.createWritable();await response.body.pipeTo(output);}
    $('message').textContent=`Saved ${job.state.files.length} files to ${folder.name}.`;
  }catch(e){if(e.name!=='AbortError')$('message').textContent=e.message;}finally{$('saveFolder').disabled=false;}
}
$('saveFolder').onclick=saveToFolder;
$('archive').onclick=async()=>{
  try{if(window.showSaveFilePicker){const handle=await window.showSaveFilePicker({suggestedName:'MediaFlow-playlist.zip',types:[{description:'ZIP archive',accept:{'application/zip':['.zip']}}]});const response=await fetch(workerURL('archive'));if(!response.ok)throw new Error('Archive unavailable.');await response.body.pipeTo(await handle.createWritable());$('message').textContent='ZIP saved successfully.';}else{const link=document.createElement('a');link.href=workerURL('archive');link.download='MediaFlow-playlist.zip';link.rel='noreferrer';link.click();$('message').textContent='ZIP download started. Choose the save location in your browser.';}}catch(e){if(e.name!=='AbortError')$('message').textContent=e.message;}
};
connect();if(job&&job.expiresAt>Date.now()){$('form').hidden=true;$('job').hidden=false;poll();}
