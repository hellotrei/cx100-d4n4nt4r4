import fs from 'fs';
import path from 'path';

export class Logger {
  constructor(logDir = 'logs') {
    this.logDir = logDir;
    this.results = [];
    this.startTime = new Date().toISOString().replace(/[:.]/g, '-');
    this.logFile = path.join(logDir, `run-${this.startTime}.json`);
    this.textFile = path.join(logDir, `run-${this.startTime}.log`);

    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    console.log(logMessage);
    fs.appendFileSync(this.textFile, logMessage + '\n');
  }

  recordResult(email, status, details) {
    const result = {
      email,
      status, // success, failed, skipped
      timestamp: new Date().toISOString(),
      details,
    };
    this.results.push(result);

    if (status === 'success') {
      this.log(`✅ SUCCESS: ${email} - ${details.message}`);
    } else if (status === 'failed') {
      this.log(`❌ FAILED: ${email} - ${details.error}`, 'ERROR');
    } else {
      this.log(`⏭️  SKIPPED: ${email} - ${details.reason}`);
    }
  }

  getSummary() {
    const success = this.results.filter((r) => r.status === 'success').length;
    const failed = this.results.filter((r) => r.status === 'failed').length;
    const skipped = this.results.filter((r) => r.status === 'skipped').length;
    const total = this.results.length;

    return {
      total,
      success,
      failed,
      skipped,
      startTime: this.startTime,
      endTime: new Date().toISOString(),
    };
  }

  saveResults() {
    const summary = this.getSummary();
    const output = {
      summary,
      results: this.results,
    };

    fs.writeFileSync(this.logFile, JSON.stringify(output, null, 2));

    // Print summary
    this.log('');
    this.log('=== RUN SUMMARY ===');
    this.log(`Total: ${summary.total}`);
    this.log(`Success: ${summary.success}`);
    this.log(`Failed: ${summary.failed}`);
    this.log(`Skipped: ${summary.skipped}`);
    this.log(`Results saved to: ${this.logFile}`);
    this.log(`Text log saved to: ${this.textFile}`);

    return output;
  }
}
