const $=id=>document.getElementById(id), num=v=>Number.isFinite(Number(v))?Number(v):null;
const fmt=(v,d=2)=>num(v)==null?'—':Number(v).toFixed(d), pct=v=>num(v)==null?'—':fmt(v,1)+'%', when=v=>v?new Date(v).toLocaleString([], {hour:'2-digit',minute:'2-digit'}):'—';
const age=s=>s==null?'—':s<60?fmt(s,1)+' s':Math.floor(s/60)+' m '+Math.floor(s%60)+' s';
const duration=s=>s==null?'—':s<60?Math.round(s)+' s':s<3600?Math.floor(s/60)+' m':Math.floor(s/3600)+' h '+Math.floor((s%3600)/60)+' m';
const avg=a=>{let x=a.map(num).filter(v=>v!=null);return x.length?x.reduce((p,v)=>p+v,0)/x.length:null};
const imbalance=a=>{let x=a.map(num).filter(v=>v!=null),m=avg(x);return m?((Math.max(...x)-Math.min(...x))/m*100):null};
const ymd=d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
const addDays=(d,n)=>{let x=new Date(d);x.setDate(x.getDate()+n);return x};
let liveData={}, energyData={}, electricalData=null, loaded={energy:false,electrical:false,compare:false};

function metric(label,value,unit=''){return `<div class="metric"><span>${label}</span><b>${value}</b><small>${unit}</small></div>`}
function row(label,value,state=''){return `<dt>${label}</dt><dd class="${state}">${value}</dd>`}
function stateWord(value){return String(value||'UNAVAILABLE').toUpperCase()}
function phaseMatrix(v){
  let vs=[num(v.voltage_l1),num(v.voltage_l2),num(v.voltage_l3)], cs=[num(v.current_a),num(v.current_b),num(v.current_c)];
  let hi=cs.some(x=>x!=null)?cs.indexOf(Math.max(...cs.filter(x=>x!=null))):null;
  return `<div class="phase-row phase-head"><span>MEASURE</span><span>L1 / A</span><span>L2 / B</span><span>L3 / C</span><span>AVG</span></div>
  <div class="phase-row"><b>Voltage</b>${vs.map(x=>`<span>${fmt(x)} <small>V</small></span>`).join('')}<strong>${fmt(avg(vs))} <small>V</small></strong></div>
  <div class="phase-row"><b>Current</b>${cs.map((x,i)=>`<span class="${i===hi?'phase-high':''}">${fmt(x)} <small>A</small></span>`).join('')}<strong>${fmt(avg(cs))} <small>A</small></strong></div>
  <div class="phase-foot"><span>Voltage spread <b>${pct(imbalance(vs))}</b></span><span>Current spread <b>${pct(imbalance(cs))}</b></span><span>Highest current <b>${hi==null?'—':'Phase '+['A','B','C'][hi]+' · '+fmt(cs[hi])+' A'}</b></span></div>`;
}

async function live(){
  try{liveData=await fetch('/api/live',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()})}
  catch(e){liveData={state:'OFFLINE',values:{},persistence:{},diag:{},error:String(e)}}
  let p=liveData,v=p.values||{},status=$('status'); status.textContent=stateWord(p.state); status.className='status '+String(p.state||'offline').toLowerCase();
  $('overview-age').textContent='Latest reading '+age(p.age_seconds)+' ago'; $('energy-overview').textContent=fmt(v.energy_kwh)+' kWh'; $('overview-phases').innerHTML=phaseMatrix(v);
  let vs=[v.voltage_l1,v.voltage_l2,v.voltage_l3],cs=[v.current_a,v.current_b,v.current_c],hi=cs.map(num).some(x=>x!=null)?cs.map(num).indexOf(Math.max(...cs.map(num).filter(x=>x!=null))):null;
  $('voltage').innerHTML=metric('L1',fmt(vs[0]),'V')+metric('L2',fmt(vs[1]),'V')+metric('L3',fmt(vs[2]),'V')+metric('Average',fmt(avg(vs)),'V')+metric('Spread',pct(imbalance(vs)));
  $('current').innerHTML=metric('A',fmt(cs[0]),'A')+metric('B',fmt(cs[1]),'A')+metric('C',fmt(cs[2]),'A')+metric('Average',fmt(avg(cs)),'A')+metric('Highest',hi==null?'—':'Phase '+['A','B','C'][hi],hi==null?'':fmt(cs[hi])+' A');
  renderHealth(); if(loaded.energy)buildInsights();
}

