'use strict';
const $=id=>document.getElementById(id);
let current='',offset=0,total=0,items=[],upload=null,loadSequence=0;
const PAGE=200;
const join=(a,b)=>a?`${a}/${b}`:b;
const url=(route,path='')=>`/api/v1/${route}?path=${encodeURIComponent(path)}`;
function message(text){$('message').textContent=text;$('message').hidden=!text;}
async function request(target,options={}){
 const response=await fetch(target,{credentials:'same-origin',...options});
 const type=response.headers.get('Content-Type')||'';
 if(!type.includes('application/json'))throw Error('Sesión vencida o respuesta inesperada. Recarga para iniciar sesión.');
 const data=await response.json();if(!response.ok)throw Error(data.error||`Error ${response.status}`);return data;
}
function button(label,action,cls=''){const e=document.createElement('button');e.textContent=label;e.className=cls;e.addEventListener('click',action);return e;}
function size(n){if(n<1024)return `${n} B`;const units=['KB','MB','GB','TB'];let i=-1;do{n/=1024;i++;}while(n>=1024&&i<units.length-1);return `${n.toFixed(1)} ${units[i]}`;}
function breadcrumbs(){
 $('breadcrumbs').replaceChildren(button('⌂ Mi espacio',()=>navigate('')));
 let path='';for(const part of current.split('/').filter(Boolean)){path=join(path,part);const dest=path;const sep=document.createElement('span');sep.textContent='/';$('breadcrumbs').append(sep,button(part,()=>navigate(dest)));}
}
function download(path){const a=document.createElement('a');a.href=url('content',path);a.download=path.split('/').pop();a.click();}
async function rename(item){const next=prompt('Nuevo nombre (o ruta relativa completa dentro del espacio):',join(current,item.name));if(!next||next===join(current,item.name))return;
 try{await request('/api/v1/entries',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:join(current,item.name),destination:next})});await load();message('Nombre actualizado.');}catch(e){message(e.message);}}
async function remove(item){if(!confirm(`¿Eliminar "${item.name}"? Las carpetas deben estar vacías. La réplica no garantiza recuperar este cambio si aún no se ha ejecutado.`))return;
 try{await request(url('entries',join(current,item.name)),{method:'DELETE'});await load();message('Elemento eliminado.');}catch(e){message(e.message);}}
function render(){
 const list=$('file-list');list.replaceChildren();const q=$('search').value.toLocaleLowerCase();const visible=items.filter(i=>i.name.toLocaleLowerCase().includes(q));
 for(const item of visible){const tr=document.createElement('tr'),td=document.createElement('td');const name=button('',()=>item.type==='directory'?navigate(join(current,item.name)):download(join(current,item.name)),'filename');
 const icon=document.createElement('span');icon.className=`file-icon ${item.type==='file'?'doc':''}`;icon.textContent=item.type==='directory'?'▱':'▤';const title=document.createElement('span');title.textContent=item.name;name.append(icon,title);td.append(name);tr.append(td);
 const bytes=document.createElement('td');bytes.textContent=item.type==='directory'?'—':size(item.size);tr.append(bytes);const date=document.createElement('td');date.textContent=new Date(item.modified*1000).toLocaleString('es-CL',{dateStyle:'medium',timeStyle:'short'});tr.append(date);
 const actions=document.createElement('td'),row=document.createElement('div');row.className='row-actions';row.append(button('Renombrar',()=>rename(item)),button('Eliminar',()=>remove(item)));actions.append(row);tr.append(actions);list.append(tr);}
 $('empty').hidden=visible.length!==0;$('item-count').textContent=String(total);$('page-label').textContent=total?`${offset+1}–${Math.min(offset+PAGE,total)} de ${total} elementos`:'Sin archivos en esta carpeta';$('prev').disabled=offset===0;$('next').disabled=offset+PAGE>=total;
}
async function load(){const sequence=++loadSequence;try{const data=await request(url('files',current)+`&offset=${offset}&limit=${PAGE}`);if(sequence!==loadSequence)return;items=data.items;total=data.total;breadcrumbs();render();}catch(e){message(e.message);$('page-label').textContent='No se pudo consultar el almacenamiento';}}
function navigate(path){current=path;offset=0;$('search').value='';message('');load();}
async function health(){try{const h=await request('/api/v1/health');$('mount-status').textContent=h.storage==='mounted'?'Conectado':'No disponible';$('mount-detail').textContent=`Union OneDrive · carga máxima ${size(h.max_upload_bytes)}`;}catch(e){$('mount-status').textContent='Sin conexión';$('mount-detail').textContent='Revisar sesión, FUSE y servicios';message(e.message);}}
$('mkdir-btn').addEventListener('click',async()=>{const name=prompt('Nombre de la nueva carpeta:');if(!name)return;try{await request('/api/v1/directories',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:join(current,name)})});await load();message('Carpeta creada.');}catch(e){message(e.message);}});
$('upload-btn').addEventListener('click',()=>$('upload-input').click());
function sendFile(file,path){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();upload=xhr;xhr.open('PUT',url('content',path));xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.upload.onprogress=e=>{if(e.lengthComputable)$('progress').value=e.loaded/e.total*100;};xhr.onload=()=>{let r;try{r=JSON.parse(xhr.responseText);}catch{return reject(Error('Sesión vencida o respuesta inesperada. Recarga la página.'));}if(xhr.status>=200&&xhr.status<300)resolve(r);else reject(Error(r.error||'Error de carga'));};xhr.onerror=()=>reject(Error('No se pudo completar la carga. Comprueba la conexión.'));xhr.onabort=()=>reject(Error('Carga cancelada.'));xhr.send(file);});}
$('upload-input').addEventListener('change',async()=>{const files=[...$('upload-input').files];if(!files.length)return;if(!confirm('Los archivos con el mismo nombre se reemplazarán. ¿Continuar con la carga?')){$('upload-input').value='';return;}
 const dest=current;$('upload-btn').disabled=true;$('upload-progress').hidden=false;message('');try{for(const file of files){$('progress').value=0;$('progress-label').textContent=`Subiendo ${file.name}`;await sendFile(file,join(dest,file.name));}message('Carga recibida en la caché VFS. Rclone completará la transferencia a OneDrive.');}catch(e){message(e.message);}finally{upload=null;$('upload-btn').disabled=false;$('upload-progress').hidden=true;$('upload-input').value='';await load();}});
$('cancel-upload').addEventListener('click',()=>upload?.abort());$('refresh').addEventListener('click',()=>{message('');load();health();});$('search').addEventListener('input',render);$('prev').addEventListener('click',()=>{offset=Math.max(0,offset-PAGE);load();});$('next').addEventListener('click',()=>{offset+=PAGE;load();});$('api-info').addEventListener('click',()=>$('api-dialog').showModal());$('close-api').addEventListener('click',()=>$('api-dialog').close());
fetch('/config.json').then(r=>r.json()).then(c=>{$('files-link').href=c.files_url;$('auth-link').href=c.auth_url;$('api-url').textContent=c.api_url+'/v1';}).catch(()=>{});
load();health();
