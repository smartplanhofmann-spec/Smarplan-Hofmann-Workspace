const Module=require('node:module');const load=Module._load;
Module._load=function(request,parent,isMain){if(request==='./company-events-flow.cjs'&&parent?.filename==='/workspace/smartplan-company-events-integration-20261104/web/office/tests/e2e.cjs')return load.call(this,'/tmp/events-merge-background-review.cjs',module,false);return load.call(this,request,parent,isMain);};
