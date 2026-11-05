/* Delay only the genuine media-change callback; keep actual application, API and assertions. */
const fs=require('node:fs');
const path=require('node:path');
const Module=require('node:module');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../../..');
const filename=path.join(root,'web/office/tests/e2e.cjs');
const phase=process.argv[2];
if(!['before','after'].includes(phase))throw new Error('Use before or after');
let source=phase==='before'?execFileSync('git',['show','a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5:web/office/tests/e2e.cjs'],{cwd:root,encoding:'utf8'}):fs.readFileSync(filename,'utf8');
const injection=`await context.addInitScript(()=>{
  const actual=window.matchMedia.bind(window);
  window.matchMedia=query=>{
    const media=actual(query);
    if(query==='(max-width:760px)'){
      const add=media.addEventListener.bind(media);
      media.addEventListener=(type,callback,...options)=>add(type,type==='change'?event=>setTimeout(()=>callback.call(media,event),250):callback,...options);
    }
    return media;
  };
});\n    `;
const target="page=await context.newPage();";
if(source.split(target).length!==2)throw new Error('Expected exact live page-creation hook');
source=source.replace(target,injection+target);
if(!source.includes('if(require.main===module)main();'))throw new Error('Expected actual main entry');
source=source.replace('if(require.main===module)main();','main();');
console.log('Controlled real drawer media event delay: 250 ms; phase='+phase);
const run=new Module(filename,module);run.filename=filename;run.paths=Module._nodeModulePaths(path.dirname(filename));run._compile(source,filename);
