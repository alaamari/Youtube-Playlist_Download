import {mkdir,rm,copyFile} from 'node:fs/promises';
// Explicit allowlist: server source, dependency files and credentials cannot become static files.
await rm('public',{recursive:true,force:true});
await mkdir('public');
for(const file of ['index.html','style.css','cloud.js','privacy.html'])await copyFile(file,'public/'+file);
