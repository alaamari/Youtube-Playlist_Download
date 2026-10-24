import {Sandbox} from '@vercel/sandbox';
import {checkBotId} from 'botid/server';
import {readFile} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
import {validate,sign,verify} from '../lib/security.mjs';
import {reserve,release,redisCommand,AdmissionError,SESSION_MS,LEASE_MS} from '../lib/admission.mjs';
export const config={maxDuration:120};
const ORIGINS=new Set(['https://youtube-playlist-download.vercel.app','https://youtube-playlist-download-alaa12.vercel.app']);
const NETWORK={allow:['spotify.com','*.spotify.com','*.scdn.co','*.spotifycdn.com','*.spotifycdn.net','bandcamp.com','*.bandcamp.com','*.bcbits.com','youtube.com','*.youtube.com','youtu.be','*.googlevideo.com','*.ytimg.com','*.ggpht.com','*.google.com','*.googleapis.com'],subnets:{deny:['0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8','169.254.0.0/16','172.16.0.0/12','192.168.0.0/16','224.0.0.0/4','::/128','::1/128','fc00::/7','fe80::/10']}};
export function createHandler({Worker=Sandbox,botCheck=checkBotId,admit=reserve,free=release,command=redisCommand}={}){
 return async function handler(req,res){
  res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Allow','GET, POST');
  // Use the existing owner-approved Hobby snapshot to avoid new persistent storage.
  const secret=process.env.MEDIAFLOW_SIGNING_SECRET,snapshotId=process.env.MEDIAFLOW_SNAPSHOT_ID;
  if(!secret||!snapshotId||!process.env.KV_REST_API_URL||!process.env.KV_REST_API_TOKEN)return res.status(503).json({error:'Cloud configuration is updating. Please try again shortly.'});
  if(req.method==='GET'){
   try{if(await command('PING')!=='PONG')throw new Error('Unavailable');return res.status(200).json({status:'ready',mode:'cloud',cloudEnabled:true,limits:{songs:20,fileMiB:64,totalMiB:256,sessionMinutes:20,sharedSessionsPer30Days:10,sessionsPerConnectionPerDay:3}});}
   catch{return res.status(503).json({error:'Cloud limits are temporarily unavailable. Please try again later.'});}
  }
  if(req.method!=='POST')return res.status(405).json({error:'Use POST.'});
  if(!ORIGINS.has(req.headers.origin))return res.status(403).json({error:'Start downloads from this website.'});
  if(Number(req.headers['content-length']||0)>4096)return res.status(413).json({error:'Request too large.'});
  let input;try{input=typeof req.body==='string'?JSON.parse(req.body):req.body;if(!input||typeof input!=='object'||JSON.stringify(input).length>4096)throw new Error();}catch{return res.status(400).json({error:'Invalid download request.'});}
  if(input.action==='cancel'){
   let ticket;try{ticket=verify(input.ticket,secret);}catch{return res.status(400).json({error:'The download session has expired or is invalid.'});}
   try{const worker=await Worker.get({name:ticket.name,resume:false});await worker.stop();await free(ticket.owner);return res.status(200).json({state:'cancelled'});}
   catch(error){console.error('Cloud session close:',error.name);return res.status(502).json({error:'The session could not be closed yet. Its automatic expiry still applies; please try again.'});}
  }
  if(input.action!=null&&input.action!=='start')return res.status(400).json({error:'Invalid action.'});
  let params;try{params=validate(input);}catch(error){return res.status(400).json({error:error.message});}
  let worker,owner,name,admitted=false,stage='browser verification';
  try{
   const verification=await botCheck({developmentOptions:{isDevelopment:false},advancedOptions:{checkLevel:'basic',headers:req.headers}});
   if(verification.isBot||!verification.isHuman)return res.status(403).json({error:'Browser verification failed. Reload the page in a regular browser and try again.'});
   owner=randomBytes(24).toString('base64url');name='mediaflow-download-v2-'+randomBytes(12).toString('hex');
   stage='free-limit reservation';
   const allowance=await admit(req,owner);admitted=true;
   const jobKey=randomBytes(32).toString('base64url'),fileKey=randomBytes(32).toString('base64url');
   const exp=Date.now()+SESSION_MS;
   stage='sandbox creation';
   worker=await Worker.create({name,source:{type:'snapshot',snapshotId},ports:[8000],resources:{vcpus:1},timeout:SESSION_MS,persistent:false,networkPolicy:NETWORK,env:{JOB_KEY:jobKey,FILE_KEY:fileKey,APP_ORIGIN:req.headers.origin,JOB_EXPIRES_AT:String(exp)}});
   stage='worker file setup';
   const names=['worker.py','runner_entry.py','desktop_runner.py','spotdl_cli.py'];
   const sources=await Promise.all(names.map(n=>readFile(new URL('../cloud/'+n,import.meta.url))));
   await worker.writeFiles([{path:'/vercel/job/config.json',content:Buffer.from(JSON.stringify(params))},...names.map((n,i)=>({path:'/vercel/'+n,content:sources[i]}))]);
   stage='worker launch';
   await worker.runCommand({cmd:'/vercel/mediaflow-venv/bin/python',args:['-u','/vercel/worker.py'],detached:true,cwd:'/vercel'});
   stage='worker readiness';
   const ready=await worker.runCommand({cmd:'/vercel/mediaflow-venv/bin/python',args:['-c',"from pathlib import Path; import time,sys; p=Path('/vercel/job/server.ready'); [(time.sleep(0.1) if not p.exists() else None) for _ in range(100)]; sys.exit(0 if p.exists() else 1)"],cwd:'/vercel'});
   if(ready.exitCode!==0)throw new Error('Worker not ready');
   stage='worker route validation';
   const domain=worker.domain(8000),url=new URL(domain);
   if(url.protocol!=='https:'||!url.hostname.endsWith('.vercel.run')||url.username||url.password||url.port)throw new Error('Invalid worker domain');
   return res.status(202).json({domain,jobKey,expiresAt:exp,remainingSessions:allowance.remaining,ticket:sign({p:'cancel',name,owner,exp:Date.now()+LEASE_MS},secret)});
  }catch(error){
   if(admitted){
    try{const current=worker||await Worker.get({name,resume:false});await current.stop();await free(owner);}
    catch(cleanupError){
     const status=cleanupError.statusCode||cleanupError.status,code=String(cleanupError.code||cleanupError.name||'');
     if(!worker&&(status===404||code==='NOT_FOUND'||code==='NotFoundError'))try{await free(owner);}catch{}
    }
   }
   if(error instanceof AdmissionError){res.setHeader('Retry-After',String(error.retry));return res.status(error.status).json({error:error.message,retryAfter:error.retry});}
   console.error('Cloud download start:',stage,error.name,error.statusCode||error.status||'',error.code||'');
   return res.status(502).json({error:'The cloud download could not start. Please reload and try again. Your Mac app remains available.'});
  }
 };
}
export default createHandler();
