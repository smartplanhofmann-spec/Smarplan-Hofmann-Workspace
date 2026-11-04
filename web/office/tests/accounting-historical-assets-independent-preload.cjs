/* Explicit test-entry substitution; does not patch product modules or server responses. */
const Module=require('node:module'),path=require('node:path'),original=Module._load;
Module._load=function(request,parent,isMain){if(request==='./accounting-historical-assets-flow.cjs')return original.call(this,path.join(__dirname,'accounting-historical-assets-independent-flow.cjs'),parent,isMain);return original.apply(this,arguments);};
