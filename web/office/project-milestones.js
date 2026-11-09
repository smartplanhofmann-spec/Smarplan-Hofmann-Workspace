import {ApiError} from './office.js';

export const MILESTONE_STATUSES=[['planned','Geplant'],['achieved','Erreicht'],['cancelled','Entfallen']];
const fields=['title','details','due_date','assignee_id','status'];
const recordKeys=['schema_version','id','project_id',...fields,'revision','created_by','created_at','updated_by','updated_at','content_hash'];
const hex=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
const fail=message=>{throw new ApiError(message,502);};
const ordered=value=>Array.isArray(value)?value.map(ordered):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,ordered(value[key])])):value;
const same=(a,b)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
const keys=(value,expected)=>value&&typeof value==='object'&&!Array.isArray(value)&&same(Object.keys(value).sort(),[...expected].sort());
export async function milestoneHash(value){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(value)))))].map(byte=>byte.toString(16).padStart(2,'0')).join('');}
function text(value,max,required=false){
  const blank=/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/u;
  if(typeof value!=='string'||[...value].length>max||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]/u.test(value)||required&&blank.test(value))fail('Bitte gültigen Text für den Meilenstein eingeben.');return value;
}
function day(value){
  if(value===null||value==='')return null;
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||value<'1900-01-01'||value>'2200-12-31')fail('Bitte ein gültiges Fälligkeitsdatum von 1900 bis 2200 eingeben.');
  const date=new Date(value+'T00:00:00Z');if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==value)fail('Bitte ein gültiges Fälligkeitsdatum eingeben.');return value;
}
export function milestoneValues(value,team,current=null){
  if(!value||!Array.isArray(team))fail('Meilenstein und Projektteam zuerst neu laden.');
  const result={title:text(value.title,200,true),details:text(value.details,10000),due_date:day(value.due_date??null),assignee_id:value.assignee_id===''?null:value.assignee_id,status:value.status};
  if(!MILESTONE_STATUSES.some(([status])=>status===result.status))fail('Unbekannter Meilensteinstatus.');
  if(result.assignee_id!==null&&(!hex(result.assignee_id)||result.assignee_id!==current?.assignee_id&&!team.some(member=>member.id===result.assignee_id)))fail('Eine neue Verantwortlichkeit benötigt ein aktuelles Mitglied dieses Projekts.');return result;
}
export async function milestoneRecord(value,project,identifier=null){
  if(!keys(value,recordKeys)||value.schema_version!==1||!hex(value.id)||!hex(project)||value.project_id!==project||identifier&&value.id!==identifier||!Number.isSafeInteger(value.revision)||value.revision<1||value.revision>=2**31||!hex(value.created_by)||!hex(value.updated_by)||!['created_at','updated_at'].every(name=>typeof value[name]==='string'&&/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value[name])&&Number.isFinite(Date.parse(value[name])))||Date.parse(value.updated_at)<Date.parse(value.created_at)||typeof value.content_hash!=='string'||!/^[a-f0-9]{64}$/.test(value.content_hash))fail('Die Meilensteinfassung ist unvollständig oder gehört zu einem anderen Projekt.');
  const normalized=milestoneValues(value,[],value);for(const field of fields)if(value[field]!==normalized[field])fail('Die Meilensteinfassung enthält nicht bestätigte Angaben.');
  const {content_hash,...raw}=value;if(await milestoneHash(raw)!==content_hash)fail('Die Originalprüfsumme des Meilensteins stimmt nicht.');return value;
}
export async function milestoneList(value,project){
  if(!keys(value,['schema_version','project_id','items'])||value.schema_version!==1||value.project_id!==project||!Array.isArray(value.items)||new Set(value.items.map(item=>item?.id)).size!==value.items.length)fail('Die Meilensteinliste gehört nicht vollständig zum geöffneten Projekt.');
  await Promise.all(value.items.map(item=>milestoneRecord(item,project)));return value.items;
}
export async function milestoneHistory(value,project,current){
  await milestoneRecord(current,project);
  if(!keys(value,['schema_version','project_id','milestone_id','items'])||value.schema_version!==1||value.project_id!==project||value.milestone_id!==current.id||!Array.isArray(value.items)||value.items.length!==current.revision)fail('Der Meilensteinverlauf ist unvollständig.');
  await Promise.all(value.items.map(async(item,index)=>{await milestoneRecord(item,project,current.id);if(item.revision!==index+1||item.created_at!==current.created_at||item.created_by!==current.created_by)fail('Der Meilensteinverlauf enthält nicht zusammengehörige Fassungen.');}));
  if(!same(value.items.at(-1),current))fail('Der Meilenstein wurde inzwischen geändert. Bitte den Verlauf neu laden.');return value.items;
}
export async function milestoneReceipt(value,project,identifier,body,{original=null,actorId}={}){
  await milestoneRecord(value,project,identifier);
  if(value.revision!==(body.revision??0)+1||body.schema_version!==1||!hex(actorId)||value.updated_by!==actorId)fail('Die angenommene Meilensteinversion stimmt nicht mit dem Auftrag überein.');
  if(identifier){
    await milestoneRecord(original,project,identifier);
    if(original.revision!==body.revision||value.created_by!==original.created_by||value.created_at!==original.created_at)fail('Die bestätigte Änderung ersetzt die ursprünglichen Anlageangaben.');
  }else if(value.created_by!==actorId||value.created_at!==value.updated_at)fail('Die Anlagebestätigung gehört nicht zum ursprünglichen Auftrag.');
  for(const field of fields)if(value[field]!==body[field])fail('Die Meilensteinantwort bestätigt nicht die ursprüngliche Eingabe.');return value;
}
export function milestoneRights(caps,project){
  const available=caps?.project_id===project&&caps?.features?.includes('project_milestones')===true&&caps?.capabilities?.includes('business_project_milestones')===true;
  const read=available&&caps.permissions?.includes('planning.read')===true;
  return {read,write:read&&caps.permissions.includes('projects.manage')&&caps.readonly===false&&caps.organization?.modules?.planning?.enabled!==false};
}
export async function milestoneContext(api,project,{write=false}={}){
  if(!hex(project))fail('Bitte ein gültiges Projekt öffnen.');
  const caps=await api.get('/business/capabilities?project_id='+project),rights=milestoneRights(caps,project);
  if(!rights.read||write&&!rights.write)throw new ApiError('Für diese Meilensteine besteht aktuell kein '+(write?'Schreib':'Lese')+'recht.',403);
  const [workspace,user]=await Promise.all([api.get(`/projects/${project}/workspace`),api.get('/me')]);
  if(workspace?.project?.id!==project||!Array.isArray(workspace.team)||workspace.team.some(member=>!hex(member.id)||typeof member.email!=='string'||typeof member.role!=='string')||new Set(workspace.team.map(member=>member.id)).size!==workspace.team.length)fail('Das aktuelle Projektteam konnte nicht sicher gelesen werden.');
  if(!hex(user?.id))fail('Der aktuell angemeldete Benutzer konnte nicht sicher gelesen werden.');
  return {caps,rights,team:workspace.team,user};
}
export function milestoneCommandPath(path){return /^\/business\/projects\/([a-f0-9]{32})\/milestones(?:\/([a-f0-9]{32}))?$/.exec(path||'');}
export async function milestonePendingAuthorize(api,operation){
  const match=milestoneCommandPath(operation?.path),body=api.pendingCommandValues(operation?.key,operation?.path);
  if(!match||operation.key!==`milestone-save-${match[2]||'new-'+match[1]}`||!keys(body,['schema_version',...fields,...(match[2]?['revision']:[])])||body.schema_version!==1)fail('Der ursprüngliche Meilensteinauftrag ist nicht mehr vollständig verfügbar.');
  await milestoneContext(api,match[1],{write:true});
  if(match[2])await milestoneRecord(await api.get(operation.path),match[1],match[2]);
  const normalized=milestoneValues(body,[],body);for(const field of fields)if(body[field]!==normalized[field])fail('Der ursprüngliche Meilensteinauftrag wurde verändert.');
  if(match[2]&&(!Number.isSafeInteger(body.revision)||body.revision<1||body.revision>=2**31))fail('Die ursprüngliche Ausgangsversion fehlt.');return true;
}

