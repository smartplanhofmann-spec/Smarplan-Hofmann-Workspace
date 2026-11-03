/* Foreground-only push-to-talk. No audio, transcript or credential persistence. */
export const speechLimit={seconds:60,sampleRate:16000,maxAudioBytes:1920044,maxEncodedBytes:4000000};
export function speechWav(samples){
  if(!(samples instanceof Float32Array)||!samples.length||samples.length>speechLimit.seconds*speechLimit.sampleRate)throw new Error('Aufnahme muss zwischen einem Sample und 60 Sekunden lang sein.');
  const bytes=new Uint8Array(44+samples.length*2),view=new DataView(bytes.buffer);
  const ascii=(offset,value)=>{for(let index=0;index<value.length;index++)bytes[offset+index]=value.charCodeAt(index);};
  ascii(0,'RIFF');view.setUint32(4,bytes.length-8,true);ascii(8,'WAVE');ascii(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);ascii(36,'data');view.setUint32(40,samples.length*2,true);
  for(let index=0;index<samples.length;index++){if(!Number.isFinite(samples[index]))throw new Error('Die Aufnahme enthält ungültige Audiodaten.');const value=Math.max(-1,Math.min(1,samples[index]));view.setInt16(44+index*2,Math.round(value*(value<0?32768:32767)),true);}return bytes;
}
export async function decodeSpeech(blob){
  const Audio=globalThis.AudioContext||globalThis.webkitAudioContext,Offline=globalThis.OfflineAudioContext||globalThis.webkitOfflineAudioContext;
  if(!Audio||!Offline)throw new Error('Dieser Browser kann die Aufnahme nicht sicher in Sprache umwandeln.');
  const decoder=new Audio();let decoded;
  try{decoded=await decoder.decodeAudioData(await blob.arrayBuffer());}finally{await decoder.close();}
  if(!decoded.length||decoded.duration>60||decoded.numberOfChannels>8)throw new Error('Die Aufnahme überschreitet die zulässige Dauer oder Kanalzahl.');
  const length=Math.round(decoded.duration*16000),offline=new Offline(1,length,16000),source=offline.createBufferSource();source.buffer=decoded;source.connect(offline.destination);source.start();const normalized=await offline.startRendering();return speechWav(normalized.getChannelData(0));
}
export function speechResult(value,{requestId,projectId,contextId,contextSha256}){
  if(value?.id!==requestId||value.project_id!==projectId||value.context_id!==contextId||value.context_sha256!==contextSha256||value.status!=='completed'||value.audio_persisted!==false||value.transcript_persisted!==false||value.retry_automatically!==false||typeof value.text!=='string'||!value.text.trim()||value.text.length>4000||!/^[a-f0-9]{64}$/.test(value.audio_sha256||''))throw new Error('Die Sprachantwort bestätigt den ursprünglichen Auftrag nicht.');return value.text;
}
export class SpeechCapture{
  constructor({getMedia=()=>navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true},video:false}),createRecorder=stream=>{
    const type=['audio/webm;codecs=opus','audio/mp4','audio/webm'].find(type=>MediaRecorder.isTypeSupported(type));if(!type)throw new Error('Das Aufnahmeformat dieses Browsers wird nicht unterstützt.');return new MediaRecorder(stream,{mimeType:type,audioBitsPerSecond:64000});
  },decode=decodeSpeech,allowed=()=>true,changed=()=>{},setTimer=(fn,ms)=>setTimeout(fn,ms),clearTimer=id=>clearTimeout(id)}={}){
    Object.assign(this,{getMedia,createRecorder,decode,allowed,changed,setTimer,clearTimer});this.epoch=0;this.phase='idle';this.message='';this.audio=null;this.timer=null;this.stream=null;this.recorder=null;this.chunks=[];this.size=0;this.closed=false;
  }
  publish(){if(!this.closed)this.changed(this);}
  erase(){this.audio?.fill(0);this.audio=null;this.chunks=[];this.size=0;}
  release(){if(this.timer!==null)this.clearTimer(this.timer);this.timer=null;for(const track of this.stream?.getTracks()||[])track.stop();this.stream=null;}
  async start(){
    if(this.closed||!this.allowed()||!['idle','error'].includes(this.phase))return;
    const epoch=++this.epoch;this.erase();this.phase='requesting';this.message='Mikrofonfreigabe wird geprüft. Zum Sprechen gedrückt halten.';this.publish();
    try{const stream=await this.getMedia();if(this.closed||epoch!==this.epoch||!this.allowed()){for(const track of stream.getTracks())track.stop();return;}
      this.stream=stream;this.recorder=this.createRecorder(stream);const recorder=this.recorder;
      recorder.addEventListener('dataavailable',event=>{if(epoch!==this.epoch||!event.data?.size)return;this.size+=event.data.size;if(this.size>speechLimit.maxEncodedBytes){this.cancel('Die Aufnahme ist zu groß.');return;}this.chunks.push(event.data);});
      recorder.addEventListener('error',()=>this.cancel('Die Mikrofonaufnahme wurde unterbrochen.'));
      recorder.addEventListener('stop',async()=>{this.release();if(this.closed||epoch!==this.epoch||this.phase!=='processing')return;try{const audio=await this.decode(new Blob(this.chunks,{type:recorder.mimeType}));this.chunks=[];this.size=0;if(this.closed||epoch!==this.epoch||!this.allowed()){audio.fill(0);return;}if(!(audio instanceof Uint8Array)||audio.length>speechLimit.maxAudioBytes||audio.length<=44)throw new Error('Die Aufnahme ist leer oder überschreitet 60 Sekunden.');this.audio=audio;this.phase='ready';this.message='Aufnahme beendet. Erst nach Ihrer Bestätigung wird sie zur Spracherkennung übertragen.';this.publish();}catch(error){if(epoch===this.epoch)this.cancel(error.message||'Die Aufnahme konnte nicht gelesen werden.');}});
      for(const track of stream.getTracks())track.addEventListener?.('ended',()=>{if(this.phase==='recording')this.cancel('Die Mikrofonaufnahme wurde beendet.');});
      recorder.start(250);this.phase='recording';this.message='Aufnahme läuft · zum Beenden loslassen · höchstens 60 Sekunden';this.timer=this.setTimer(()=>this.stop(),60000);this.publish();
    }catch(error){if(epoch===this.epoch)this.cancel(error.name==='NotAllowedError'?'Mikrofonzugriff nicht freigegeben. Die Texteingabe bleibt verfügbar.':error.message||'Mikrofonaufnahme nicht verfügbar.');}
  }
  stop(){if(this.phase==='requesting'){this.cancel('Vor dem Start losgelassen. Nach der Mikrofonfreigabe erneut gedrückt halten.');return;}if(this.phase!=='recording')return;this.phase='processing';this.message='Aufnahme beendet. Audiodaten werden lokal geprüft.';if(this.timer!==null)this.clearTimer(this.timer);this.timer=null;try{this.recorder.stop();}catch{this.cancel('Die Aufnahme konnte nicht beendet werden.');}this.publish();}
  cancel(message='Aufnahme verworfen.'){
    this.epoch++;this.erase();this.phase='error';this.message=message;try{if(this.recorder?.state==='recording'||this.recorder?.state==='paused')this.recorder.stop();}catch{}this.release();this.publish();
  }
  dispose(){this.cancel('');this.closed=true;this.changed=()=>{};}
}
function base64(bytes){let value='';for(let offset=0;offset<bytes.length;offset+=16384)value+=String.fromCharCode(...bytes.subarray(offset,offset+16384));return btoa(value);}
export function speechDraftDialog(h,{project,context,provider,onDraft}){
  const {el,button,dialog,notice,api,biz}=h,stamp=h.stamp(),requestId=h.requestId();let disposed=false,requestStarted=false,transcript='',statusText='';
  const allowed=()=>!disposed&&h.allowed(project)&&h.writable(project)&&h.stamp()===stamp;
  const message=el('p',{role:'status'}),hold=button('Zum Sprechen gedrückt halten',event=>{if(event.detail===0){if(capture.phase==='recording')capture.stop();else capture.start();}},'primary'),consent=el('input',{type:'checkbox','aria-label':'Ich bestätige die Übertragung dieser Aufnahme an den eingerichteten Sprachanbieter.'}),editor=el('textarea',{'aria-label':'Erkannter Textentwurf',rows:6,maxLength:4000});
  const body=el('div',{class:'stack assistant-workspace','data-assistant-project':project},notice(`Sprachanbieter: ${provider.model} · ${provider.endpoint}. Aufnahme nur während des Gedrückthaltens, höchstens 60 Sekunden; Audio bleibt ausschließlich im Arbeitsspeicher.`),hold,message);
  const capture=new SpeechCapture({allowed,changed:render});
  const transfer=button('Aufnahme in Text umwandeln',async()=>{
    if(!allowed()||capture.phase!=='ready'||consent.checked!==true||requestStarted)return;
    requestStarted=true;capture.phase='sending';capture.message='Die bestätigte Aufnahme wird einmalig übertragen. Ein begonnener Anbieteraufruf lässt sich möglicherweise nicht zurückrufen.';render();
    let values;
    try{const current=await api.get(biz('/assistant/contexts/'+context.id));if(!allowed()||current.project_id!==project||current.sha256!==context.sha256||current.current!==true)throw new Error('Datenbasis oder Berechtigung wurde geändert. Bitte neu auswählen.');
      values={request_id:requestId,context_id:context.id,data_transfer_confirmed:true,audio_base64:base64(capture.audio)};capture.erase();
      const result=await api.post(biz('/assistant/speech/transcribe'),values);values.audio_base64='';if(!allowed())return;transcript=speechResult(result,{requestId,projectId:project,contextId:context.id,contextSha256:context.sha256});editor.value=transcript;capture.phase='completed';capture.message='Erkannten Text prüfen und bearbeiten. Es wurde noch keine Chatnachricht gesendet.';
    }catch(error){if(allowed()){capture.phase='unknown';capture.message='Keine bestätigte Sprachantwort. Ein Anbieteraufruf kann bereits erfolgt sein. Den Status prüfen; dieselbe Aufnahme wird nicht erneut gesendet.';statusText=error.message||'';}}
    finally{if(values)values.audio_base64='';capture.erase();if(allowed())render();}
  },'primary');
  const status=button('Status des begonnenen Aufrufs prüfen',async()=>{if(!allowed()||!requestStarted)return;try{const value=await api.get(biz('/assistant/speech/requests/'+requestId));if(!allowed())return;if(value.id!==requestId||value.project_id!==project||value.context_id!==context.id||value.retry_automatically!==false||value.transcript_persisted!==false)throw new Error('Status bestätigt den ursprünglichen Auftrag nicht.');statusText='Dokumentierter Status: '+({started:'Begonnen',completed:'Anbieterantwort erhalten; der Text wurde nicht gespeichert',failed:'Fehlgeschlagen',interrupted:'Unterbrochen'}[value.status]||'Unbestätigt')+'. Für einen neuen Versuch eine neue Aufnahme ausdrücklich starten.';}catch(error){if(allowed())statusText=error.message||'Status nicht verfügbar.';}if(allowed())render();},'small');
  const accept=button('Textentwurf übernehmen',()=>{if(allowed()&&editor.value.trim()&&editor.value.length<=4000){const text=editor.value.trim();dispose();h.closeModal();onDraft(text);}},'primary');
  const controls=el('div',{class:'stack'},el('label',{class:'field check'},'Ich bestätige die Übertragung dieser Aufnahme an den eingerichteten Sprachanbieter.',consent),transfer),result=el('div',{class:'stack'},el('label',{class:'field'},'Erkannter Textentwurf',editor),accept),pending=el('div',{class:'stack'},status,el('p',{class:'speech-status'}));
  body.append(controls,result,pending,button('Aufnahme und Entwurf verwerfen',()=>{dispose();h.closeModal();},'small'));
  function render(){if(disposed)return;message.textContent=capture.message;hold.disabled=!allowed()||!['idle','error','requesting','recording'].includes(capture.phase)||requestStarted;controls.hidden=capture.phase!=='ready';consent.disabled=requestStarted;transfer.disabled=!consent.checked||requestStarted;result.hidden=capture.phase!=='completed';pending.hidden=capture.phase!=='unknown';pending.querySelector('p').textContent=statusText;}
  consent.addEventListener('change',render);
  hold.addEventListener('pointerdown',event=>{if(event.button!==0||hold.disabled)return;event.preventDefault();hold.setPointerCapture(event.pointerId);capture.start();});hold.addEventListener('pointerup',()=>capture.stop());hold.addEventListener('pointercancel',()=>capture.cancel());hold.addEventListener('keydown',event=>{if([' ','Enter'].includes(event.key)&&!event.repeat){event.preventDefault();capture.start();}});hold.addEventListener('keyup',event=>{if([' ','Enter'].includes(event.key)){event.preventDefault();capture.stop();}});
  const hidden=()=>{if(document.hidden)dispose();},pagehide=()=>dispose();document.addEventListener('visibilitychange',hidden);window.addEventListener('pagehide',pagehide);
  const observer=new MutationObserver(()=>{if(!body.isConnected)dispose();});
  function dispose(){if(disposed)return;disposed=true;capture.dispose();editor.value='';transcript='';consent.checked=false;document.removeEventListener('visibilitychange',hidden);window.removeEventListener('pagehide',pagehide);observer.disconnect();body.replaceChildren(notice('Aufnahme und Entwurf wurden verworfen.'));}
  dialog('Sprache als Textentwurf',body);observer.observe(document.body,{childList:true,subtree:true});render();return dispose;
}
