import fs from 'fs';
import path from 'path';

export class ReportGenerator {
  constructor(outputDir = 'evidence') {
    this.outputDir = outputDir;
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
  }

  generateReport(results, config) {
    const reportData = results.map(r => ({
      email: r.email,
      status: r.status,
      timestamp: r.timestamp,
      details: r.details || {},
    }));

    const html = this.buildHTML(reportData, config);
    const reportPath = path.join(this.outputDir, 'report.html');
    fs.writeFileSync(reportPath, html);

    return reportPath;
  }

  buildHTML(data, config) {
    const successful = data.filter(d => d.status === 'success');
    const failed = data.filter(d => d.status === 'failed');

    return `<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CX100 Stress Test Report</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f0f0f; color: #fff; padding: 20px;
    }
    .header {
      text-align: center; padding: 40px 20px;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      border-radius: 12px; margin-bottom: 30px;
    }
    .header h1 { font-size: 28px; margin-bottom: 10px; color: #fff; }
    .header .subtitle { color: #888; font-size: 14px; }
    
    .stats {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
      margin-bottom: 30px;
    }
    .stat-card {
      background: #1a1a1a; border-radius: 10px; padding: 20px;
      text-align: center; border: 1px solid #333;
    }
    .stat-card .value { font-size: 36px; font-weight: bold; }
    .stat-card .label { font-size: 12px; color: #888; margin-top: 5px; }
    .stat-card.success .value { color: #22c55e; }
    .stat-card.failed .value { color: #ef4444; }
    .stat-card.total .value { color: #3b82f6; }
    .stat-card.time .value { color: #f59e0b; font-size: 18px; }
    
    .config-info {
      background: #1a1a1a; border-radius: 10px; padding: 20px;
      margin-bottom: 30px; border: 1px solid #333;
    }
    .config-info h3 { margin-bottom: 15px; color: #3b82f6; }
    .config-row { display: flex; margin-bottom: 10px; }
    .config-label { color: #888; min-width: 120px; }
    .config-value { color: #fff; font-family: monospace; }
    
    .section-title {
      font-size: 20px; margin: 30px 0 15px; padding-bottom: 10px;
      border-bottom: 1px solid #333;
    }
    
    .vote-table {
      width: 100%; border-collapse: collapse; margin-bottom: 30px;
    }
    .vote-table th, .vote-table td {
      padding: 12px 16px; text-align: left; border-bottom: 1px solid #333;
    }
    .vote-table th {
      background: #1a1a1a; color: #888; font-size: 12px; text-transform: uppercase;
      position: sticky; top: 0;
    }
    .vote-table tr:hover { background: #1a1a1a; }
    .vote-table .status-badge {
      display: inline-block; padding: 4px 10px; border-radius: 20px;
      font-size: 11px; font-weight: 600;
    }
    .vote-table .success .status-badge { background: #22c55e22; color: #22c55e; }
    .vote-table .failed .status-badge { background: #ef444422; color: #ef4444; }
    .vote-table .email { font-weight: 500; word-break: break-all; }
    .vote-table .response { 
      max-width: 300px; overflow: hidden; text-overflow: ellipsis; 
      white-space: nowrap; color: #888; font-size: 13px;
    }
    .vote-table .response:hover { white-space: normal; }
    
    .footer {
      text-align: center; padding: 30px; color: #666; font-size: 12px;
      margin-top: 40px; border-top: 1px solid #333;
    }
    
    @media (max-width: 768px) {
      .stats { grid-template-columns: repeat(2, 1fr); }
      .vote-table { font-size: 12px; }
      .vote-table th, .vote-table td { padding: 8px; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>🎯 CX100 Stress Test Report</h1>
    <div class="subtitle">Automated Voting Evidence • ${new Date().toLocaleDateString('id-ID', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</div>
  </div>

  <div class="stats">
    <div class="stat-card total">
      <div class="value">${data.length}</div>
      <div class="label">Total Akun</div>
    </div>
    <div class="stat-card success">
      <div class="value">${successful.length}</div>
      <div class="label">Berhasil</div>
    </div>
    <div class="stat-card failed">
      <div class="value">${failed.length}</div>
      <div class="label">Gagal</div>
    </div>
    <div class="stat-card time">
      <div class="value">${config.vote?.pollSlug || 'CX100'}</div>
      <div class="label">Target</div>
    </div>
  </div>

  <div class="config-info">
    <h3>📋 Konfigurasi Voting</h3>
    <div class="config-row">
      <span class="config-label">Sektor</span>
      <span class="config-value">${config.vote?.subSectorId || '-'}</span>
    </div>
    <div class="config-row">
      <span class="config-label">Institusi</span>
      <span class="config-value">${config.vote?.institutionId || '-'}</span>
    </div>
    <div class="config-row">
      <span class="config-label">Faktor</span>
      <span class="config-value">${(config.vote?.selectedFactors || []).join(', ')}</span>
    </div>
  </div>

  <h2 class="section-title">✅ Berhasil Vote (${successful.length})</h2>
  <table class="vote-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Email</th>
        <th>Timestamp</th>
        <th>Status</th>
        <th>Response</th>
      </tr>
    </thead>
    <tbody>
      ${successful.map((item, idx) => this.buildTableRow(item, idx)).join('\n')}
    </tbody>
  </table>

  ${failed.length > 0 ? `
  <h2 class="section-title">❌ Gagal (${failed.length})</h2>
  <table class="vote-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Email</th>
        <th>Timestamp</th>
        <th>Status</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody>
      ${failed.map((item, idx) => this.buildTableRow(item, idx)).join('\n')}
    </tbody>
  </table>
  ` : ''}

  <div class="footer">
    Generated by CX100 Stress Test • ${new Date().toISOString()}
  </div>
</body>
</html>`;
  }

  buildTableRow(item, idx) {
    const time = item.timestamp ? new Date(item.timestamp).toLocaleString('id-ID') : '-';
    const response = item.details?.voteResponse || item.details?.error || item.details?.message || '-';
    const truncatedResponse = response.length > 100 ? response.substring(0, 100) + '...' : response;

    return `
    <tr class="${item.status}">
      <td>${idx + 1}</td>
      <td class="email">${item.email}</td>
      <td>${time}</td>
      <td><span class="status-badge">${item.status === 'success' ? '✅ BERHASIL' : '❌ GAGAL'}</span></td>
      <td class="response" title="${response}">${truncatedResponse}</td>
    </tr>`;
  }
}
