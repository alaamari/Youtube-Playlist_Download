import {createHmac, timingSafeEqual} from 'node:crypto';
export function equal(a,b) {const x=Buffer.from(a||''),y=Buffer.from(b||'');return x.length===y.length && timingSafeEqual(x,y);}
export function sign(data,key) {const body=Buffer.from(JSON.stringify(data)).toString('base64url'); return body+'.'+createHmac('sha256',key).update(body).digest('base64url');}
export function verify(ticket,key) {const [body,mac]=String(ticket||'').split('.');if(!body||!equal(mac,createHmac('sha256',key).update(body).digest('base64url')))throw new Error('Invalid job ticket.');const data=JSON.parse(Buffer.from(body,'base64url').toString());if(data.exp<Date.now())throw new Error('This download session has expired. Start a new download.');return data;}
export function validate(input) {
  let url;try{url=new URL(input.url);}catch{throw new Error('Paste a valid YouTube or Spotify URL.');}
  if(url.protocol!=='https:'||url.username||url.password||url.port)throw new Error('Use an HTTPS YouTube or Spotify URL.');
  const provider=url.hostname==='open.spotify.com'?'spotify':['youtube.com','www.youtube.com','music.youtube.com','youtu.be'].includes(url.hostname)?'youtube':null;
  if(!provider)throw new Error('Only YouTube and Spotify links are supported.');
  if(provider==='spotify'&&!/^\/(?:intl-[a-z]{2}\/)?(?:playlist|album|track)\/[A-Za-z0-9]{22}\/?$/.test(url.pathname))throw new Error('Use a Spotify playlist, album, or track link.');
  if(!['mp3','mp4','flac','m4a'].includes(input.format)||(provider==='spotify'&&input.format==='mp4'))throw new Error('Choose a supported format. Spotify supports audio formats.');
  return {url:url.href,provider,format:input.format,playlist:input.playlist!==false};
}

export function youtubeCookies(value){
  if(value==null||value==='')return null;
  if(typeof value!=='string'||Buffer.byteLength(value,'utf8')>262144)throw new Error('Session file must be a cookies.txt file smaller than 256 KB.');
  const rows=[];
  for(const line of value.replace(/\r\n?/g,'\n').split('\n')){
    if(!line.trim()||(line.startsWith('#')&&!line.startsWith('#HttpOnly_')))continue;
    const raw=line.startsWith('#HttpOnly_')?line.slice(10):line;
    const fields=raw.split('\t');
    if(fields.length!==7)throw new Error('Session file must use Netscape cookies.txt format.');
    const [domain,subdomains,path,secure,expires,name,cookie]=fields;
    const host=domain.replace(/^\./,'').toLowerCase();
    if(host!=='youtube.com'&&!host.endsWith('.youtube.com'))continue;
    if(!/^(TRUE|FALSE)$/.test(subdomains)||!path.startsWith('/')||!/^(TRUE|FALSE)$/.test(secure)||!/^\d+$/.test(expires)||!name||/[\x00-\x1f\x7f]/.test(raw.replaceAll('\t',''))||name.includes('='))throw new Error('The YouTube session file contains an invalid cookie.');
    rows.push((line.startsWith('#HttpOnly_')?'#HttpOnly_':'')+fields.join('\t'));
    if(rows.length>1000)throw new Error('The session file contains too many cookies.');
  }
  if(!rows.length)throw new Error('No YouTube cookies were found. Export youtube.com cookies from your signed-in browser.');
  return '# Netscape HTTP Cookie File\n'+rows.join('\n')+'\n';
}
