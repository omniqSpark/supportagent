'use strict';
function recordText(value){if(value===null||value==='')return 'None recorded';if(Array.isArray(value))return value.length?value.map(recordText).join(' | '):'None recorded';if(typeof value==='object')return Object.entries(value).map(([key,item])=>key.replaceAll('_',' ')+': '+recordText(item)).join('; ');return String(value);}

const $ = id => document.getElementById(id);
let tickets = [], current = null, mode = 'sample', sequence = 0;
const el = (tag, text, cls) => { const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(cls) n.className = cls; return n; };
async function api(path, options) {
  const res = await fetch(path, {cache:'no-store', ...options});
  const data = await res.json();
  if(!res.ok) throw new Error(data.error || 'Request failed. Retry when ready.');
  return data;
}
function queue() {
  const q = $('search').value.toLowerCase(); $('queue').replaceChildren();
  const matches = tickets.filter(t => (t.id+' '+t.subject).toLowerCase().includes(q));
  for(const t of matches) {
    const b = el('button', undefined, 'ticket'); b.append(el('small','#'+t.id),el('span',t.subject));
    b.setAttribute('aria-current', String(current?.id === t.id)); b.onclick = () => select(t.id); $('queue').append(b);
  }
  if(!matches.length) $('queue').append(el('p','No matching tickets. Clear your search or check the pilot scope.','muted'));
}
async function reload() {
  $('refresh').disabled = true; $('status').textContent = 'Loading ticket queue…';
  try { const status = await api('/api/status'); mode=status.mode; $('mode').textContent= mode==='sample'?'Sample mode · Read-only':'Freshdesk pilot · Read-only';
    tickets = await api('/api/tickets'); queue(); $('status').textContent = tickets.length+' tickets available for review.';
    if(tickets.length && !current) await select(tickets[0].id);
  } catch(e) { $('status').textContent=e.message; } finally { $('refresh').disabled=false; }
}
async function select(id) {
  const request = ++sequence; $('status').textContent='Reading ticket and conversation history…'; $('review').setAttribute('aria-busy','true');
  $('review').replaceChildren(el('p','Loading review…','empty'));
  try { const data = await api('/api/review?id='+encodeURIComponent(id)); if(request!==sequence)return; render(data); $('status').textContent='Review ready. Drafts have not been sent.';
  } catch(e) { if(request===sequence){$('status').textContent=e.message; $('review').replaceChildren(el('p','Unable to review this ticket. Select a ticket to retry.','empty'));} }
  finally { if(request===sequence)$('review').removeAttribute('aria-busy'); }
}
function metric(label,value,detail) { const n=el('div'); n.append(el('p',label,'metric-label'),el('div',value,'metric-value'),el('p',detail,'metric-detail'));return n; }
function render({ticket:t,review:r}) {
  current=t; queue(); const root=$('review');root.replaceChildren();
  root.append(el('p','#'+t.id+' / '+r.customer+' / '+r.site,'eyebrow'),el('h2',t.subject,'ticket-title'));
  if(t.mapping_notes) root.append(el('p',t.mapping_notes,'muted'));
  if(t.identity_evidence?.status){
    const evidence=el('details');evidence.append(el('summary','Customer identity evidence · '+t.identity_evidence.status));
    evidence.append(el('p','Requester domain: '+(t.identity_evidence.requester_domain||'Unavailable')),el('p','Company: '+(t.identity_evidence.display_company||t.customer_name||t.identity_evidence.ticket_company_id||'Not identified')));
    for(const c of t.identity_evidence.company_candidates||[])evidence.append(el('p',c.name+' · '+c.evidence.join('; ')));
    for(const warning of t.identity_evidence.warnings||[])evidence.append(el('p',warning,'muted'));
    evidence.append(el('p',t.identity_evidence.directory_basis,'footnote'));root.append(evidence);
  }
  if(t.assigned_agent) root.append(el('p','Current Freshdesk owner: '+t.assigned_agent+' · Coverage and skills not implied.','muted'));
  const input=el('details'); input.append(el('summary','Original ticket & conversation history'),el('p',t.description,'text'));
  for(const c of t.conversations){input.append(el('h3',(c.private?'Internal note':'Conversation')+' · '+(c.author_role||'unknown')+' · '+(c.created_at||'Date not supplied')),el('p',c.body,'text'));} root.append(input);
  const m=el('div',undefined,'metrics');m.append(metric('ISSUE CLASSIFICATION',r.category,r.confidence),metric('RECOMMENDED PRIORITY',r.priority,'Advisory priority; ticket unchanged.'),metric('LOCAL TECHNICIAN',r.technician,r.routing_reason));root.append(m);
  const call=el('section',undefined,'callout'+(r.escalate?' warn':''));call.append(el('h3',r.escalate?'Human escalation required':'Ready for support review'));
  if(r.escalate){const list=el('ul');r.escalation_reasons.forEach(x=>list.append(el('li',x)));call.append(list);}else{call.append(el('p','No mandatory escalation detected. Confirm the recommendation before acting.'));}
  call.append(el('h3','Smallest useful next detail'),el('p',r.question));root.append(call);
  const context=r.conversation_review;
  if(context){
    const action=el('section',undefined,'block');action.append(el('h3','Next action'),el('p','Responsible: '+context.action_owner),el('p',context.next_action||'A reviewer must determine the next action.'),el('p',r.send_recommendation||'Human approval required','badge'));
    action.append(el('p','Reply language: '+(r.reply_language==='es'?'Spanish':'English')+' · Latest public evidence: '+context.latest_public_source,'muted'));
    const evidence=el('details');evidence.append(el('summary','Conversation evidence'));
    for(const item of context.pending||[])evidence.append(el('p',item.topic+' ['+item.source+']'));
    if(context.conflict_sources?.length)evidence.append(el('p','Potentially conflicting guidance: '+context.conflict_sources.join('; ')));
    action.append(evidence);root.append(action);
  }
  const columns=el('div',undefined,'columns');const draft=el('section');const label=el('div',undefined,'draft-label');const lab=el('label','Customer reply');lab.htmlFor='reply';label.append(lab,el('span','Unsent draft','badge'));
  const reply=el('textarea');reply.id='reply';reply.value=r.reply;draft.append(label,reply,el('p','Edit locally for review. Edits are discarded when switching tickets.','footnote'));
  const hand=el('section');hand.append(el('h3','Internal handoff'),el('p',r.handoff,'text'));columns.append(draft,hand);root.append(columns);
  const sources=el('section',undefined,'block');sources.append(el('h3','Supporting sources'));
  const guidance=r.library_guidance;
  if(guidance){
    const tech=el('section',undefined,'block');tech.append(el('h3','Suggestions for the technician'),el('p',guidance.scope,'badge'));
    if(!guidance.technician.length)tech.append(el('p','No applicable technician card passed the product, version and source checks.','muted'));
    for(const g of guidance.technician){tech.append(el('h4',g.title),el('p',g.text),el('p',g.citation+' · '+g.filename,'muted'),el('p','Scope: '+g.applicability));}
    for(const g of guidance.customer)tech.append(el('p','Customer draft source: '+g.citation+' · '+g.filename,'muted'));
    if(guidance.withheld.length){const d=el('details');d.append(el('summary','Guidance withheld and missing details'));for(const g of guidance.withheld)d.append(el('p',g.id+': '+g.reason));tech.append(d);}
    root.append(tech);
  }
  if(!r.sources.length)sources.append(el('p',guidance?.customer.length||guidance?.technician.length?'No production-approved article is available. The cited library suggestions above are authorized for sandbox draft testing only.':'No applicable approved article or sandbox guidance is available. Technical advice is withheld.','muted'));
  r.sources.forEach(s=>{const n=el('details');n.append(el('summary',s.id+' · '+s.title+' · v'+s.version),el('p',s.advice),el('p','Approval: '+s.approval+' · '+s.approved_by+' · Valid through '+s.valid_until,'muted'));sources.append(n);});
  if(r.coverage_source)sources.append(el('p','Routing source: '+r.coverage_source+' · See reference library for coverage and skills.','muted'));root.append(sources);
  if(r.candidate_sources?.length){
    const refs=el('section',undefined,'block');refs.append(el('h3','References awaiting review'),el('p','These references are not approved instructions for this ticket.','muted'));
    for(const s of r.candidate_sources){const d=el('details');d.append(el('summary',s.id+' · '+s.title),el('p',s.limitations),el('p','Approval: '+s.approval+' · Classification: '+s.classification,'muted'));
      if(s.review_findings){d.append(el('h3','Source review finding'),el('p',s.review_findings.finding),el('p','Locators: '+s.review_findings.locators.join('; ')),el('p','Images detected: '+s.review_findings.images_detected+' · Images reviewed: '+(s.review_findings.images_reviewed?'Yes':'No'),'muted'));}
      if(s.kind==='freshdesk' && /^https:\/\/[a-z0-9-]+\.freshdesk\.com\/support\/solutions\/articles\/\d+$/.test(s.url||'')){const a=el('a','Open original article');a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';d.append(a);}
      if(s.path)d.append(el('p','Original local reference: '+s.path,'text'));
      d.append(el('p','Registered SHA-256: '+s.sha256,'text'));refs.append(d);}
    root.append(refs);
  }
  for(const b of r.blocked_sources||[])root.append(el('p','Withheld '+b.id+': '+b.reasons.join('; '),'muted'));
  const evidence=el('details');evidence.append(el('summary','Classification evidence'),el('pre',JSON.stringify(r.evidence,null,2)));root.append(evidence);
  // Keep the everyday review focused; preserve all evidence in one disclosure.
  const supporting=el('details');supporting.id='supporting-details';
  supporting.append(el('summary','Supporting details and technician handoff'));
  for(const child of [...root.children].slice(2))supporting.append(child);
  const overview=el('section',undefined,'block');overview.append(el('h3',r.current_issue?.source?.startsWith('Conversation')?'Latest customer update':'Customer issue'),el('p',(r.current_issue?.text||t.subject).length>280?(r.current_issue?.text||t.subject).slice(0,280).replace(/\s+\S*$/,'')+'…':(r.current_issue?.text||t.subject),'text'));
  const decision=el('section',undefined,'block');decision.append(el('h3','Technician recommendation'),el('p',r.technician),el('p',r.routing_reason,'muted'));
  if(r.escalate)decision.append(el('p',r.priority==='Urgent'?'Urgent — human review required':'Human review required','badge'));
  root.append(overview,draft,decision,supporting);if(r.internal_record){const audit=el('details');audit.append(el('summary','Internal reply record'));for(const [key,value] of Object.entries(r.internal_record))audit.append(el('p',key.replaceAll('_',' ')+': '+recordText(value),'text'));draft.append(audit);}
  if(mode==='sample'){
    const edit=el('details');edit.append(el('summary','Edit sample ticket & rerun'));
    const label=el('label','Common ticket JSON');label.htmlFor='editor'; const area=el('textarea');area.id='editor';area.value=JSON.stringify(t,null,2);
    const b=el('button','Analyze edited sample','primary');b.onclick=async()=>{b.disabled=true;try{const data=JSON.parse(area.value);const result=await api('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});render(result);$('status').textContent='Edited sample analyzed. No files or tickets were changed.';}catch(e){$('status').textContent=e instanceof SyntaxError?'Invalid JSON. Your edits are preserved.':e.message;}finally{b.disabled=false;}};
    edit.append(label,area,el('p','Temporary preview. To keep edits, update data/tickets.json locally.','footnote'),b);root.append(edit);
  }
}
$('search').oninput=queue;$('refresh').onclick=reload;
$('references').onclick=async()=>{try{const data=await api('/api/references');const n=$('library-content');n.replaceChildren();for(const [title,rows] of Object.entries(data)){n.append(el('h3',({knowledge:'Knowledge articles',coverage:'Site-to-technician coverage',source_catalog:'Source register'})[title]||title));rows.forEach(r=>{const d=el('details');d.append(el('summary',r.id+' · '+(r.title||r.site+' / '+r.technician)),el('pre',JSON.stringify(r,null,2)));n.append(d);});}$('library').hidden=false;$('library').scrollIntoView();$('close-library').focus();}catch(e){$('status').textContent=e.message;}};
$('close-library').onclick=()=>{$('library').hidden=true;$('references').focus();};reload();

let historyItems=[];
function showHistory(){
  const item=historyItems.find(x=>x.id===$('history-select').value);const root=$('history-body');root.replaceChildren();if(!item)return;
  root.append(el('h3','#'+item.id+' · '+item.subject),el('p','Decision: '+item.decision+' · Reply cutoff: '+(item.cutoff||'Unavailable'),'badge'),el('p',item.purpose,'muted'),el('p',item.context_limit,'muted'));
  const context=el('details');context.append(el('summary','Customer context before the selected reply'),el('p',item.context,'text'));root.append(context);
  root.append(el('h4','Historical public support reply'),el('p',item.historical_reply||'No eligible public reply found. Keep on hold for manual review.','text'));
  if(item.flags.length)root.append(el('p',item.flags.join(' · '),'callout warn'));
  const label=el('label','Your preferred reply');label.htmlFor='history-reply';const reply=el('textarea');reply.id='history-reply';reply.value=item.proposed_reply;
  const noteLabel=el('label','What should the agent learn or avoid?');noteLabel.htmlFor='history-note';const note=el('textarea');note.id='history-note';note.value=item.note;
  root.append(label,reply,noteLabel,note);const actions=el('div',undefined,'queuehead');
  for(const [decision,title] of [['approved','Approve style'],['edited','Save edit & approve style'],['rejected','Reject'],['hold','Hold']]){
    const b=el('button',title,decision==='approved'?'primary':'');
    b.disabled=['approved','edited'].includes(decision)&&(!item.historical_reply||item.flags.includes('Incomplete history')||item.flags.some(f=>f.includes('Out-of-office')));
    b.onclick=async()=>{const buttons=[...actions.querySelectorAll('button')];buttons.forEach(x=>x.disabled=true);
      try{const saved=await api('/api/history-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:item.id,decision,proposed_reply:reply.value,note:note.value,revision:item.revision||0})});Object.assign(item,saved);$('history-status').textContent='Saved locally: '+decision+'. No ticket changed and no reply sent.';showHistory();}
      catch(e){$('history-status').textContent=e.message;buttons.forEach(x=>x.disabled=false);}
    };actions.append(b);
  }
  root.append(actions,el('p','Approval is for a local style example only. It does not approve technical procedures or automatically train the agent. Unsaved edits are discarded when switching examples.','footnote'));
}
$('history-open').onclick=async()=>{
  $('history-panel').hidden=false;$('history-status').textContent='Loading historical examples…';
  try{const data=await api('/api/history-review');historyItems=data.items;$('history-select').replaceChildren();
    for(const item of historyItems){const option=el('option','#'+item.id+' · '+item.subject);option.value=item.id;$('history-select').append(option);}
    $('history-status').textContent=historyItems.length+' historical tickets · '+historyItems.filter(x=>x.decision==='pending').length+' pending review.';
    showHistory();$('history-panel').scrollIntoView();$('history-select').focus();
  }catch(e){$('history-status').textContent=e.message;}
};
$('history-select').onchange=showHistory;
$('history-close').onclick=()=>{$('history-panel').hidden=true;$('history-open').focus();};

let comparisons=[];
function showComparison(){
  const item=comparisons.find(x=>x.id===$('comparisons-select').value);const root=$('comparisons-body');root.replaceChildren();if(!item)return;
  root.append(el('h3','#'+item.id+' · '+item.subject),el('p','Reply cutoff: '+item.cutoff+' · '+item.before_words+' → '+item.after_words+' words'),el('p',item.limitations,'muted'));
  const columns=el('div',undefined,'columns');for(const [title,value] of [['Before style update',item.baseline],['After style update',item.revised]]){const section=el('section');section.append(el('h4',title),el('p',value,'text'));columns.append(section);}root.append(columns);
  const context=el('details');context.append(el('summary','Frozen input and historical reply'),el('p',item.input.description,'text'));
  for(const c of item.input.conversations)context.append(el('p',c.author_role+' · '+c.created_at+'\n'+c.body,'text'));
  context.append(el('h4','Historical support reply — not automatically correct'),el('p',item.historical_reply,'text'));root.append(context);
  root.append(el('p','Review whether the revised draft is clearer and useful. Shorter is not automatically better. Share the ticket ID and your correction; approval in the historical queue applies to historical style examples, not these evaluation drafts.','footnote'));
}
$('comparisons-open').onclick=async()=>{
  $('comparisons-panel').hidden=false;$('comparisons-status').textContent='Loading comparisons…';
  try{const data=await api('/api/draft-comparisons');comparisons=data.items;$('comparisons-select').replaceChildren();
    for(const item of comparisons){const option=el('option','#'+item.id+' · '+item.subject);option.value=item.id;$('comparisons-select').append(option);}
    $('comparisons-status').textContent=comparisons.length+' comparisons ready for review.';showComparison();$('comparisons-panel').scrollIntoView();$('comparisons-select').focus();
  }catch(e){$('comparisons-status').textContent=e.message;}
};
$('comparisons-select').onchange=showComparison;
$('comparisons-close').onclick=()=>{$('comparisons-panel').hidden=true;$('comparisons-open').focus();};

let pilotItems=[];
function showPilot(){
 const row=pilotItems.find(x=>x.id===$('pilot-select').value);const root=$('pilot-body');root.replaceChildren();if(!row)return;
 root.append(el('h3','#'+row.id+' '+row.ticket.subject),el('p',row.review.reply,'text'),el('p','Classification: '+row.review.category+' | Technician: '+row.review.technician+' | Priority: '+row.review.priority));
 if(row.retest){const revised=el('section',undefined,'block');revised.append(el('h3','Updated draft after your feedback'),el('p',row.retest.reply,'text'),el('p','Not yet rated. The rating fields below apply to the original draft above.','footnote'));root.append(revised);}
 const detail=el('details');detail.append(el('summary','Ticket evidence and recommendation details'),el('p',row.ticket.description,'text'));
 for(const c of row.ticket.conversations)detail.append(el('p',(c.private?'Internal':'Public')+' '+c.created_at+' '+c.body,'text'));
 detail.append(el('p',row.review.handoff,'text'));root.append(detail);
 const fields=[['reply_usefulness','Reply is useful and ready for human approval'],['classification','Issue classification is correct'],['routing','Technician recommendation or abstention is correct'],['escalation','Priority and escalation are correct']];
 for(const [key,title] of fields){const label=el('label',title);label.htmlFor='score-'+key;const select=el('select');select.id='score-'+key;for(const value of ['unsure','pass','fail']){const option=el('option',value);option.value=value;select.append(option);}select.value=row.score[key]||'unsure';root.append(label,select);}
 const label=el('label','Correction or reason');label.htmlFor='pilot-note';const note=el('textarea');note.id='pilot-note';note.value=row.score.note||'';root.append(label,note);
 const save=el('button','Save review locally','primary');save.onclick=async()=>{save.disabled=true;try{const data={id:row.id,revision:row.score.revision||0,note:note.value};for(const [key] of fields)data[key]=$('score-'+key).value;row.score=await api('/api/pilot-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});await loadPilot(row.id);$('pilot-status').textContent+=' Review saved locally.';}catch(e){$('pilot-status').textContent=e.message;}finally{save.disabled=false;}};root.append(save);
}
async function loadPilot(selected){const data=await api('/api/pilot-review');pilotItems=data.items;$('pilot-select').replaceChildren();for(const row of pilotItems){const option=el('option','#'+row.id+' '+row.ticket.subject);option.value=row.id;$('pilot-select').append(option);}if(selected)$('pilot-select').value=selected;$('pilot-status').textContent=pilotItems.length+' cases. '+Object.entries(data.metrics).map(([key,m])=>key.replaceAll('_',' ')+': '+(m.scored?m.passed+'/'+m.scored+' ('+m.percent+'%)':'not scored')).join('; ');showPilot();}
$('pilot-open').onclick=async()=>{$('pilot-panel').hidden=false;try{await loadPilot();$('pilot-panel').scrollIntoView();$('pilot-select').focus();}catch(e){$('pilot-status').textContent=e.message;}};
$('pilot-select').onchange=showPilot;
$('pilot-close').onclick=()=>{$('pilot-panel').hidden=true;$('pilot-open').focus();};