function renderHealth(){
  let p=liveData, q=energyData.quality||{}, persistence=stateWord((p.persistence||{}).status), healthy=persistence==='OK'?'HEALTHY':persistence;
  $('overview-health').innerHTML=row('Meter / RS485',p.serial_ok?'HEALTHY':stateWord(p.state),p.serial_ok?'ok':'bad')+row('Latest reading',age(p.age_seconds)+' ago')+row('Persistence',healthy,healthy==='HEALTHY'?'ok':'warn')+row('Coverage today',pct(q.coverage),q.coverage>=80?'ok':'warn');
  $('system-monitoring').innerHTML=row('Meter',p.serial_ok?'HEALTHY':stateWord(p.state))+row('RS485 / serial',p.serial_ok?'HEALTHY':'OFFLINE')+row('Latest reading',age(p.age_seconds)+' ago')+row('Freshness',stateWord(p.state));
  $('system-data').innerHTML=row('Persistence',persistence)+row('Database / API',persistence==='OK'?'HEALTHY':'UNAVAILABLE')+row('Latest accepted record',p.timestamp?new Date(p.timestamp).toLocaleString():'UNAVAILABLE')+row('Coverage today',pct(q.coverage));
  let d=p.diag||{}, pick=(...keys)=>{for(let k of keys)if(d[k]!=null)return d[k];return 'UNAVAILABLE'};
  $('system-quality').innerHTML=row('Current gap',q.current_gap?'YES':'NO')+row('CRC errors',pick('crc_errors','crc_error_count'))+row('Timeouts',pick('timeouts','timeout_count'))+row('Reopens',pick('reopens','reopen_count'));
  $('system-service').innerHTML=row('Dashboard API','HEALTHY')+row('Production data API',p.error?'ERROR':'HEALTHY')+row('Live state',stateWord(p.state))+row('Reporting rows',energyData.rows??'—');
  $('system-updated').textContent='Updated '+new Date().toLocaleTimeString(); $('engineering-diag').textContent=`timestamp: ${p.timestamp||'unavailable'}\nserial: ${p.serial_ok?'healthy':'unavailable'}\npersistence: ${persistence}`;
}

function setDates(kind){
  let now=new Date(),start=new Date(now),end=addDays(now,1);
  if(kind==='yesterday'){start=addDays(now,-1);end=now}
  if(kind==='7d')start=addDays(now,-6);
  if(kind==='month')start=new Date(now.getFullYear(),now.getMonth(),1);
  if(kind==='prev'){start=new Date(now.getFullYear(),now.getMonth()-1,1);end=new Date(now.getFullYear(),now.getMonth(),1)}
  $('from').value=ymd(start); $('to').value=ymd(end);
}
async function history(from,to){let r=await fetch(`/api/energy?from=${from}&to=${to}`,{cache:'no-store'});if(!r.ok)throw Error(await r.text());return r.json()}

function buildInsights(){
  let p=liveData,q=energyData.quality||{},items=[];
  if(p.state!=='LIVE')items.push(`${stateWord(p.state)} · the latest accepted reading is ${age(p.age_seconds)} old.`);
  if(q.coverage!=null&&q.coverage<80)items.push(`Monitoring coverage today is ${pct(q.coverage)}; the displayed total is partial.`);
  if(q.gap_count)items.push(`${q.gap_count} monitoring gap${q.gap_count===1?'':'s'} detected; longest ${duration(q.longest_gap_seconds)}.`);
  let dom=electricalData&&electricalData.phase_dominance_60m;if(dom&&dom.percent>=50)items.push(`Phase ${dom.phase} carried the highest current for ${fmt(dom.percent,0)}% of the last 60 minutes.`);
  let peak=energyData.peak;if(peak)items.push(`Peak accepted energy use was ${fmt(peak.energy_kwh)} kWh during ${peak.label}.`);
  if(!items.length)items.push('No notable change in the available period.');
  $('insights').innerHTML=items.slice(0,4).map(x=>`<li>${x}</li>`).join('');
}

