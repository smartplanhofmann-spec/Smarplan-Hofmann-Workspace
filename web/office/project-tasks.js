import {ApiError} from './office.js';

export const TASK_STATUSES=[['todo','Offen'],['in_progress','In Bearbeitung'],['done','Erledigt'],['cancelled','Abgebrochen']];
export const TASK_PRIORITIES=[['normal','Normal'],['high','Hoch']];
const id=/^[a-f0-9]{32}$/,fields=['title','details','status','priority','due_date','assignee_id'];
const fail=message=>{throw new ApiError(message,409);};
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
function text(value,max,required=false){
  if(typeof value!=='string'||value.length>max||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value)||required&&!value.trim())fail('Bitte gültige Aufgabendaten eingeben.');
  return value.trim();
}
function day(value){
  if(value===''||value===null)return null;
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||value<'1900-01-01'||value>'2200-12-31')fail('Bitte ein gültiges Fälligkeitsdatum von 1900 bis 2200 eingeben.');
  const date=new Date(value+'T00:00:00Z');if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==value)fail('Bitte ein gültiges Fälligkeitsdatum eingeben.');return value;
}
export function taskValues(values,team,current=null){
  if(!values||!Array.isArray(team))fail('Aufgabe und Projektteam zuerst neu laden.');
  const result={title:text(values.title,200,true),details:text(values.details,10000),status:values.status,priority:values.priority,due_date:day(values.due_date??null),assignee_id:values.assignee_id||null};
  if(!TASK_STATUSES.some(([value])=>value===result.status)||!TASK_PRIORITIES.some(([value])=>value===result.priority))fail('Unbekannter Aufgabenstatus oder unbekannte Priorität.');
  if(result.assignee_id!==null&&(!id.test(result.assignee_id)||result.assignee_id!==current?.assignee_id&&!team.some(member=>member.id===result.assignee_id)))fail('Die neu zugewiesene Person muss zum aktuellen Projektteam gehören.');
  return result;
}
export function taskRecord(value,project,identifier=null){
  if(!value||!id.test(project)||!id.test(value.id)||value.project_id!==project||identifier&&value.id!==identifier||!Number.isSafeInteger(value.revision)||value.revision<1||!id.test(value.created_by)||!id.test(value.updated_by)||typeof value.created_at!=='string'||!Number.isFinite(Date.parse(value.created_at))||typeof value.updated_at!=='string'||!Number.isFinite(Date.parse(value.updated_at)))fail('Die Aufgabenfassung gehört nicht zum aktuellen Projekt oder ist unvollständig.');
  const normalized=taskValues(value,[],value);for(const name of fields)if(value[name]!==normalized[name])fail('Die gespeicherte Aufgabenfassung ist unvollständig.');return value;
}
export function taskHistory(value,project,current){
  taskRecord(current,project);const items=value?.items;
  if(!Array.isArray(items)||items.length!==current.revision)fail('Der Aufgabenverlauf ist unvollständig. Bitte neu laden.');
  items.forEach((item,index)=>{taskRecord(item,project,current.id);if(item.revision!==index+1||item.created_by!==current.created_by||item.created_at!==current.created_at)fail('Der Aufgabenverlauf ist widersprüchlich.');});
  if(!same(items.at(-1),current))fail('Die Aufgabe wurde inzwischen geändert. Bitte den Verlauf neu laden.');return items;
}
export function taskReceipt(value,project,identifier,body){
  try{
    taskRecord(value,project,identifier);if(value.revision!==(body.revision??0)+1)fail('Die bestätigte Aufgabenrevision stimmt nicht mit dem Auftrag überein.');
    for(const name of fields)if(value[name]!==body[name])fail('Die bestätigte Aufgabe weicht von der ursprünglichen Eingabe ab.');return value;
  }catch(error){throw new ApiError('Die Aufgabenantwort ist nicht sicher bestätigt. Der ursprüngliche Auftrag bleibt offen: '+error.message,502);}
}
export async function taskContext(api,project,{write=false}={}){
  if(!id.test(project))fail('Bitte ein gültiges Projekt öffnen.');
  const [workspace,user,caps]=await Promise.all([api.get(`/projects/${project}/workspace`),api.get('/me'),api.get('/business/capabilities')]);
  if(workspace?.project?.id!==project||!Array.isArray(workspace.team)||workspace.team.some(member=>!id.test(member.id)||typeof member.email!=='string')||new Set(workspace.team.map(member=>member.id)).size!==workspace.team.length)fail('Das aktuelle Projektteam konnte nicht eindeutig gelesen werden.');
  if(write&&(caps.readonly!==false||!['owner','manager','technician'].includes(user.role)))throw new ApiError('Für diese Aufgabe besteht aktuell kein Schreibrecht.',403);
  return {team:workspace.team,user,caps};
}
export async function taskPendingAuthorize(api,operation){
  try{
  const match=/^\/projects\/([a-f0-9]{32})\/tasks(?:\/([a-f0-9]{32}))?$/.exec(operation?.path||'');
  const body=api.pendingCommandValues(operation?.key,operation?.path);
  if(!match||!body||operation.key!==`project-task-${match[2]||'new-'+match[1]}`)fail('Der ursprüngliche Aufgabenauftrag ist nicht mehr verfügbar.');
  await taskContext(api,match[1],{write:true});
  if(match[2])taskRecord(await api.get(operation.path),match[1],match[2]);
  // A previously accepted reply can be older than today's task/team. The
  // server replays only the original request after checking today's access.
  if(!same(Object.keys(body).sort(),[...fields,...(match[2]?['revision']:[])].sort()))fail('Der ursprüngliche Aufgabenauftrag ist unvollständig.');
  const normalized=taskValues(body,[],body);for(const field of fields)if(body[field]!==normalized[field])fail('Der ursprüngliche Aufgabenauftrag ist verändert.');
  if(match[2]&&(!Number.isSafeInteger(body.revision)||body.revision<1))fail('Die ursprüngliche Aufgabenrevision fehlt.');
  return true;
  }catch(error){if(error.status===409)throw new ApiError('Der Aufgabenauftrag bleibt unbestätigt: '+error.message,502);throw error;}
}

