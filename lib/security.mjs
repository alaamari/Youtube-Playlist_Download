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
