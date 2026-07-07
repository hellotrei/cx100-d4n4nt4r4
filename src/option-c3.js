import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import fs from 'fs';
import path from 'path';
import { Logger } from './logger.js';
import { ReportGenerator } from './report-generator.js';

chromium.use(StealthPlugin());

const config = JSON.parse(fs.readFileSync('config.json', 'utf8'));
const accounts = JSON.parse(fs.readFileSync('accounts.json', 'utf8'));
const logger = new Logger();
const report = new ReportGenerator('evidence');

// Create evidence directory
if (!fs.existsSync('evidence')) {
  fs.mkdirSync('evidence', { recursive: true });
}

function sanitizeFilename(email) {
  return email.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
}

async function processAccount(account) {
  const { email, password } = account;
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `${sanitizeFilename(email)}_${timestamp}.png`;
  const screenshotPath = path.join('evidence', filename);

  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-blink-features=AutomationControlled',
    ],
  });

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Safari/605.1.15',
    viewport: { width: 1280, height: 800 },
    locale: 'en-US',
  });

  let voteDetails = {};

  try {
    // 1. Login Google first
    logger.log(`[${email}] Logging into Google...`);
    const googlePage = await context.newPage();
    await googlePage.goto('https://accounts.google.com/signin', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await googlePage.waitForTimeout(2000);

    await googlePage.fill('input#identifierId', email);
    await googlePage.click('#identifierNext');
    await googlePage.waitForTimeout(3000);

    await googlePage.fill('input[type="password"]', password);
    await googlePage.click('#passwordNext');
    await googlePage.waitForTimeout(5000);

    const googleUrl = googlePage.url();
    if (googleUrl.includes('challenge') || googleUrl.includes('accounts.google.com/signin')) {
      throw new Error(`Google login failed: ${googleUrl.substring(0, 80)}`);
    }

    logger.log(`[${email}] Google login OK`);
    await googlePage.close();

    // 2. Go DIRECTLY to sector page
    logger.log(`[${email}] Navigating to sector page directly...`);
    const page = await context.newPage();
    const sectorUrl = `${config.voting.baseUrl}${config.voting.pollPath}?ref=${config.vote.ref}&state=sector-${config.vote.subSectorId}-subsector-${config.vote.subSectorId}`;
    
    // Capture all network responses
    let accessToken = null;
    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes('/api/v1/')) {
        try {
          const body = await response.json().catch(() => null);
          if (body?.accessToken) {
            accessToken = body.accessToken;
            logger.log(`[${email}] Got accessToken from API!`);
          }
        } catch {}
      }
    });

    await page.goto(sectorUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);

    // 3. Check what's on the page
    const pageState = await page.evaluate(() => ({
      url: location.href,
      title: document.title,
      text: document.body?.innerText?.substring(0, 500),
    }));
    logger.log(`[${email}] Page: ${pageState.title} — ${pageState.url.substring(0, 80)}`);

    // 4. Wait for GIS to auto-login
    logger.log(`[${email}] Waiting for GIS...`);
    
    for (let i = 0; i < 30; i++) {
      await page.waitForTimeout(1000);

      const gsiReady = await page.evaluate(() => !!window.google?.accounts?.id);
      if (gsiReady) {
        logger.log(`[${email}] GIS loaded!`);
        await page.evaluate(() => {
          try { window.google.accounts.id.prompt(); } catch {}
        });
      }

      if (accessToken) {
        logger.log(`[${email}] Got accessToken!`);
        break;
      }

      const gsiFrame = page.frames().find(f => f.url().includes('accounts.google.com/gsi'));
      if (gsiFrame) {
        logger.log(`[${email}] Found GIS iframe!`);
        try {
          const accountBtn = gsiFrame.locator(`[data-email="${email}"]`);
          if (await accountBtn.count() > 0) {
            await accountBtn.click();
            logger.log(`[${email}] Clicked account in GIS iframe!`);
          }
        } catch {}
      }

      const allPages = context.pages();
      for (const p of allPages) {
        const url = p.url();
        if (url.includes('accounts.google.com/o/oauth')) {
          logger.log(`[${email}] Found Google OAuth page!`);
          const hash = url.split('#')[1];
          if (hash) {
            const params = new URLSearchParams(hash);
            const idToken = params.get('id_token');
            if (idToken) {
              logger.log(`[${email}] Got ID token from URL!`);
              accessToken = idToken;
            }
          }
        }
      }

      if (accessToken) break;
    }

    // 5. Check for accessToken in all pages
    if (!accessToken) {
      for (const p of context.pages()) {
        try {
          const state = await p.evaluate(() => {
            const items = {};
            for (let i = 0; i < localStorage.length; i++) {
              const key = localStorage.key(i);
              items[key] = localStorage.getItem(key)?.substring(0, 100);
            }
            for (let i = 0; i < sessionStorage.length; i++) {
              const key = sessionStorage.key(i);
              items[`ss:${key}`] = sessionStorage.getItem(key)?.substring(0, 100);
            }
            return items;
          });

          logger.log(`[${email}] Storage: ${JSON.stringify(state)}`);

          for (const [key, value] of Object.entries(state)) {
            if (value?.startsWith('eyJ') || key.includes('token') || key.includes('auth')) {
              logger.log(`[${email}] Found potential token: ${key} = ${value?.substring(0, 50)}`);
              accessToken = value;
            }
          }
        } catch {}
      }
    }

    // 6. Submit vote and capture evidence
    if (accessToken) {
      logger.log(`[${email}] Submitting vote with accessToken...`);
      
      // Capture screenshot BEFORE submitting
      await page.screenshot({ path: screenshotPath, fullPage: true });
      logger.log(`[${email}] Screenshot saved: ${filename}`);

      // Extract vote details from page
      voteDetails = await page.evaluate(() => {
        const text = document.body?.innerText || '';
        // Try to extract sub-sector and institution from page text
        const subSectorMatch = text.match(/Sektor[:\s]+([^\n]+)/i);
        const institutionMatch = text.match(/Institusi[:\s]+([^\n]+)/i);
        return {
          subSectorName: subSectorMatch?.[1]?.trim() || null,
          institutionName: institutionMatch?.[1]?.trim() || null,
          pageUrl: window.location.href,
        };
      });

      // Merge with config data
      voteDetails = {
        ...voteDetails,
        subSectorId: config.vote.subSectorId,
        institutionId: config.vote.institutionId,
        selectedFactors: config.vote.selectedFactors,
        pollSlug: config.vote.pollSlug,
      };

      const result = await submitVote(accessToken);
      
      if (result.success) {
        logger.recordResult(email, 'success', {
          message: 'Vote submitted!',
          screenshot: filename,
          ...voteDetails,
        });
      } else {
        logger.recordResult(email, 'failed', {
          error: `Vote failed: ${result.error}`,
          screenshot: filename,
          ...voteDetails,
        });
      }
    } else {
      // Take screenshot for debugging
      await page.screenshot({ path: screenshotPath, fullPage: true });
      logger.recordResult(email, 'failed', {
        error: 'No accessToken found on sector page',
        screenshot: filename,
      });
    }

  } finally {
    await browser.close();
  }
}

