const assert=require('node:assert/strict');
module.exports.companyEventsFlow=async({page,navigate})=>{
 for(const returned of [false,true])for(const failed of [false,true]){
  await navigate(page,'Assistent');let enter,release,done;const entered=new Promise(r=>enter=r),completed=new Promise(r=>done=r),message='PRIVATE HELD BACKGROUND EVENT ERROR';
  await page.route('**/api/v1/business/company-events/plans',async route=>{const actual=await route.fetch();await new Promise(r=>{release=r;enter();});await route.fulfill(failed?{status:409,contentType:'application/json',body:JSON.stringify({error:message})}:{response:actual});done();});
  try{
   await page.getByRole('button',{name:'Unternehmensereignisse öffnen',exact:true}).click();await entered;
   assert.equal(await page.getByRole('dialog').count(),0,'Initial read is still before its first dialog');
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
   if(returned)await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});
   release();await completed;await page.waitForLoadState('networkidle');
   const count=await page.getByRole('dialog').count(),privateErrorVisible=(await page.locator('body').innerText()).includes(message);
   console.log(JSON.stringify({case:'held initial event list after actual DOM visibility handler',returnedToForeground:returned,response:failed?'error':'success',hidden:await page.evaluate(()=>document.hidden),dialogs:count,privateErrorVisible}));
   assert.equal(count,0,'Initial private event list must not appear after background before its first dialog');assert.equal(privateErrorVisible,false);
  }finally{release?.();await page.unroute('**/api/v1/business/company-events/plans');await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});}
 }
};
