// Replace only the selected workflow entry; do not import the owner's flow tests.
const Module=require('node:module');
const path=require('node:path');
const load=Module._load;
Module._load=function(request,parent,isMain){
  if(request==='./company-events-flow.cjs'&&parent?.filename===path.join(__dirname,'e2e.cjs')){
    return load.call(this,'./company-events-independent-browser.cjs',module,false);
  }
  return load.call(this,request,parent,isMain);
};
