/* Real mobile MFA after a prior viewport change; authentication is not mocked. */
const assert=require('node:assert/strict'),path=require('node:path');

async function mobileLoginFlow({page,context,login,ready,navigate,screenshots}){
  await ready(page);await page.setViewportSize({width:390,height:844});
  await navigate(page,'Personal');
  await page.getByRole('button',{name:'Abmelden',exact:true}).click();
  await page.getByRole('heading',{name:'Willkommen im Büro.',exact:true}).waitFor();
  const email='technician@browser.example.test',users=[];
  const observe=async route=>{
    const response=await route.fetch({maxRedirects:0});assert.equal(response.status(),200);
    const user=await response.json();await route.fulfill({response});users.push(user);
  };
  await context.route('**/api/v1/me',observe);
  try{
    const codes=await login(page,email);
    assert.equal(users.at(-1).email,email);
    const identity=page.locator('.topbar .identity').getByText(email,{exact:true});
    assert.equal(await identity.count(),1);assert.equal(await identity.isHidden(),true);
    assert.equal(await page.getByRole('button',{name:'Abmelden',exact:true}).isVisible(),true);
    await navigate(page,'Personal');
    await page.reload();
    await login(page,email,codes[0]);
    assert.equal(users.length,2);assert.ok(users.every(user=>user.email===email));
    assert.equal(await identity.isHidden(),true);assert.equal(page.viewportSize().width,390);
    await navigate(page,'Personal');
    await page.screenshot({path:path.join(screenshots,'mobile-login-technician.png'),fullPage:false});
    console.log('mobile login: real technician /me, MFA and recovery login at390px, hidden exact identity and visible logout verified without timeout changes');
  }finally{await context.unroute('**/api/v1/me',observe);}
}
module.exports={mobileLoginFlow};