async function loadOverview(){
  let now=new Date(),today=ymd(now),tomorrow=ymd(addDays(now,1));
  try{energyData=await history(today,tomorrow);loaded.energy=true}catch(e){energyData={error:String(e),quality:{}}}
  let p=energyData,q=p.quality||{};$('today-total').textContent=p.total_kwh==null?'UNAVAILABLE':fmt(p.total_kwh);
  $('today-demand').textContent=p.average_demand_kw==null?'WITHHELD':fmt(p.average_demand_kw)+' kW'; $('today-coverage').textContent=pct(q.coverage);
  $('today-note').textContent=p.error?p.error:(q.coverage<80?'PARTIAL · accepted records do not cover the full day':'Counter-continuous accepted energy');
  let bs=p.buckets||[],complete=bs.filter(x=>!x.partial),peak=p.peak,current=bs.at(-1),previous=bs.at(-2);
  $('recent-context').innerHTML=row('Current hour',current?fmt(current.energy_kwh)+' kWh'+(current.partial?' · PARTIAL':''):'UNAVAILABLE')+row('Previous hour',previous?fmt(previous.energy_kwh)+' kWh'+(previous.partial?' · PARTIAL':''):'UNAVAILABLE')+row('Peak complete hour',peak?peak.label+' · '+fmt(peak.energy_kwh)+' kWh':'UNAVAILABLE')+row('Valid samples',p.rows??0);
  $('today-delta').textContent='Loading…'; renderEnergy(); renderHealth(); buildInsights();
  try{let y=addDays(now,-1),prior=await history(ymd(y),today);$('today-delta').textContent=comparisonText(p,prior)}catch(_){$('today-delta').textContent='UNAVAILABLE'}
}

function renderEnergy(){
  let p=energyData,q=p.quality||{};$('total').textContent=p.total_kwh==null?'UNAVAILABLE':fmt(p.total_kwh);$('period-demand').textContent=p.average_demand_kw==null?'WITHHELD':fmt(p.average_demand_kw);
  $('peak-period').textContent=p.peak?p.peak.label:'UNAVAILABLE';$('peak-value').textContent=p.peak?fmt(p.peak.energy_kwh)+' kWh':'No complete bucket';$('coverage').textContent=pct(q.coverage);$('coverage-state').textContent=q.coverage>=80?'COMPLETE ENOUGH':'PARTIAL';
  $('quality').textContent=p.error||p.broken?'Counter continuity failed; total withheld.':p.truncated?'PARTIAL · reporting row limit reached.':`${p.rows||0} accepted samples · expected cadence ${q.expected_cadence_seconds||'—'} s.`;
  $('chart-title').textContent=(p.aggregation==='hour'?'Hourly':p.aggregation==='day'?'Daily':'Weekly')+' energy use';drawBars(p.buckets||[]);drawAvailability(p);
}

function drawBars(buckets){
  let svg=$('chart'),empty=$('chart-empty');if(!buckets.length){svg.innerHTML='';svg.classList.add('hidden');empty.classList.remove('hidden');empty.textContent='UNAVAILABLE · No accepted energy samples in this period.';return}
  svg.classList.remove('hidden');empty.classList.add('hidden');let values=buckets.map(b=>num(b.energy_kwh)).filter(v=>v!=null),max=Math.max(1,...values),left=72,top=22,bottom=52,plotH=250,plotW=850;
  let ticks=[0,max/4,max/2,max*3/4,max],grid=ticks.map((v,i)=>{let y=top+plotH-(v/max*plotH);return `<line x1="${left}" y1="${y}" x2="${left+plotW}" y2="${y}"/><text x="${left-10}" y="${y+4}" text-anchor="end">${fmt(v,1)}</text>`}).join('');
  let step=Math.min(72,plotW/Math.max(1,buckets.length)),width=Math.min(38,step*.62),usedWidth=step*buckets.length,x0=left+(buckets.length<10?(plotW-usedWidth)/2:0);
  let every=Math.max(1,Math.ceil(buckets.length/10));let bars=buckets.map((b,i)=>{let v=num(b.energy_kwh),x=x0+i*step+(step-width)/2,h=v==null?0:v/max*plotH,y=top+plotH-h,label=i%every===0||i===buckets.length-1?`<text x="${x+width/2}" y="${top+plotH+24}" text-anchor="middle">${b.label}</text>`:'';
    return `<g><rect class="bar ${b.partial?'partial':''}" tabindex="0" role="img" aria-label="${b.label}: ${v==null?'missing':fmt(v,3)+' kilowatt hours'}, coverage ${pct(b.coverage)}" x="${x}" y="${y}" width="${width}" height="${Math.max(h,v===0?1:0)}"><title>${b.label} · ${v==null?'missing':fmt(v,3)+' kWh'} · ${pct(b.coverage)} coverage${b.partial?' · partial':''}</title></rect>${v==null?`<line class="missing" x1="${x}" y1="${top+plotH-4}" x2="${x+width}" y2="${top+plotH-4}"/>`:''}${label}</g>`}).join('');
  svg.innerHTML=`<g class="gridlines">${grid}</g><text class="axis-title" transform="translate(16 ${top+plotH/2}) rotate(-90)" text-anchor="middle">Energy use (kWh)</text>${bars}<line class="baseline" x1="${left}" y1="${top+plotH}" x2="${left+plotW}" y2="${top+plotH}"/>`;
}

