'use strict';
// Remove credentials from older cloud sessions. This release starts no public workers.
sessionStorage.removeItem('mediaflow-cloud-job');
const connection=document.getElementById('connection');
if(connection)connection.textContent='Mac app available';
