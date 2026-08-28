const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Desktop
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('http://localhost:3001/scan', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'screenshot_desktop_scan.png' });
  
  // Operations Desktop
  await page.goto('http://localhost:3001/operations', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'screenshot_desktop_operations.png' });
  
  // Dashboard Desktop
  await page.goto('http://localhost:3001/dashboard', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'screenshot_desktop_dashboard.png' });

  // Events Desktop
  await page.goto('http://localhost:3001/events', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'screenshot_desktop_events.png' });

  // Mobile Scan
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('http://localhost:3001/scan', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'screenshot_mobile_scan.png' });

  await browser.close();
})();
