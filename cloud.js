'use strict';
const $=id=>document.getElementById(id);
let job,folder,targetFolder,timer,failures=0,saving=false;
const savedFiles=new Set();
const restored=sessionStorage.getItem('mediaflow-cloud-job');
try {if(restored)job=JSON.parse(restored);}catch{}
async function api(body) {
  const response=await fetch('/api/jobs',{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(125000)});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Cloud connection failed.');return data;
}
async function selectedSession(){const file=$('youtubeCookies').files?.[0];if(!file)return undefined;if(file.size>262144)throw new Error('Choose a cookies.txt file smaller than 256 KB.');const text=await file.text();if(!text.trim())throw new Error('The session file is empty. Choose a YouTube cookies.txt export.');return text;}
$('youtubeCookies').onchange=()=>{$('sessionStatus').textContent=$('youtubeCookies').files?.[0]?'Session selected for this download only.':'No session selected.';};
function error(message){$('error').textContent=message;$('error').hidden=false;}
async function connect(){try{await api();$('connection').textContent='Cloud connected';$('connection').classList.add('connected');return true;}catch(e){$('connection').textContent='Cloud unavailable';error(e.message);return false;}}
$('browse').onclick=async()=>{
  if(!window.showDirectoryPicker){$('destinationHint').textContent='This browser can save each song using its link as soon as it is ready. Open Chrome or Edge to save songs automatically to a chosen folder.';return;}
  try{folder=await window.showDirectoryPicker({mode:'readwrite'});$('destination').value=folder.name;$('destinationHint').textContent='Each finished song will save here immediately while the others keep downloading.';}catch(e){if(e.name!=='AbortError')error(e.message);}
};
$('url').oninput=()=>{let spotify=false;try{spotify=new URL($('url').value).hostname==='open.spotify.com';}catch{}$('format').querySelector('[value="mp4"]').disabled=spotify;if(spotify&&$('format').value==='mp4')$('format').value='mp3';$('playlist').disabled=spotify;if(spotify)$('playlist').value='yes';$('providerHint').textContent=spotify?'Spotify tracks are matched with audio on YouTube; matches can differ from the original recording.':'Download one video or a full playlist. Conversion does not improve source quality.';};
$('form').onsubmit=async event=>{
  event.preventDefault();$('error').hidden=true;$('start').disabled=true;
  try{if(!await connect())throw new Error('The cloud downloader is unavailable. Please try again shortly.');const youtubeCookies=await selectedSession();job=await api({youtubeCookies,url:$('url').value.trim(),format:$('format').value,playlist:$('playlist').value==='yes'});targetFolder=null;savedFiles.clear();$('readyFiles').replaceChildren();sessionStorage.setItem('mediaflow-cloud-job',JSON.stringify(job));$('form').hidden=true;$('job').hidden=false;$('jobState').textContent='Starting cloud worker';$('message').textContent='Reading your playlist…';$('another').hidden=true;$('cancel').hidden=false;$('pause').hidden=false;$('pause').textContent='Pause';$('archive').hidden=true;$('saveFolder').hidden=true;$('retrySession').hidden=true;$('progress').removeAttribute('value');failures=0;poll();}catch(e){error(e.message);}finally{$('start').disabled=false;}
};
function workerURL(path){return `${job.domain}/${path}${path.includes('?')?'&':'?'}key=${encodeURIComponent(job.jobKey)}`;}
async function poll(){
  if(Date.now()>job.expiresAt){$('message').textContent='This cloud session has expired. Start a new download.';$('another').hidden=false;$('cancel').hidden=true;return;}
  try{
    const response=await fetch(workerURL('status'),{signal:AbortSignal.timeout(15000)});if(!response.ok)throw new Error('Worker unavailable');const state=await response.json();failures=0;job.state=state;
    $('jobState').textContent=({running:'Downloading',paused:'Paused',finishing:'Finishing',complete:'Ready to save',partial:'Some files ready',cancelled:'Cancelled',error:'Download failed'})[state.state]||state.state;
    $('count').textContent=state.files.length?`${savedFiles.size} saved · ${state.files.length} ready`:'';
    renderFiles(state.files);$('message').textContent=state.message;$('logs').textContent=state.log.join('\n');$('savedFolder').textContent=`Save before ${new Date(job.expiresAt).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}. Files are removed when this cloud session ends.`;
    const active=['running','paused','finishing'].includes(state.state);$('pause').hidden=!['running','paused'].includes(state.state);$('pause').textContent=state.state==='paused'?'Resume':'Pause';const needsSession=['YOUTUBE_AUTH_REQUIRED','SOURCE_UNAVAILABLE'].includes(state.errorCode)||/sign in to confirm|YT-DLP download error|provider may require sign-in/i.test([state.message,...state.log].join('\n'));$('retrySession').hidden=active||!needsSession;$('another').hidden=active;$('cancel').hidden=!['running','paused'].includes(state.state);$('archive').hidden=!state.archiveReady;$('saveFolder').hidden=!state.files.length||!window.showDirectoryPicker;
    if(folder&&state.files.some(file=>!savedFiles.has(file.name)))await saveToFolder();
    if(!active){$('progress').max=1;$('progress').value=state.state==='complete'?1:0;return;}
  }catch(e){failures++;$('message').textContent=failures<5?'Waiting for the cloud worker…':'The cloud worker is not responding. You can cancel and start again.';if(failures>=5){$('another').hidden=false;return;}}
  timer=setTimeout(poll,2000);
}
async function stop(){if(job){await api({action:'cancel',ticket:job.ticket});sessionStorage.removeItem('mediaflow-cloud-job');job=null;}}
async function workerControl(action){
  const response=await fetch(workerURL('control'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action}),signal:AbortSignal.timeout(15000)});
  const state=await response.json();if(!response.ok)throw new Error(state.error||'Could not update the download.');job.state=state;return state;
}
$('pause').onclick=async()=>{try{const state=await workerControl(job.state?.state==='paused'?'resume':'pause');$('pause').textContent=state.state==='paused'?'Resume':'Pause';$('message').textContent=state.message;$('jobState').textContent=state.state==='paused'?'Paused':'Downloading';}catch(e){$('message').textContent=e.message;}};
$('cancel').onclick=async()=>{try{await workerControl('cancel');clearTimeout(timer);$('jobState').textContent='Cancelled';$('message').textContent='Download cancelled. Songs already saved remain in your folder.';$('cancel').hidden=true;$('pause').hidden=true;$('another').hidden=false;await poll();}catch(e){$('message').textContent=e.message;}};
$('retrySession').onclick=async()=>{try{await stop();clearTimeout(timer);$('job').hidden=true;$('form').hidden=false;$('youtubeSession').open=true;$('sessionStatus').textContent='Choose your signed-in YouTube cookies.txt file, then start again.';$('youtubeCookies').focus();}catch(e){$('message').textContent=e.message;}};
$('another').onclick=async()=>{try{await stop();clearTimeout(timer);$('job').hidden=true;$('form').hidden=false;}catch(e){$('message').textContent=e.message;}};
function renderFiles(files){
  const list=$('readyFiles');list.replaceChildren();
  for(const file of files){
    const row=document.createElement('p');row.className='hint';
    const link=document.createElement('a');link.textContent=(savedFiles.has(file.name)?'✓ Saved: ':'↓ Save song: ')+file.name;link.href=workerURL('file?name='+encodeURIComponent(file.name));link.download=file.name;link.rel='noreferrer';link.style.color='#c4f3cf';row.append(link);list.append(row);
  }
}
async function saveToFolder(){
  if(saving)return;
  saving=true;const currentJob=job;
  try{if(!folder)folder=await window.showDirectoryPicker({mode:'readwrite'});
    if(!targetFolder)targetFolder=await folder.getDirectoryHandle('MediaFlow-'+new Date().toISOString().replace(/[:.]/g,'-'),{create:true});$('saveFolder').disabled=true;
    for(const file of currentJob.state.files){
      if(savedFiles.has(file.name)||job!==currentJob)continue;
      $('message').textContent=`Saving ${file.name}…`;
      const response=await fetch(workerURL('file?name='+encodeURIComponent(file.name)));if(!response.ok)throw new Error('File is unavailable. The cloud session may have expired.');
      const handle=await targetFolder.getFileHandle(file.name.replace(/[\x00-\x1f/\\]/g,'_'),{create:true});const output=await handle.createWritable();await response.body.pipeTo(output);savedFiles.add(file.name);renderFiles(currentJob.state.files);
    }
    $('count').textContent=`${savedFiles.size} saved · ${currentJob.state.files.length} ready`;
    $('message').textContent=`Saved ${savedFiles.size} songs to ${folder.name}.`+(currentJob.state.state==='paused'?' Download paused.':['running','finishing'].includes(currentJob.state.state)?' The remaining songs are still processing.':'');
  }catch(e){if(e.name!=='AbortError')$('message').textContent=e.message;}finally{saving=false;$('saveFolder').disabled=false;}
}
$('saveFolder').onclick=saveToFolder;
$('archive').onclick=async()=>{
  try{if(window.showSaveFilePicker){const handle=await window.showSaveFilePicker({suggestedName:'MediaFlow-playlist.zip',types:[{description:'ZIP archive',accept:{'application/zip':['.zip']}}]});const response=await fetch(workerURL('archive'));if(!response.ok)throw new Error('Archive unavailable.');await response.body.pipeTo(await handle.createWritable());$('message').textContent='ZIP saved successfully.';}else{const link=document.createElement('a');link.href=workerURL('archive');link.download='MediaFlow-playlist.zip';link.rel='noreferrer';link.click();$('message').textContent='ZIP download started. Choose the save location in your browser.';}}catch(e){if(e.name!=='AbortError')$('message').textContent=e.message;}
};
connect();if(job&&job.expiresAt>Date.now()){$('form').hidden=true;$('job').hidden=false;poll();}
