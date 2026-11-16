// Isolated production-preview transport. Not imported by application code.
// Uses a reserved test hostname and a temporary trusted CA; no TLS bypass.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, writeFile, chmod, rm, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend=fileURLToPath(new URL('../',import.meta.url));
const repository=fileURLToPath(new URL('../../',import.meta.url));
await access(join(frontend,'.next/BUILD_ID'));
const directory=await mkdtemp(join(tmpdir(),'consumer-preview-'));
await chmod(directory,0o700);
const key=join(directory,'key.pem'),cert=join(directory,'cert.pem'),preload=join(directory,'transport.cjs');
execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=consumer-api.example.test',
 '-addext','subjectAltName=DNS:consumer-api.example.test','-days','2','-keyout',key,'-out',cert],{stdio:'ignore'});
await chmod(key,0o600);
await writeFile(preload,`// Test process only. Never install in production.\nconst dns=require('node:dns');\nconst lookup=dns.lookup;\ndns.lookup=function(host,options,callback){\n if(host!=='consumer-api.example.test')return lookup.apply(this,arguments);\n const done=typeof options==='function'?options:callback;\n queueMicrotask(()=>options&&options.all?done(null,[{address:'127.0.0.1',family:4}]):done(null,'127.0.0.1',4));\n};\nconst fetch=globalThis.fetch;\nglobalThis.fetch=function(input,options){\n const url=new URL(typeof input==='string'?input:input.url||String(input));\n if(!['consumer-api.example.test','127.0.0.1','localhost'].includes(url.hostname))throw Error('Non-fixture network request prohibited during consumer QA');\n return fetch.call(this,input,options);\n};\n`);
const children=[];
let stopping=false;
async function stop(code=0){
 if(stopping)return;stopping=true;
 for(const child of children)child.kill('SIGTERM');
 await Promise.all(children.map(child=>child.exitCode!==null||child.signalCode!==null||!child.pid?Promise.resolve():new Promise(resolve=>child.once('exit',resolve))));
 await rm(directory,{recursive:true,force:true});process.exit(code);
}
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>void stop());
const fixture=spawn(process.execPath,['frontend/tests/fixtures/consumer-api.mjs'],{cwd:repository,stdio:'inherit',env:{...process.env,
 CONSUMER_FIXTURE_TLS_CERT:cert,CONSUMER_FIXTURE_TLS_KEY:key}});children.push(fixture);
fixture.on('error',()=>void stop(1));fixture.on('exit',code=>{if(!stopping)void stop(code||1);});
for(let attempt=0;attempt<100;attempt++){
 try{const response=await fetch('http://127.0.0.1:19081/api/v1/features/');if(response.ok)break;}catch{}
 if(attempt===99){console.error('Synthetic API did not become ready.');await stop(1);}
 await new Promise(resolve=>setTimeout(resolve,200));
}
const app=spawn(process.execPath,[join(frontend,'node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port','3100'],{
 cwd:frontend,stdio:'inherit',env:{...process.env,API_URL:'https://consumer-api.example.test:19443/api/v1',
 NODE_EXTRA_CA_CERTS:cert,NODE_OPTIONS:[process.env.NODE_OPTIONS||'',`--require=${preload}`].join(' ').trim(),NEXT_TELEMETRY_DISABLED:'1'}});
children.push(app);app.on('error',()=>void stop(1));app.on('exit',code=>{if(!stopping)void stop(code||1);});
console.log('Consumer QA: http://localhost:3100; synthetic HTTPS API only; no hosted records or providers.');
