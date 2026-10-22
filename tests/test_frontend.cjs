// A tiny DOM harness checks browser logic without requiring a browser install.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor() {
    this.children=[];this.textContent='';this.value='';this.disabled=false;
    this.hidden=false;this.handlers={};this.classes=new Set();this.attributes={};
    this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),
      toggle:(x,on)=>{if(on===undefined)on=!this.classes.has(x);on?this.classes.add(x):this.classes.delete(x);return on;}};
  }
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  setAttribute(name,value){this.attributes[name]=String(value);}
  addEventListener(name,fn){this.handlers[name]=fn;}
  click(){if(this.handlers.click)this.handlers.click();}
}
const elements=new Map();
function get(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);}
get('states').append(...Array.from({length:4},()=>new Element()));
const context=vm.createContext({document:{getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element(),body:new Element()},
  location:{protocol:'file:'},setInterval(){},setTimeout,clearTimeout,Blob,URL,AbortController,Date,console});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../assets/app.js'),'utf8'),context);
let count=0;
for(let q=0;q<4;q++)for(let key=0;key<16;key++){
  const expected=q<3&&key===[10,6,9][q]?q+1:0;
  assert.equal(vm.runInContext(`gateNext(${q},${key})`,context),expected);count++;
}
assert.equal(get('keypad').children.length,16);assert.equal(get('decoder').children.length,16);
for(const key of [10,6,9])get('keypad').children[key].click();
assert.equal(get('state-bits').textContent,'11');assert.equal(get('green-bit').textContent,1);
assert.match(get('lab-message').textContent,/Sequence accepted/);
get('keypad').children[0].click();assert.equal(get('state-bits').textContent,'00');
get('reset-lab').onclick();assert.equal(get('trace').children.length,0);
for(let i=0;i<40;i++)get('keypad').children[5].click();
assert.equal(get('trace').children.length,32);
const status={state:'UNCONFIGURED',attempts_left:5,events:[]};
context.sample=status;vm.runInContext('render(sample)',context);
assert.equal(get('unlock').textContent,'Create PIN');assert.equal(get('confirm-wrap').hidden,false);
status.state='LOCKOUT';status.cooldown=30;vm.runInContext('render(sample)',context);
assert.equal(get('unlock').disabled,true);assert.equal(get('change').disabled,true);
status.state='UNLOCKED';status.remaining=15;vm.runInContext('render(sample)',context);
assert.equal(get('protected').disabled,false);assert.equal(get('confirm-wrap').hidden,true);
vm.runInContext('offline()',context);assert.equal(get('protected').disabled,true);
assert.equal(get('self-check').textContent,'64 / 64');
get('reset-lab').onclick();
for(let i=0;i<3;i++)get('demo-step').onclick();
assert.equal(get('state-bits').textContent,'11');
assert.equal(get('waveform').children.filter(n=>(n.attributes.class||'').startsWith('wave-signal')).length,4);
get('demo-step').onclick();assert.equal(get('state-bits').textContent,'00');
get('new-pin').value='123456';get('new-pin-confirm').value='654321';
get('change-form').onsubmit({preventDefault(){}});
assert.match(get('feedback').textContent,/do not match/);
console.log(`${count}/64 JavaScript transitions passed; keypad, reset, trace retention, setup, lockout, unlock and offline UI checks passed.`);

async function integration() {
  const {spawn}=require('node:child_process');
  const {once}=require('node:events');
  const os=require('node:os');
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'vondoom-test-'));
  const python=process.env.PYTHON || (process.platform==='win32'?'python':'python3');
  const child=spawn(python,['-u','-c',
    'from server import make_server; import sys; app=make_server(0,sys.argv[1]); print(app.server_port,flush=True); app.serve_forever()',
    path.join(temp,'lock.db')],{cwd:path.join(__dirname,'..'),stdio:['ignore','pipe','pipe']});
  let errors='';child.stderr.on('data',chunk=>errors+=chunk);
  const exited=once(child,'exit');
  try {
    const port=await new Promise((resolve,reject)=>{
      let text='';const deadline=setTimeout(()=>reject(new Error('Server startup timed out. '+errors)),10000);
      child.on('error',error=>{clearTimeout(deadline);reject(error);});
      child.on('exit',code=>{clearTimeout(deadline);reject(new Error(`Server exited: ${code}. ${errors}`));});
      child.stdout.on('data',chunk=>{text+=chunk;if(text.includes('\n')){clearTimeout(deadline);resolve(Number(text.trim()));}});
    });
    const base=`http://127.0.0.1:${port}`;
    context.location.protocol='http:';
    context.fetch=(route,options)=>fetch(base+route,{...options,headers:{...options.headers,Origin:base}});
    await vm.runInContext('poll()',context);
    assert.equal(get('lock-state').textContent,'UNCONFIGURED');
    await vm.runInContext('act("/api/setup",{pin:"483729"})',context);
    assert.equal(get('lock-state').textContent,'LOCKED');
    await vm.runInContext('act("/api/unlock",{pin:"483729"})',context);
    assert.equal(get('lock-state').textContent,'UNLOCKED');
    await vm.runInContext('act("/api/protected",{})',context);
    assert.match(get('protected-result').textContent,/Access granted/);
    await vm.runInContext('act("/api/lock",{})',context);
    assert.equal(get('protected').disabled,true);
    await vm.runInContext('act("/api/change-pin",{current:"483729",new:"123456"})',context);
    await vm.runInContext('act("/api/unlock",{pin:"123456"})',context);
    assert.equal(get('lock-state').textContent,'UNLOCKED');
    for(let i=0;i<5;i++)await vm.runInContext('act("/api/unlock",{pin:"999999"})',context);
    assert.equal(get('lock-state').textContent,'LOCKOUT');
    assert.equal(get('unlock').disabled,true);
    await vm.runInContext('token="expired"; act("/api/lock",{})',context);
    assert.notEqual(vm.runInContext('token',context),'expired');
    assert.equal(get('lock-state').textContent,'LOCKOUT');
    const realFetch=context.fetch;
    let finishOldPoll;
    context.fetch=(route,options)=>route==='/api/status'
      ? new Promise(resolve=>{finishOldPoll=resolve;}) : realFetch(route,options);
    const oldPoll=vm.runInContext('poll()',context);
    await vm.runInContext('act("/api/lock",{})',context);
    finishOldPoll({ok:true,json:async()=>({state:'UNLOCKED',remaining:15,attempts_left:5,events:[]})});
    await oldPoll;
    assert.equal(get('lock-state').textContent,'LOCKOUT');
    context.fetch=()=>Promise.reject(new Error('Connection lost'));
    await vm.runInContext('poll()',context);
    assert.equal(get('lock-state').textContent,'OFFLINE');
    assert.equal(get('protected').disabled,true);
    assert.doesNotMatch(get('protected-result').textContent,/Access granted/);
    console.log('JavaScript-to-Python HTTP integration passed: setup, unlock, protected response, relock, PIN change, lockout, token refresh, stale polling and disconnect recovery.');
  } finally {
    child.kill();await exited;fs.rmSync(temp,{recursive:true,force:true});
  }
}
if(process.argv.includes('--integration'))integration().catch(error=>{console.error(error);process.exitCode=1;});