function drawAvailability(p){
  let q=p.quality||{},bar=$('availability-bar');bar.innerHTML='';bar.className='availability-bar '+(q.coverage>=80?'good':'partial');
  let start=new Date(p.from+'T00:00:00+07:00'),end=new Date(p.to+'T00:00:00+07:00'),span=end-start;
  (q.gaps||[]).forEach(g=>{let a=Math.max(0,(new Date(g.start)-start)/span*100),b=Math.min(100,(new Date(g.end)-start)/span*100);let el=document.createElement('i');el.style.left=a+'%';el.style.width=Math.max(.4,b-a)+'%';bar.appendChild(el)});
  $('availability-copy').textContent=`${pct(q.coverage)} coverage · ${q.gap_count||0} gap${q.gap_count===1?'':'s'}`;
  $('gap-summary').textContent=q.gap_count?`Longest gap ${duration(q.longest_gap_seconds)}${q.current_gap?' · monitoring is currently in a gap':''}.`:'No cadence gap detected in available records.';
}

async function loadEnergy(){
  $('quality').textContent='Loading bounded report…';try{energyData=await history($('from').value,$('to').value);renderEnergy()}catch(e){$('quality').textContent='ERROR · '+e.message;$('chart').innerHTML=''}
}

function lineChart(id,buckets,key){
  let svg=$(id);if(!buckets.length){svg.innerHTML='<text x="20" y="75">UNAVAILABLE · insufficient history</text>';return}
  let lines=[0,1,2].map(phase=>buckets.map(b=>b[key][phase])),all=lines.flat(),min=Math.min(...all),max=Math.max(...all),colors=['phase1','phase2','phase3'];
  svg.innerHTML='<g class="mini-grid"><line x1="42" y1="20" x2="625" y2="20"/><line x1="42" y1="125" x2="625" y2="125"/></g>'+lines.map((values,p)=>`<polyline class="${colors[p]}" points="${values.map((v,i)=>`${42+i/(values.length-1||1)*583},${125-(v-min)/(max-min||1)*105}`).join(' ')}"><title>Phase ${p+1}</title></polyline>`).join('')+`<text x="4" y="25">${fmt(max,1)}</text><text x="4" y="128">${fmt(min,1)}</text><text x="42" y="145">−60 min</text><text x="625" y="145" text-anchor="end">now</text>`;
}

async function loadElectrical(){
  if(loaded.electrical)return;loaded.electrical=true;
  try{electricalData=await fetch('/api/electrical-history',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()});let h=electricalData.last_hour,t=electricalData.today;
    lineChart('voltage-trend',electricalData.buckets||[],'v');lineChart('current-trend',electricalData.buckets||[],'i');
    $('voltage-context').innerHTML=metric('60m min / max',h?fmt(h.voltage.min)+' / '+fmt(h.voltage.max):'—','V')+metric('Today min / max',t?fmt(t.voltage.min)+' / '+fmt(t.voltage.max):'—','V')+metric('Today average',t?fmt(t.voltage.average):'—','V')+metric('Peak spread',t?pct(t.voltage_imbalance.peak):'—',t?when(t.voltage_imbalance.time):'');
    $('current-context').innerHTML=metric('60m min / max',h?fmt(h.current.min)+' / '+fmt(h.current.max):'—','A')+metric('Today min / max',t?fmt(t.current.min)+' / '+fmt(t.current.max):'—','A')+metric('Today average',t?fmt(t.current.average):'—','A')+metric('Today peak',t?fmt(t.peak_current.value):'—',t?'Phase '+t.peak_current.phase+' · '+when(t.peak_current.time):'');
    let vs=[liveData.values?.voltage_l1,liveData.values?.voltage_l2,liveData.values?.voltage_l3],cs=[liveData.values?.current_a,liveData.values?.current_b,liveData.values?.current_c];
    $('imbalance-context').innerHTML=metric('Voltage now',pct(imbalance(vs)))+metric('Voltage 1h median',h?pct(h.voltage_imbalance.median):'—')+metric('Current now',pct(imbalance(cs)))+metric('Current 1h median',h?pct(h.current_imbalance.median):'—');buildInsights();
  }catch(e){loaded.electrical=false;$('imbalance-context').textContent='UNAVAILABLE · '+e.message}
}

