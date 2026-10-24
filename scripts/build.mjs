import {mkdir,rm,copyFile} from 'node:fs/promises';
import {build} from 'esbuild';
await rm('public',{recursive:true,force:true});await mkdir('public');
for(const file of ['index.html','style.css','privacy.html'])await copyFile(file,'public/'+file);
await build({entryPoints:['cloud.js'],outfile:'public/cloud.js',bundle:true,minify:true,platform:'browser',target:'es2022',format:'iife'});
