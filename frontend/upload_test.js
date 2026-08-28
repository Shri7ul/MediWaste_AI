const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto('http://localhost:3001/scan', { waitUntil: 'networkidle2' });
  
  // Find file input and upload
  const fileInput = await page.$('input[type=file]');
  const filePath = path.resolve('../data/hospital_guideline.pdf'); // Wait, use a jpg!
  const imgPath = path.resolve('../static/samples/sample4.jpg');
  await fileInput.uploadFile(imgPath);
  
  // Wait for Analyzing to finish
  await page.waitForFunction(() => document.body.innerText.includes('VERIFY COMPLIANCE'), { timeout: 15000 });
  
  await page.screenshot({ path: 'screenshot_desktop_analyze_result.png' });
  
  // Select RED route (intentional violation)
  // The actual route selector uses cards. Let's click the card containing 'RED'
  const routeCards = await page.$$('.grid-cols-2 .cursor-pointer');
  let clicked = false;
  for (const card of routeCards) {
     const text = await page.evaluate(el => el.innerText, card);
     if (text.includes('RED')) {
         await card.click();
         clicked = true;
         break;
     }
  }
  
  // Click verify
  const buttons = await page.$$('button');
  for (const btn of buttons) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text.includes('VERIFY COMPLIANCE')) {
          await btn.click();
          break;
      }
  }
  
  // Wait for Result
  await page.waitForFunction(() => document.body.innerText.includes('VIOLATION'), { timeout: 10000 });
  await page.screenshot({ path: 'screenshot_desktop_violation.png' });
  
  // Click Why this route
  const buttons2 = await page.$$('button');
  for (const btn of buttons2) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text.includes('Why this route?')) {
          await btn.click();
          break;
      }
  }
  await new Promise(r => setTimeout(r, 1000)); // Wait for sheet animation
  
  await page.screenshot({ path: 'screenshot_desktop_evidence.png' });

  await browser.close();
})();
