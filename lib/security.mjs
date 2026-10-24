import {createHmac,timingSafeEqual} from 'node:crypto';
export function sign(data,key){const body=Buffer.from(JSON.stringify(data)).toString('base64url');return body+'.'+createHmac('sha256',key).update(body).digest('base64url');}
export function verify(ticket,key){
 if(typeof ticket!=='string'||ticket.length>2048)throw new Error('Invalid session ticket.');
 const parts=ticket.split('.');if(parts.length!==2)throw new Error('Invalid session ticket.');
 const [body,mac]=parts,expected=createHmac('sha256',key).update(body).digest('base64url');
 if(mac.length!==expected.length||!timingSafeEqual(Buffer.from(mac),Buffer.from(expected)))throw new Error('Invalid session ticket.');
 const data=JSON.parse(Buffer.from(body,'base64url').toString());
 if(data.p!=='cancel'||!/^mediaflow-download-v2-[a-f0-9]{24}$/.test(data.name)||typeof data.owner!=='string'||data.owner.length!==32||!Number.isFinite(data.exp)||data.exp<Date.now())throw new Error('This session has expired.');
 return data;
}
export function validate(input){
 if(!input||typeof input!=='object'||Array.isArray(input))throw new Error('Paste a supported media link.');
 for(const field of ['youtubeCookies','cookies','password'])if(input[field]!=null)throw new Error('Account credentials and cookie files are not accepted.');
 if(typeof input.url!=='string'||input.url.length>2048)throw new Error('Paste a supported media link.');
 let url;try{url=new URL(input.url);}catch{throw new Error('Paste a valid YouTube or Spotify link.');}
 if(url.protocol!=='https:'||url.username||url.password||url.port||url.hash)throw new Error('Use a supported HTTPS media link.');
 let provider;
 if(url.hostname==='open.spotify.com'){
  if(!/^\/(?:intl-[a-z]{2}\/)?(?:album|playlist|track)\/[A-Za-z0-9]{22}\/?$/.test(url.pathname))throw new Error('Use a Spotify album, playlist or track link.');
  url.search='';provider='spotify';
 }else if(['youtube.com','www.youtube.com','music.youtube.com','youtu.be'].includes(url.hostname)){
  const id=/^[A-Za-z0-9_-]{11}$/;let video;
  if(url.hostname==='youtu.be'&&id.test(url.pathname.slice(1)))video=url.pathname.slice(1);
  else if(url.pathname==='/watch'&&url.searchParams.getAll('v').length===1&&id.test(url.searchParams.get('v')))video=url.searchParams.get('v');
  else if(/^\/(shorts|live)\/[A-Za-z0-9_-]{11}\/?$/.test(url.pathname))video=url.pathname.split('/')[2];
  else if(url.hostname!=='youtu.be'&&url.pathname==='/playlist')video=null;
  else throw new Error('Use a YouTube video or playlist link. Redirect and channel links are not supported.');
  const list=url.searchParams.getAll('list');if(list.length>1||(list.length&&!/^[A-Za-z0-9_-]{10,120}$/.test(list[0])))throw new Error('Use a valid YouTube playlist link.');
  if(!video&&!list.length)throw new Error('Use a YouTube video or playlist link.');
  url=new URL('https://www.youtube.com/'+(video?'watch':'playlist'));if(video)url.searchParams.set('v',video);if(list.length)url.searchParams.set('list',list[0]);provider='youtube';
 }else throw new Error('Only YouTube and Spotify links are supported.');
 if(!['mp3','m4a','flac','mp4'].includes(input.format)||(provider==='spotify'&&input.format==='mp4'))throw new Error('Choose a supported format. Spotify supports audio formats.');
 return {url:url.href,provider,format:input.format,playlist:input.playlist!==false};
}
