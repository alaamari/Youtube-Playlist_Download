import {readFile} from 'node:fs/promises';
import {createHmac} from 'node:crypto';
import {isIP} from 'node:net';
const PREFIX='mediaflow:{v2}:';
export const SESSION_MS=20*60*1000;
export const LEASE_MS=SESSION_MS+180000;
export const WINDOW_MS=30*24*60*60*1000;
const SCRIPT=readFile(new URL('./admission.lua',import.meta.url),'utf8');
export class AdmissionError extends Error {constructor(message,status=429,retry=60){super(message);this.status=status;this.retry=retry;}}
export async function redisCommand(...command){
 const url=process.env.KV_REST_API_URL,token=process.env.KV_REST_API_TOKEN;
 if(!url||!token)throw new AdmissionError('The cloud service is being configured. Please try again shortly.',503);
 let result;
 try{
  const response=await fetch(url,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(command),signal:AbortSignal.timeout(6000)});
  if(!response.ok)throw new Error('Storage unavailable');
  result=await response.json();if(result.error)throw new Error('Storage unavailable');
 }catch{throw new AdmissionError('Usage limits could not be checked. No download worker was started. Please try again later.',503);}
 return result.result;
}
export async function reserve(req,owner,command=redisCommand){
 const raw=String(req.headers['x-vercel-forwarded-for']||req.headers['x-forwarded-for']||'').split(',')[0].trim();
 if(!isIP(raw))throw new AdmissionError('Your connection could not be verified. Please reload the website.',400);
 const ip=createHmac('sha256',process.env.MEDIAFLOW_SIGNING_SECRET).update(raw).digest('hex');
 const result=await command('EVAL',await SCRIPT,3,PREFIX+'active',PREFIX+'sessions',PREFIX+'client:'+ip,owner,Date.now(),WINDOW_MS,LEASE_MS,10,3);
 if(!Array.isArray(result)||result.length!==3)throw new AdmissionError('Usage limits are unavailable. Please try again later.',503);
 if(Number(result[0])!==1){
  const messages={1:'Another cloud session is active. Finish or end it before starting another download.',2:'The shared free allowance of 10 cloud sessions per 30 days has been used. Please use the Mac app or try after the allowance resets.',3:'Your connection has reached its daily limit of 3 cloud sessions. Please use the Mac app or try tomorrow.'};
  throw new AdmissionError(messages[result[1]]||'The free cloud allowance is unavailable.',Number(result[1])===1?409:429,Math.max(1,Math.ceil(Number(result[2])/1000)));
 }
 return {remaining:Number(result[1])};
}
export async function release(owner,command=redisCommand){
 return command('EVAL',"if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end",1,PREFIX+'active',owner);
}
