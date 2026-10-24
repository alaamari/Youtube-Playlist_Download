// Public cloud jobs remain disabled until a zero-overage execution service is configured.
// No worker SDK or credentials are loaded by this endpoint.
export const config={maxDuration:5};
export default function handler(req,res) {
  res.setHeader('Cache-Control','no-store');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Allow','GET, POST');
  if(req.method==='GET')return res.status(200).json({status:'paused',mode:'desktop',cloudEnabled:false,message:'Cloud downloads are paused. Use the Mac app to download directly to your chosen folder.'});
  if(req.method!=='POST')return res.status(405).json({error:'Method not allowed.'});
  return res.status(503).json({error:'Cloud downloads are paused to prevent unapproved cloud charges. Use the Mac app instead.'});
}
