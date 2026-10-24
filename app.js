'use strict';
const $ = id => document.getElementById(id);
const local = ['localhost', '127.0.0.1'].includes(location.hostname);
const base = local ? location.origin : 'http://127.0.0.1:3000';
let token = window.MEDIAFLOW_LOCAL?.token || sessionStorage.getItem('mediaflow-key') || '';
let currentJob, timer;
async function api(path, method = 'GET', body) {
  const response = await fetch(base + path, {
    method, headers: {Authorization: `Bearer ${token}`, ...(body ? {'Content-Type':'application/json'} : {})},
    ...(body ? {body: JSON.stringify(body)} : {}), signal: AbortSignal.timeout(path === '/api/folder' ? 125000 : 15000)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The engine could not complete this request.');
  return data;
}
function showError(message) { $('error').textContent = message; $('error').hidden = false; }
async function connect() {
  try {
    const data = await api('/api/health');
    const missing = Object.entries(data.dependencies).filter(([, ok])=> !ok).map(([name])=>name);
    $('connection').textContent = missing.length ? 'Dependencies missing' : 'Mac engine connected';
    $('connection').classList.toggle('connected', !missing.length);
    if (!$('destination').value) $('destination').value = data.defaultDestination;
    $('setupMessage').textContent = missing.length ? `Install missing dependencies: ${missing.join(', ')}.` : 'Connected. Downloads save directly to your Mac.';
    $('setup').open = !!missing.length;
    sessionStorage.setItem('mediaflow-key', token);
    return !missing.length;
  } catch {
    $('connection').textContent = 'Engine disconnected';
    $('connection').classList.remove('connected');
    $('setup').open = true;
    $('setupMessage').textContent = 'Start the engine on this Mac and enter its connection key. Your browser may ask permission to access your local network.';
    return false;
  }
}
$('connect').onclick = () => {token = $('key').value.trim(); connect();};
$('url').oninput = () => {
  let spotify = false;
  try {spotify = new URL($('url').value).hostname === 'open.spotify.com';} catch {}
  const video = $('format').querySelector('[value="mp4"]');
  video.disabled = spotify;
  if (spotify && $('format').value === 'mp4') $('format').value = 'mp3';
  $('playlist').disabled = spotify;
  if (spotify) $('playlist').value = 'yes';
  $('providerHint').textContent = spotify ? 'Spotify tracks are matched with audio on YouTube; matches can differ from the original recording.' : 'Choose one video or the full YouTube playlist. Audio conversion does not improve the source quality.';
};
$('browse').onclick = async () => {
  $('error').hidden = true;
  try {
    const data = await api('/api/folder', 'POST');
    if (data.destination) $('destination').value = data.destination;
  } catch (error) {showError(error.message + ' You can also enter the folder path above.');}
};
$('form').onsubmit = async event => {
  event.preventDefault(); $('error').hidden = true; $('start').disabled = true;
  try {
    if (!await connect()) throw new Error('Connect your Mac engine before downloading. See the instructions below.');
    currentJob = await api('/api/jobs', 'POST', {url: $('url').value.trim(), format: $('format').value, playlist: $('playlist').value === 'yes', destination: $('destination').value.trim()});
    $('form').hidden = true; $('job').hidden = false; render(currentJob); poll();
  } catch (error) {showError(error.message);} finally {$('start').disabled = false;}
};
function render(job) {
  $('jobState').textContent = ({queued:'Queued',running:'Downloading & converting',complete:'Saved to your folder',partial:'Saved with some failures',error:'Download failed',cancelled:'Download cancelled'})[job.state];
  $('count').textContent = job.files.length ? `${job.files.length} files` : '';
  $('message').textContent = job.message;
  $('savedFolder').textContent = job.destination;
  $('logs').textContent = job.log.join('\n');
  const active = ['queued','running'].includes(job.state);
  $('cancel').hidden = !active; $('another').hidden = active;
  $('archive').hidden = !job.archiveReady;
  if (active) $('progress').removeAttribute('value'); else {$('progress').max = 1; $('progress').value = job.state === 'complete' ? 1 : 0;}
}
async function poll() {
  try {
    currentJob = await api(`/api/jobs/${currentJob.id}`); render(currentJob);
    if (['queued','running'].includes(currentJob.state) || (['complete','partial'].includes(currentJob.state) && !currentJob.archiveReady)) timer = setTimeout(poll, 1500);
  } catch (error) {
    $('message').textContent = 'Connection interrupted. Reconnecting to your Mac…'; timer = setTimeout(poll, 4000);
  }
}
$('cancel').onclick = async () => {
  try {currentJob = await api(`/api/jobs/${currentJob.id}/cancel`, 'POST'); clearTimeout(timer); render(currentJob);} catch(error) {$('message').textContent = error.message;}
};
$('another').onclick = () => {clearTimeout(timer); $('job').hidden = true; $('form').hidden = false;};
$('archive').onclick = async () => {
  $('archive').disabled = true;
  try {
    const response = await fetch(`${base}/api/jobs/${currentJob.id}/archive`, {headers:{Authorization:`Bearer ${token}`}});
    if (!response.ok) throw new Error('Could not save archive. Your media files are already in the destination folder.');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = 'MediaFlow-playlist.zip'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),60000);
  } catch(error) {$('message').textContent = error.message;} finally {$('archive').disabled = false;}
};
if (token) connect(); else $('setup').open = true;
