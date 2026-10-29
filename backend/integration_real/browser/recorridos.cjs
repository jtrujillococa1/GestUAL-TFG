const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const scenario = process.argv[2];
const output = process.env.GESTUAL_REPORT_DIR;
const base = 'http://127.0.0.1:3000';
const evidence = [];

async function login(page) {
  page.setDefaultTimeout(60000);
  page.on('response', r => {
    if (r.url().startsWith('http://127.0.0.1:8011'))
      evidence.push({method:r.request().method(), path:new URL(r.url()).pathname,status:r.status()});
  });
  await page.goto(base+'/login');
  await page.getByLabel('Correo Institucional').fill('ana@gestual.example.org');
  await page.getByLabel('Contraseña',{exact:true}).fill('Gestual-Pruebas-2026!');
  const response=page.waitForResponse(r=>r.url().endsWith('/auth/token') && r.request().method()==='POST');
  await page.getByRole('button',{name:'Iniciar Sesión'}).click();
  assert.equal((await response).status(),200);
  await page.waitForURL('**/dashboard');
  await page.goto(base+'/eleccion');
}
async function select(page) {
  await page.getByRole('button',{name:/Asignatura Alfa/}).click();
  const response=page.waitForResponse(r=>r.url().includes('/anadir')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Agregar',exact:true}).first().click();
  assert.equal((await response).status(),200);
  await page.getByRole('button',{name:'Confirmar Turno',exact:true}).click();
  await page.getByRole('dialog').waitFor();
}
(async()=>{
  const browser=await chromium.launch({channel:process.env.GESTUAL_BROWSER_CHANNEL || 'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();
  try {
    await login(page);
    await select(page);
    if(scenario==='obsoleta') {
      // Otra sesión legítima modifica el borrador. No se manipula la petición
      // ni se sustituye la respuesta de la API de la primera sesión.
      const other=await browser.newContext();
      const second=await other.newPage();
      await login(second);
      const cleared=second.waitForResponse(r=>r.request().method()==='DELETE'&&r.url().includes('/borrador/'));
      await second.getByRole('button',{name:'Limpiar',exact:true}).click();
      assert.equal((await cleared).status(),200);
      await second.getByRole('button',{name:/Asignatura Beta/}).click();
      const replaced=second.waitForResponse(r=>r.url().includes('/anadir')&&r.request().method()==='POST');
      await second.getByRole('button',{name:'Agregar',exact:true}).first().click();
      assert.equal((await replaced).status(),200);
      await other.close();
    }
    const response=page.waitForResponse(r=>r.url().includes('/confirmar-turno')&&r.request().method()==='POST');
    await page.getByRole('dialog').getByRole('button',{name:'Confirmar',exact:true}).click();
    const confirmation=await response;
    assert.equal(confirmation.status(),scenario==='confirmacion'?200:409);
    if(scenario==='confirmacion') {
      await page.getByText('La selección ha sido guardada',{exact:true}).waitFor();
      await page.goto(base+'/adjudicaciones');
      await page.reload();
      const row=page.getByRole('row').filter({hasText:'Asignatura Alfa'});
      await row.waitFor();
      const text=await row.innerText();
      assert.match(text,/Ana/);
      assert.match(text,/6[.,]0 h/);
    } else {
      await page.getByText(/cambió en otra sesión/i).first().waitFor();
      await page.reload();
      await page.getByText('Asignatura Beta - A',{exact:true}).waitFor();
    }
    assert.equal(evidence.filter(x=>x.status>=500).length,0,'No debe haber errores internos de API');
    await page.screenshot({path:path.join(output,scenario+'.png'),fullPage:true});
    fs.writeFileSync(path.join(output,scenario+'.json'),JSON.stringify({scenario,passed:true,browser:browser.version(),requests:evidence},null,2));
    console.log(JSON.stringify({scenario,passed:true}));
  } catch(error) {
    fs.writeFileSync(path.join(output,scenario+'.failure.txt'),await page.locator('body').innerText());
    fs.writeFileSync(path.join(output,scenario+'.requests.json'),JSON.stringify(evidence,null,2));
    await page.screenshot({path:path.join(output,scenario+'.failure.png'),fullPage:true});
    throw error;
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