function comparisonText(a,b){let qa=a.quality?.coverage||0,qb=b.quality?.coverage||0;if(a.total_kwh==null||b.total_kwh==null||qa<80||qb<80)return 'UNAVAILABLE';let delta=a.total_kwh-b.total_kwh;return `${delta>=0?'+':''}${fmt(delta)} kWh · ${b.total_kwh?fmt(delta/b.total_kwh*100,1)+'%':'no baseline'}`}
function comparisonCard(a,b){let qa=a.quality?.coverage||0,qb=b.quality?.coverage||0,valid=a.total_kwh!=null&&b.total_kwh!=null&&qa>=80&&qb>=80;
  if(!valid)return `<div class="unavailable"><b>UNAVAILABLE FOR RELIABLE COMPARISON</b><p>Current coverage ${pct(qa)} · previous coverage ${pct(qb)}</p><small>${a.total_kwh==null||b.total_kwh==null?'Insufficient accepted energy history.':'One or both periods are below 80% coverage.'}</small></div>`;
  let delta=a.total_kwh-b.total_kwh,change=b.total_kwh?delta/b.total_kwh*100:null,max=Math.max(a.total_kwh,b.total_kwh,1);return `<div class="compare-values"><div><span>Current</span><b>${fmt(a.total_kwh)} kWh</b><i style="width:${a.total_kwh/max*100}%"></i></div><div><span>Previous</span><b>${fmt(b.total_kwh)} kWh</b><i style="width:${b.total_kwh/max*100}%"></i></div></div><p>${delta>=0?'+':''}${fmt(delta)} kWh · ${change==null?'no percentage baseline':(change>=0?'+':'')+fmt(change,1)+'%'}</p><small>Coverage ${pct(qa)} / ${pct(qb)}</small>`}
async function loadCompare(){
  if(loaded.compare)return;loaded.compare=true;let now=new Date(),today=ymd(now),tomorrow=ymd(addDays(now,1)),yesterday=ymd(addDays(now,-1));let monday=addDays(now,-((now.getDay()+6)%7)),month=new Date(now.getFullYear(),now.getMonth(),1);let elapsedDays=Math.max(1,Math.round((new Date(tomorrow)-month)/86400000));
  try{let [td,yd,w,pw,m,pm]=await Promise.all([history(today,tomorrow),history(yesterday,today),history(ymd(monday),tomorrow),history(ymd(addDays(monday,-7)),ymd(monday)),history(ymd(month),tomorrow),history(ymd(addDays(month,-elapsedDays)),ymd(month))]);$('cmp-day').innerHTML=comparisonCard(td,yd);$('cmp-week').innerHTML=comparisonCard(w,pw);$('cmp-month').innerHTML=comparisonCard(m,pm)}catch(e){$('compare-grid').innerHTML=`<article class="unavailable">ERROR · ${e.message}</article>`}
}

document.querySelectorAll('.tab').forEach(button=>button.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===button));document.querySelectorAll('.view').forEach(x=>x.classList.add('hidden'));$(button.dataset.view==='energy'?'energy-view':button.dataset.view).classList.remove('hidden');if(button.dataset.view==='live')loadElectrical();if(button.dataset.view==='energy')loadEnergy();if(button.dataset.view==='compare')loadCompare()});
$('preset').onchange=e=>{if(e.target.value!=='custom')setDates(e.target.value)};$('load').onclick=loadEnergy;
$('theme').onclick=()=>{document.body.classList.toggle('light');let light=document.body.classList.contains('light');$('theme').textContent=light?'DARK':'LIGHT';localStorage.setItem('fcn-theme',light?'light':'dark')};if(localStorage.getItem('fcn-theme')==='light')$('theme').click();
const sig=$('signature');if(!matchMedia('(prefers-reduced-motion: reduce)').matches){let target='Made by iw3',chars='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ#%+-/:',start=performance.now();function reveal(t){let n=Math.min(target.length,Math.floor((t-start)/80));sig.textContent=target.split('').map((c,i)=>i<n?c:chars[Math.floor(Math.random()*chars.length)]).join('');if(n<target.length)requestAnimationFrame(reveal);else sig.textContent=target}sig.textContent='';requestAnimationFrame(reveal)}
const query=new URLSearchParams(location.search);if(query.get('theme')==='light'){document.body.classList.add('light');$('theme').textContent='DARK'}else if(query.get('theme')==='dark'){document.body.classList.remove('light');$('theme').textContent='LIGHT'}
let initialPeriod=query.get('period')||'today';if([...$('preset').options].some(x=>x.value===initialPeriod))$('preset').value=initialPeriod;setDates(initialPeriod);
live();loadOverview();let initialView=query.get('view');if(initialView)document.querySelector(`.tab[data-view="${initialView}"]`)?.click();setInterval(live,2000);