async function submitVote(accessToken) {
  try {
    const { default: axios } = await import('axios');

    const payload = [
      config.vote.pollSlug,
      {
        subSectorId: config.vote.subSectorId,
        institutionId: config.vote.institutionId,
        questionnaireResponse: {
          selectedFactors: config.vote.selectedFactors,
          reasonText: config.vote.reasonText,
        },
      },
      accessToken,
    ];

    const response = await axios.post(
      `${config.voting.baseUrl}${config.voting.pollPath}?ref=${config.vote.ref}&state=sector-${config.vote.subSectorId}-subsector-${config.vote.subSectorId}`,
      JSON.stringify(payload),
      {
        headers: {
          'Content-Type': 'text/plain;charset=UTF-8',
          'Accept': 'text/x-component',
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
          'Origin': config.voting.baseUrl,
          'Cookie': 'g_state={"i_l":1}',
          'next-action': '709cd13f602d4f2b96ca742284b6a070ccded9e797',
          'next-router-state-tree': '%5B%22%22%2C%7B%22children%22%3A%5B%22polls%22%2C%7B%22children%22%3A%5B%5B%22slug%22%2C%22cx100-danantara%22%2C%22d%22%2Cnull%5D%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C16%5D',
        },
        timeout: 15000,
      }
    );

    return { success: true, status: response.status };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function main() {
  logger.log('Starting CX100 Stress Test with Evidence');
  logger.log(`Target: ${config.vote.pollSlug}`);
  logger.log(`Accounts: ${accounts.length}`);
  logger.log('');
  
  for (const acc of accounts) {
    try {
      await processAccount(acc);
    } catch (error) {
      logger.recordResult(acc.email, 'failed', { error: error.message });
    }
  }
  
  // Save results
  const output = logger.saveResults();
  
  // Generate report
  logger.log('');
  logger.log('Generating report...');
  const reportPath = report.generateReport(output.results, config);
  logger.log(`Report saved to: ${reportPath}`);
  
  // List evidence files
  const evidenceFiles = fs.readdirSync('evidence').filter(f => f.endsWith('.png'));
  logger.log(`Evidence screenshots: ${evidenceFiles.length}`);
}

main().catch(e => {
  logger.log(`Fatal: ${e.message}`);
  logger.saveResults();
});