export function projectTasksUi(h){
  const {api,el,button,panel,row,rows,notice,form,field,dialog,formatDate,action,refresh,stamp,writable}=h;
  const status=value=>TASK_STATUSES.find(([key])=>key===value)?.[1]||value;
  function describe(item,team){return [status(item.status),TASK_PRIORITIES.find(([key])=>key===item.priority)?.[1],item.due_date?'Fällig '+formatDate(item.due_date):'Ohne Fälligkeit',item.assignee_id?(team.find(member=>member.id===item.assignee_id)?.email||'Nicht mehr im aktuellen Projektteam'):'Nicht zugewiesen',`Version ${item.revision}`].join(' · ');}
  async function edit(project,identifier=null,target=null){
    const start=stamp();const [context,item]=await Promise.all([taskContext(api,project,{write:true}),identifier?api.get(`/projects/${project}/tasks/${identifier}`):null]);
    if(stamp()!==start)return;if(item)taskRecord(item,project,identifier);
    let ownerStamp,editor;const alive=()=>editor.isConnected&&stamp()===ownerStamp&&document.visibilityState!=='hidden';
    const choices=[['','Nicht zugewiesen'],...context.team.map(member=>[member.id,member.email])];
    if(item?.assignee_id&&!context.team.some(member=>member.id===item.assignee_id))choices.push([item.assignee_id,'Nicht mehr im aktuellen Projektteam (unverändert)']);
    editor=form('',[
      field('title','Aufgabe','text',item?.title||'',{required:true,maxLength:200}),
      field('status','Status','select',target||item?.status||'todo',{options:TASK_STATUSES}),
      field('priority','Priorität','select',item?.priority||'normal',{options:TASK_PRIORITIES}),
      field('due_date','Fällig am','date',item?.due_date||'',{min:'1900-01-01',max:'2200-12-31'}),
      field('assignee_id','Verantwortlich','select',item?.assignee_id||'',{options:choices,keepEmpty:true}),
      field('details','Beschreibung','textarea',item?.details||'',{maxLength:10000})
    ],async(values,key)=>{
      if(!alive())return;
      try{
        const path=`/projects/${project}/tasks${identifier?'/'+identifier:''}`,pending=api.pendingCommandValues(key,path);
        const fresh=await taskContext(api,project,{write:true});if(!alive())return;
        const current=identifier?taskRecord(await api.get(path),project,identifier):null;if(!alive())return;
        if(!pending&&current&&!same(current,item))fail('Die Aufgabe wurde inzwischen geändert. Dialog schließen und die aktuelle Aufgabe erneut öffnen; Ihre Eingabe bleibt hier zum Vergleich erhalten.');
        const body={...taskValues(values,pending?context.team:fresh.team,item),...(item?{revision:item.revision}:{})};
        const result=await api.mutate(key,path,body,{validate:(value,command)=>taskReceipt(value,project,identifier,command)});
        return alive()?result:undefined;
      }catch(error){
        if(alive()&&[403,404].includes(error.status)){editor.replaceChildren(notice('Diese Aufgabe ist für Ihren Zugang nicht mehr verfügbar. Eine offene Antwort bleibt zur unveränderten Klärung erhalten.','error'));return undefined;}
        if(alive())throw error;return undefined;
      }
    },{key:`project-task-${identifier||'new-'+project}`,after:()=>refresh(),description:item?`Änderung an Version ${item.revision}. Frühere Fassungen bleiben im Verlauf erhalten.`:'Die Aufgabe gehört zu diesem Projekt. Verantwortliche stammen aus dem aktuellen Projektteam.'});
    editor.setAttribute('data-project-tasks','');dialog(item?'Aufgabe bearbeiten':'Neue Aufgabe',editor);ownerStamp=stamp();
  }
  async function history(project,identifier){
    const start=stamp();const [context,current,history]=await Promise.all([taskContext(api,project),api.get(`/projects/${project}/tasks/${identifier}`),api.get(`/projects/${project}/tasks/${identifier}/history`)]);
    if(stamp()!==start)return;const items=taskHistory(history,project,current);
    const content=el('div',{'data-project-tasks':'',class:'stack'},notice('Gespeicherte Fassungen bleiben unverändert. Änderungen werden nur an der aktuellen Aufgabe vorgenommen.'),
      ...items.slice().reverse().map(item=>panel(`Version ${item.revision}${item.revision===current.revision?' · aktuell':''}`,row(item.title,describe(item,context.team)),el('p',{class:'break-word'},item.details||'Ohne Beschreibung'),el('p',{class:'caption'},'Gespeichert '+formatDate(item.updated_at,true)))));
    dialog('Aufgabenverlauf',content);
  }
  async function view(project){
    const [context,values]=await Promise.all([taskContext(api,project),api.get(`/projects/${project}/tasks`)]);
    const items=Array.isArray(values)?values:values?.items;if(!Array.isArray(items))fail('Die Aufgabenliste ist unvollständig.');items.forEach(item=>taskRecord(item,project));
    const canWrite=writable()&&context.caps.readonly===false&&['owner','manager','technician'].includes(context.user.role);
    return panel('Aufgaben',canWrite?button('Aufgabe hinzufügen',()=>action(()=>edit(project)),'primary'):null,
      rows(items,item=>row(item.title,describe(item,context.team),[
        canWrite?button('Bearbeiten',()=>action(()=>edit(project,item.id)),'small'):null,
        canWrite?button(['done','cancelled'].includes(item.status)?'Wieder öffnen':'Erledigt',()=>action(()=>edit(project,item.id,['done','cancelled'].includes(item.status)?'todo':'done')),'small'):null,
        button('Verlauf',()=>action(()=>history(project,item.id)),'small')],item.details),'Noch keine Aufgaben vorhanden.'));
  }
  return {view,edit,history};
}
