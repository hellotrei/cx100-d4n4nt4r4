import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import fs from 'fs';
import path from 'path';
import { Logger } from './logger.js';
import { ReportGenerator } from './report-generator.js';
import { EvidenceGenerator } from './evidence-generator.js';
import { TurnstileSolver } from './turnstile-solver.js';
import { EmailChecker } from './email-checker.js';

chromium.use(StealthPlugin());

const config = JSON.parse(fs.readFileSync('config.json', 'utf8'));
const accounts = JSON.parse(fs.readFileSync('accounts.json', 'utf8'));
const logger = new Logger();
const report = new ReportGenerator('evidence');
const evidence = new EvidenceGenerator('/Users/trei/Desktop/ss-template/index.html');
const turnstileSolver = new TurnstileSolver(config.captchaApiKey || '');
const emailChecker = new EmailChecker(config);

if (!fs.existsSync('evidence')) {
  fs.mkdirSync('evidence', { recursive: true });
}

function sanitizeFilename(email) {
  return email.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
}

async function processAccount(account) {
  const { email, password } = account;

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

  try {
    // 1. Login Google
    logger.log(`[${email}] Login Google...`);
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

    logger.log(`[${email}] Login OK`);
    await googlePage.close();

    // 2. Navigate to voting page
    logger.log(`[${email}] Navigate voting page...`);
    const page = await context.newPage();
    const sectorUrl = `${config.voting.baseUrl}${config.voting.pollPath}?ref=${config.vote.ref}&state=sector-${config.vote.subSectorId}-subsector-${config.vote.subSectorId}`;
    
    let accessToken = null;
    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes('/api/v1/')) {
        try {
          const body = await response.json().catch(() => null);
          if (body?.accessToken) {
            accessToken = body.accessToken;
          }
        } catch {}
      }
    });

    await page.goto(sectorUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);

    // 3. Check if on email form or sector page
    const pageContent = await page.evaluate(() => document.body?.innerText?.substring(0, 200));
    
    if (pageContent.includes('Profil Responden') || pageContent.includes('Email')) {
      // On email form - need verification
      logger.log(`[${email}] Email form detected, starting verification...`);
      
      // Fill email
      await page.fill('input[type="email"]', email);
      
      // Check checkbox
      await page.evaluate(() => {
        const cb = document.querySelector('input[type="checkbox"]');
        if (cb) cb.click();
      });
      await page.waitForTimeout(1000);
      
      // Solve Turnstile
      if (config.captchaApiKey) {
        logger.log(`[${email}] Solving Turnstile...`);
        try {
          await turnstileSolver.solveAndFill(page);
          logger.log(`[${email}] Turnstile solved`);
        } catch (error) {
          logger.log(`[${email}] Turnstile failed: ${error.message}`);
        }
      }
      
      // Click Selanjutnya
      await page.evaluate(() => {
        const btn = document.querySelector('button');
        if (btn) {
          btn.disabled = false;
          btn.click();
        }
      });
      await page.waitForTimeout(5000);
      
      // Check for verification email
      logger.log(`[${email}] Checking email for verification link...`);
      try {
        const verificationUrl = await emailChecker.getVerificationLink(email, 30000);
        
        if (verificationUrl) {
          logger.log(`[${email}] Got verification link!`);
          await page.goto(verificationUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
          await page.waitForTimeout(3000);
        }
      } catch (error) {
        logger.log(`[${email}] Email verification failed: ${error.message}`);
      }
    }

    // 4. Wait for GIS + token
    logger.log(`[${email}] Wait token...`);
    
    for (let i = 0; i < 20; i++) {
      await page.waitForTimeout(1000);

      if (accessToken) break;

      const gsiReady = await page.evaluate(() => !!window.google?.accounts?.id);
      if (gsiReady) {
        await page.evaluate(() => {
          try { window.google.accounts.id.prompt(); } catch {}
        });
      }

      const gsiFrame = page.frames().find(f => f.url().includes('accounts.google.com/gsi'));
      if (gsiFrame) {
        try {
          const accountBtn = gsiFrame.locator(`[data-email="${email}"]`);
          if (await accountBtn.count() > 0) {
            await accountBtn.click();
          }
        } catch {}
      }

      const allPages = context.pages();
      for (const p of allPages) {
        const url = p.url();
        if (url.includes('accounts.google.com/o/oauth')) {
          const hash = url.split('#')[1];
          if (hash) {
            const params = new URLSearchParams(hash);
            const idToken = params.get('id_token');
            if (idToken) accessToken = idToken;
          }
        }
      }

      if (accessToken) break;
    }

    // 5. Check storage
    if (!accessToken) {
      for (const p of context.pages()) {
        try {
          const state = await p.evaluate(() => {
            const items = {};
            for (let i = 0; i < sessionStorage.length; i++) {
              const key = sessionStorage.key(i);
              items[key] = sessionStorage.getItem(key)?.substring(0, 100);
            }
            return items;
          });

          for (const [key, value] of Object.entries(state)) {
            if (value?.startsWith('eyJ') || key.includes('token') || key.includes('auth')) {
              accessToken = value;
            }
          }
        } catch {}
      }
    }

    // 6. Submit vote
    if (accessToken) {
      logger.log(`[${email}] Submit vote...`);
      
      const result = await submitVote(accessToken);
      
      let voteSuccess = false;
      let voteMessage = '';
      
      if (result.responseData) {
        try {
          const lines = result.responseData.split('\n');
          for (const line of lines) {
            if (line.startsWith('1:')) {
              const parsed = JSON.parse(line.substring(2));
              voteSuccess = parsed.success === true;
              voteMessage = parsed.error || parsed.message || JSON.stringify(parsed);
            }
          }
        } catch {
          voteMessage = result.responseData;
        }
      }

      if (result.success && voteSuccess) {
        const evidenceFile = `${sanitizeFilename(email)}_${Date.now()}.html`;
        const evidencePath = path.join('evidence', evidenceFile);
        const voteTime = new Date().toISOString();
        
        evidence.save(evidencePath, email, config.vote.institutionId, voteTime);
        
        logger.recordResult(email, 'success', {
          message: voteMessage || 'Vote submitted!',
          voteResponse: result.responseData || null,
          subSectorId: config.vote.subSectorId,
          institutionId: config.vote.institutionId,
          selectedFactors: config.vote.selectedFactors,
          pollSlug: config.vote.pollSlug,
          evidence: evidenceFile,
        });
      } else {
        logger.recordResult(email, 'failed', {
          error: voteMessage || `Vote failed: ${result.error}`,
          voteResponse: result.responseData || null,
        });
      }
    } else {
      logger.recordResult(email, 'failed', {
        error: 'No token found',
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

    let responseData = null;
    if (response.data) {
      responseData = typeof response.data === 'string' ? response.data : JSON.stringify(response.data);
    }

    return { success: true, status: response.status, responseData };
  } catch (error) {
    return { success: false, error: error.message, responseData: error.response?.data };
  }
}

async function main() {
  logger.log('Starting CX100 Stress Test');
  logger.log(`Target: ${config.vote.pollSlug}`);
  logger.log(`Accounts: ${accounts.length}`);
  logger.log(`CAPTCHA: ${config.captchaApiKey ? 'Configured' : 'Not configured'}`);
  logger.log(`IMAP: ${config.imap?.user || 'Not configured'}`);
  logger.log('');
  
  for (const acc of accounts) {
    try {
      await processAccount(acc);
    } catch (error) {
      logger.recordResult(acc.email, 'failed', { error: error.message });
    }
  }
  
  const output = logger.saveResults();
  
  logger.log('');
  logger.log('Generating report...');
  const reportPath = report.generateReport(output.results, config);
  logger.log(`Report saved to: ${reportPath}`);
  
  const evidenceFiles = fs.readdirSync('evidence').filter(f => f.endsWith('.html') && f !== 'report.html' && f !== 'test-evidence.html');
  logger.log(`Evidence files: ${evidenceFiles.length}`);
}

main().catch(e => {
  logger.log(`Fatal: ${e.message}`);
  logger.saveResults();
});
