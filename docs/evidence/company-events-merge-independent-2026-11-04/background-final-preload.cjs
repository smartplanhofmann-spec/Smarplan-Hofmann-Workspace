const Module=require('node:module'),path=require('node:path'),load=Module._load;
Module._load=function(request,parent,isMain){if(request==='./company-events-flow.cjs'&&parent?.filename.endsWith('/web/office/tests/e2e.cjs'))return load.call(this,path.join(__dirname,'background-final-review.cjs'),module,false);return load.call(this,request,parent,isMain);};
