import {mkdir,rm,copyFile} from 'node:fs/promises';
await rm('public',{recursive:true,force:true});await mkdir('public');
for(const file of ['index.html','style.css','privacy.html'])await copyFile(file,'public/'+file);