export function projectMilestonesUi(h){
  const {api,el,button,panel,row,rows,notice,form,field,dialog,formatDate,action,refresh,stamp}=h;
  const path=(project,identifier)=>`/business/projects/${project}/milestones${identifier?'/'+identifier:''}`;
  const status=value=>MILESTONE_STATUSES.find(([key])=>key===value)?.[1]||value;
  const label=(item,team)=>item.assignee_id?(team.find(member=>member.id===item.assignee_id)?.email||'Nicht mehr im aktuellen Projektteam'):'Nicht zugewiesen';
  const describe=(item,team)=>[status(item.status),item.due_date?'Fällig '+formatDate(item.due_date):'Ohne Fälligkeit',label(item,team),`Version ${item.revision}`].join(' · ');
  async function currentLoad(start,operation){
    try{const result=await operation();return stamp()===start?result:null;}
    catch(error){if(stamp()===start)throw error;return null;}
  }
  async function edit(project,identifier=null,target=null){
    const start=stamp();const loaded=await currentLoad(start,async()=>{
      const [context,raw]=await Promise.all([milestoneContext(api,project,{write:true}),identifier?api.get(path(project,identifier)):null]);
      return {context,item:raw?await milestoneRecord(raw,project,identifier):null};
    });if(!loaded)return;const {context,item}=loaded;
    let ownerStamp,editor;const alive=()=>editor.isConnected&&stamp()===ownerStamp&&document.visibilityState!=='hidden';
    const choices=[['','Nicht zugewiesen'],...context.team.map(member=>[member.id,member.email])];
    if(item?.assignee_id&&!context.team.some(member=>member.id===item.assignee_id))choices.push([item.assignee_id,'Nicht mehr im aktuellen Projektteam (unverändert)']);
    editor=form('',[
      field('title','Meilenstein','text',item?.title||'',{required:true,maxLength:400,help:'Höchstens 200 Zeichen.'}),
      field('status','Status','select',target||item?.status||'planned',{options:MILESTONE_STATUSES}),
      field('due_date','Fällig am','date',item?.due_date||'',{min:'1900-01-01',max:'2200-12-31'}),
      field('assignee_id','Verantwortlich','select',item?.assignee_id||'',{options:choices,keepEmpty:true}),
      field('details','Beschreibung des Projektziels','textarea',item?.details||'',{maxLength:20000,help:'Höchstens 10.000 Zeichen.'})
    ],async(values,key)=>{
      if(!alive())return;
      try{
        const url=path(project,identifier),pending=api.pendingCommandValues(key,url);
        const fresh=await milestoneContext(api,project,{write:true});if(!alive())return;
        const current=identifier?await milestoneRecord(await api.get(url),project,identifier):null;if(!alive())return;
        if(!pending&&current&&!same(current,item))throw new ApiError('Der Meilenstein wurde inzwischen geändert. Die aktuelle Fassung erneut öffnen und die Eingabe vergleichen.',409);
        const body={schema_version:1,...milestoneValues(values,pending?context.team:fresh.team,item),...(item?{revision:item.revision}:{})};
        const result=await api.mutate(key,url,body,{validate:(value,command)=>milestoneReceipt(value,project,identifier,command,{original:item,actorId:fresh.user.id})});
        return alive()?result:undefined;
      }catch(error){
        if(alive()&&[403,404].includes(error.status)){editor.replaceChildren(notice('Dieser Meilenstein ist für Ihren Zugang nicht mehr verfügbar. Eine offene Antwort bleibt zur unveränderten Klärung erhalten.','error'));return undefined;}
        if(alive())throw error;return undefined;
      }
    },{key:`milestone-save-${identifier||'new-'+project}`,after:()=>refresh(),description:item?`Änderung an Version ${item.revision}. Frühere Fassungen bleiben im Verlauf erhalten.`:'Ein Meilenstein beschreibt ein Projektziel. „Erreicht“ ist eine manuelle Statusbestätigung.'});
    editor.setAttribute('data-project-milestones','');dialog(item?'Meilenstein bearbeiten':'Neuer Meilenstein',editor);ownerStamp=stamp();
  }
  async function history(project,identifier){
    const start=stamp();const loaded=await currentLoad(start,async()=>{
      const [context,raw,record]=await Promise.all([milestoneContext(api,project),api.get(path(project,identifier)+'/history'),api.get(path(project,identifier))]);
      return {context,record,items:await milestoneHistory(raw,project,record)};
    });if(!loaded)return;const {context,record,items}=loaded;
    const content=el('div',{'data-project-milestones':'',class:'stack'},notice('Gespeicherte Fassungen bleiben unverändert. Die Zuordnung verwendet die damalige Benutzerkennung; angezeigte Teamadressen sind heutige Bezeichnungen.'),
      ...items.slice().reverse().map(item=>panel(`Version ${item.revision}${item.revision===record.revision?' · aktuell':''}`,row(item.title,describe(item,context.team)),el('p',{class:'break-word'},item.details||'Ohne Beschreibung'),el('p',{class:'caption'},'Gespeichert '+formatDate(item.updated_at,true)),
        item.assignee_id?el('p',{class:'caption break-word'},'Verantwortliche Benutzerkennung: '+item.assignee_id):null,el('details',{},el('summary',{},'Originalnachweis'),el('p',{class:'caption break-word'},'Meilenstein: '+item.id),el('p',{class:'caption break-word'},'Prüfsumme: '+item.content_hash)))));
    dialog('Meilensteinverlauf',content);
  }
  async function view(project){
    const context=await milestoneContext(api,project),items=await milestoneList(await api.get(path(project)),project);
    const count=type=>items.filter(item=>item.status===type).length;
    return panel('Meilensteine',el('p',{class:'muted'},`Geplant: ${count('planned')} · Erreicht: ${count('achieved')} · Entfallen: ${count('cancelled')}`),context.rights.write?button('Meilenstein hinzufügen',()=>action(()=>edit(project)),'primary'):null,
      rows(items,item=>row(item.title,describe(item,context.team),[
        context.rights.write?button('Bearbeiten',()=>action(()=>edit(project,item.id)),'small'):null,
        context.rights.write?button(item.status==='planned'?'Als erreicht markieren':'Wieder planen',()=>action(()=>edit(project,item.id,item.status==='planned'?'achieved':'planned')),'small'):null,
        button('Verlauf',()=>action(()=>history(project,item.id)),'small')],item.details),'Noch keine Meilensteine vorhanden.'));
  }
  return {view,edit,history};
}
