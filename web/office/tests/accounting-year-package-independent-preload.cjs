const Module=require('node:module'),path=require('node:path'),load=Module._load;
Module._load=function(request,parent,isMain){if(request==='./accounting-year-package-flow.cjs'&&parent?.filename===path.join(__dirname,'accounting-year-package-e2e.cjs'))return load.call(this,'./accounting-year-package-independent-browser.cjs',module,false);return load.call(this,request,parent,isMain);};
