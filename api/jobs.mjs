import {Sandbox} from '@vercel/sandbox';
import {readFile} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
import {sign,verify,validate} from '../lib/security.mjs';
export const config={maxDuration:120};
export default async function handler(req,res) {
  res.setHeader('Cache-Control','no-store');
  const key=process.env.MEDIAFLOW_SIGNING_SECRET;
  if(!key||!process.env.MEDIAFLOW_SNAPSHOT_ID)return res.status(503).json({error:'Cloud worker is not configured yet.'});
  if(req.method==='GET')return res.status(200).json({status:'ready',mode:'cloud'});
  if(req.method!=='POST')return res.status(405).json({error:'Use POST.'});
  let sandbox;
  try {
    const input=typeof req.body==='string'?JSON.parse(req.body):req.body;
    if(input.action==='cancel') {
      const job=verify(input.ticket,key);
      sandbox=await Sandbox.get({name:job.name,resume:false});
      await sandbox.stop();
      return res.status(200).json({state:'cancelled'});
    }
    const params=validate(input);
    // Keep the existing one-worker limit; each browser receives its own signed job ticket.
    const name='mediaflow-download-'+randomBytes(8).toString('hex');
    const listing=await Sandbox.list({namePrefix:'mediaflow-download-',sortBy:'name',limit:50});
    for await(const current of listing)if(['pending','running'].includes(current.status))return res.status(409).json({error:'A download session is already open. Finish saving or cancel it before starting another.'});
    const jobKey=randomBytes(24).toString('base64url');
    const origin='https://'+req.headers.host;
    sandbox=await Sandbox.create({name,source:{type:'snapshot',snapshotId:process.env.MEDIAFLOW_SNAPSHOT_ID},ports:[8000],resources:{vcpus:1},timeout:2700000,persistent:false,env:{JOB_KEY:jobKey,APP_ORIGIN:origin}});
    const worker=await readFile(new URL('../cloud/worker.py',import.meta.url));
    await sandbox.writeFiles([{path:'/vercel/job/config.json',content:Buffer.from(JSON.stringify(params))},{path:'/vercel/worker.py',content:worker}]);
    await sandbox.runCommand({cmd:'/vercel/mediaflow-venv/bin/python',args:['-u','/vercel/worker.py'],detached:true,cwd:'/vercel'});
    const domain=sandbox.domain(8000);
    const exp=Date.now()+2700000;
    return res.status(202).json({domain,jobKey,expiresAt:exp,ticket:sign({name,exp},key)});
  } catch(error) {
    if(sandbox)await sandbox.stop().catch(()=>{});
    console.error('MediaFlow job error:',error.message);
    const validation=/Paste|Only YouTube|Use an HTTPS|Use a Spotify|supported format|Spotify supports/.test(error.message);
    res.status(validation?400:502).json({error:validation?error.message:'The cloud worker could not start. Please try again or check the deployment logs.'});
  }
}
