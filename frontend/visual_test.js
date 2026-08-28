const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  
  // Desktop
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto('http://localhost:3001/scan', { waitUntil: 'networkidle2' });
  await page.screenshot({ path: 'screenshot_desktop_scan.png' });
  
  // Operations Desktop
  await page.goto('http://localhost:3001/operations', { waitUntil: 'networkidle2' });
  await page.screenshot({ path: 'screenshot_desktop_operations.png' });
  
  // Dashboard Desktop
  await page.goto('http://localhost:3001/dashboard', { waitUntil: 'networkidle2' });
  await page.screenshot({ path: 'screenshot_desktop_dashboard.png' });

  // Events Desktop
  await page.goto('http://localhost:3001/events', { waitUntil: 'networkidle2' });
  await page.screenshot({ path: 'screenshot_desktop_events.png' });

  // Mobile Scan
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
  await page.goto('http://localhost:3001/scan', { waitUntil: 'networkidle2' });
  await page.screenshot({ path: 'screenshot_mobile_scan.png' });

  await browser.close();
})();
