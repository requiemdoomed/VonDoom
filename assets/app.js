'use strict';
const $ = id => document.getElementById(id);
const bits = (n, width) => n.toString(2).padStart(width, '0');
let state = 0, edge = 0, trace = [], token = '', live = false, busy = false, configured = false;
let requestEpoch = 0;
function decode(key) {
  const b3=(key>>3)&1, b2=(key>>2)&1, b1=(key>>1)&1, b0=key&1;
  return [b3 & (1-b2) & b1 & (1-b0), (1-b3) & b2 & b1 & (1-b0), b3 & (1-b2) & (1-b1) & b0];
}
function gateNext(q, key) {
  const [a,b,c] = decode(key), q1=q>>1, q0=q&1;
  return ((((1-q1)&q0&b)|(q1&(1-q0)&c))<<1) | (((1-q1)&(1-q0)&a)|(q1&(1-q0)&c));
}
function drawTrace() {
  $('trace').replaceChildren();
  for (const values of trace.slice().reverse()) {
    const row = document.createElement('tr');
    for (const value of values) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    $('trace').append(row);
  }
  drawWaveform();
}

function svgNode(tag, attributes, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

function drawWaveform() {
  const chart = $('waveform'), rows = trace.slice(-16);
  const width = Math.max(500, 105 + rows.length * 48);
  chart.replaceChildren();
  chart.setAttribute('viewBox', `0 0 ${width} 245`);
  if (!rows.length) {
    chart.append(svgNode('text', {x:20,y:120,class:'wave-label'}, 'Submit a key to start the timing trace.'));
    return;
  }
  const names = ['CLK', 'Q1', 'Q0', 'GREEN'];
  names.forEach((name, signal) => {
    const baseline = 50 + signal * 48;
    chart.append(svgNode('text', {x:8,y:baseline+4,class:'wave-label'}, name));
    let path = '';
    rows.forEach((row, i) => {
      const x = 90 + i * 48;
      const oldState = parseInt(row[3], 2), newState = parseInt(row[4], 2);
      const value = q => signal === 1 ? q >> 1 : signal === 2 ? q & 1 : Number(q === 3);
      const y = bit => baseline + (bit ? -13 : 9);
      if (signal === 0) path += `M${x} ${y(0)}H${x+20}V${y(1)}H${x+38}V${y(0)}H${x+48}`;
      else path += `M${x} ${y(value(oldState))}H${x+20}V${y(value(newState))}H${x+48}`;
      if (signal === 0) {
        chart.append(svgNode('path', {d:`M${x+20} 25V210`,class:'wave-grid'}));
        chart.append(svgNode('text', {x:x+14,y:232,class:'wave-label'}, row[0]));
      }
    });
    chart.append(svgNode('path', {d:path,class:`wave-signal ${signal===0?'wave-clock':signal===3?'wave-output':''}`}));
  });
}

function checkLogic() {
  let passed = 0;
  for (let q=0; q<4; q++) for (let key=0; key<16; key++) {
    const expected = q<3 && key===[10,6,9][q] ? q+1 : 0;
    if (gateNext(q,key) === expected) passed++;
  }
  $('self-check').textContent = `${passed} / 64`;
  $('check-result').textContent = passed===64 ? 'All 64 gate transitions match the reference state table.' : 'A gate transition failed. Review the implementation.';
}
$('check-logic').onclick = checkLogic;
$('demo-step').onclick = () => press(state<3 ? [10,6,9][state] : 0);
function press(key) {
  const old = state, signals = decode(key); state = gateNext(state, key); edge++;
  $('input-bits').textContent=bits(key,4); $('state-bits').textContent=bits(state,2);
  $('next-bits').textContent=bits(state,2); $('green-bit').textContent=Number(state===3);
  ['i10','i6','i9'].forEach((id,i)=>$(id).textContent=signals[i]);
  [...$('states').children].forEach((node,i)=>node.classList.toggle('active',i===state));
  $('lab-message').textContent = state===3 ? 'Sequence accepted. The next key will relock.' : state===0 ? 'Returned to S0. Start again with key 10.' : `Now S${state}. Next expected key: ${[10,6,9][state]}.`;
  trace.push([edge,key,bits(key,4),bits(old,2),bits(state,2),Number(state===3),Number(state!==3)]);
  trace=trace.slice(-32); drawTrace();
}
for (let key=0;key<16;key++) {
  const button=document.createElement('button'); button.type='button';
  button.textContent=key; button.setAttribute('aria-label',`Submit key ${key}, binary ${bits(key,4)}`);
  const label=document.createElement('span'); label.textContent=bits(key,4); button.append(label);
  if ([10,6,9].includes(key)) button.classList.add('target');
  button.addEventListener('click',()=>press(key));
  button.addEventListener('keydown',event=>{if(event.repeat)event.preventDefault();});
  $('keypad').append(button);
  const row=document.createElement('tr');
  for(const value of [key,bits(key,4),...decode(key)]) {const cell=document.createElement('td');cell.textContent=value;row.append(cell);}
  $('decoder').append(row);
}
$('reset-lab').onclick=()=>{
  state=0; edge=0; trace=[]; drawTrace();
  ['state-bits','next-bits'].forEach(id=>$(id).textContent='00');
  ['green-bit','i10','i6','i9'].forEach(id=>$(id).textContent='0');
  $('input-bits').textContent='----'; $('lab-message').textContent='Ready. Submit key 10 to begin.';
  [...$('states').children].forEach((node,i)=>node.classList.toggle('active',i===0));
};
$('export').onclick=()=>{
  const text=['edge,key,input,old_q,new_q,green,red',...trace.map(row=>row.join(','))].join('\n');
  const url=URL.createObjectURL(new Blob([text],{type:'text/csv'}));
  const link=document.createElement('a'); link.href=url;link.download='lock-trace.csv';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
};
try { document.body.classList.toggle('light', localStorage.getItem('vondoom-theme')==='light'); } catch {}
$('theme').onclick=()=>{
  const light=document.body.classList.toggle('light');
  try { localStorage.setItem('vondoom-theme',light?'light':'dark'); } catch {}
};
function offline() {
  live=false; token=''; $('connection').textContent='SHOWCASE MODE';$('offline').hidden=false;
  ['unlock','lock-now','change','protected'].forEach(id=>$(id).disabled=true);
  $('lock-state').textContent='OFFLINE'; $('timer').textContent='Connect to the local Python controller';
  $('device-icon').classList.remove('unlocked');$('status-dot').classList.remove('open');
  $('protected-result').textContent='Available only while the Python controller is unlocked.';
  $('attempts').textContent='—';
}
function render(data) {
  configured=data.state!=='UNCONFIGURED';
  $('connection').textContent='PYTHON CONNECTED'; $('offline').hidden=true;
  $('lock-state').textContent=data.state;
  $('timer').textContent=data.state==='UNLOCKED'?`Automatically locks in ${data.remaining}s`:data.state==='LOCKOUT'?`Try again in ${data.cooldown}s`:configured?'Waiting for a valid PIN':'Create your private PIN to begin';
  $('attempts').textContent=data.attempts_left;
  $('unlock').textContent=configured?'Unlock':'Create PIN';
  $('pin-label').textContent=configured?'PIN · 6–12 digits':'Choose a PIN · 6–12 digits';
  $('confirm-wrap').hidden=configured; $('confirm-pin').required=!configured;
  $('device-icon').classList.toggle('unlocked',data.state==='UNLOCKED');
  $('status-dot').classList.toggle('open',data.state==='UNLOCKED');
  $('unlock').disabled=busy||data.state==='LOCKOUT';
  $('lock-now').disabled=busy||!configured;
  $('change').disabled=busy||!configured||data.state==='LOCKOUT';
  $('protected').disabled=busy||data.state!=='UNLOCKED';
  if(data.state!=='UNLOCKED')$('protected-result').textContent='Available only while the Python controller is unlocked.';
  $('events').replaceChildren();
  for(const event of data.events) {
    const item=document.createElement('li'), time=document.createElement('time'), text=document.createElement('span');
    time.textContent=new Date(event.time*1000).toLocaleTimeString();text.textContent=event.action.replaceAll('_',' ');
    item.append(time,text);$('events').append(item);
  }
}
async function request(path, data) {
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),7000);
  const options={cache:'no-store',signal:controller.signal};
  if(data!==undefined)Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-Lock-Token':token},body:JSON.stringify(data)});
  try {
    const response=await fetch(path,options);const result=await response.json();
    if(!response.ok)throw new Error(result.error||'Request failed.');
    return result;
  } finally { clearTimeout(timeout); }
}
async function act(path,data) {
  if(!live||busy)return;
  requestEpoch++;
  let snapshot = null;
  busy=true;['unlock','lock-now','change','protected'].forEach(id=>$(id).disabled=true);
  try {
    const result=await request(path,data);
    if(result.state) { snapshot=result; render(result); }
    $('feedback').textContent=result.ok===false?'Access denied. Check the PIN or wait for cooldown.':path==='/api/setup'?'PIN created. The lock is ready.':path==='/api/change-pin'?'PIN changed. The system is locked.':path==='/api/unlock'?'Access granted.':'Done.';
    if(result.message)$('protected-result').textContent=result.message;
  } catch(error) {
    $('protected-result').textContent='Protected response cleared. Check the controller state before retrying.';
    if(error.message==="Use this server's local web page.") {
      token='';
      $('feedback').textContent='Controller connection changed. Reconnecting; submit again once connected.';
    } else $('feedback').textContent=error.name==='AbortError'?'The controller did not respond in time. Check its status before retrying.':error.message;
  }
  finally {
    busy=false;
    if(snapshot)render(snapshot);
    await poll();
  }
}
$('pin-form').onsubmit=event=>{
  event.preventDefault();
  const pin=$('pin').value;
  if(!configured&&pin!==$('confirm-pin').value){$('feedback').textContent='The two PINs do not match.';return;}
  $('pin').value='';$('confirm-pin').value='';act(configured?'/api/unlock':'/api/setup',{pin});
};
$('lock-now').onclick=()=>act('/api/lock',{});
$('protected').onclick=()=>act('/api/protected',{});
$('change-form').onsubmit=event=>{
  event.preventDefault();const current=$('current-pin').value,newPin=$('new-pin').value;
  if(newPin!==$('new-pin-confirm').value){$('feedback').textContent='The new PINs do not match.';return;}
  $('current-pin').value='';$('new-pin').value='';$('new-pin-confirm').value='';act('/api/change-pin',{current,new:newPin});
};
let polling=false;
async function poll() {
  if(location.protocol==='file:'||polling||busy)return;
  polling=true;
  const epoch=requestEpoch;
  try {
    const data=await request(token?'/api/status':'/api/session');
    if(epoch!==requestEpoch)return;
    if(data.token)token=data.token;
    if(!live)$('feedback').textContent='Controller connected.';
    live=true;render(data);
  }catch(error){if(epoch===requestEpoch)offline();}
  finally{polling=false;}
}
drawWaveform();checkLogic();poll();setInterval(poll,1000);
