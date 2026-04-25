let equityChart = null;
let backtestHistory = [];
let syncPollTimer = null;
let enabledScanStrategies = [];

let API_BASE_URL = resolveApiBaseUrl();

document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    initializeSyncPage();
    initializeScanPage();
    initializeRankingPage();
    initializeBacktestForm();
    initializeOptimizationForm();
    loadBacktestHistory();
});

function initializeNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();

            navLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');

            const page = this.dataset.page;
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(`${page}-page`).classList.add('active');
        });
    });
}

function initializeSyncPage() {
    const manualForm = document.getElementById('manual-sync-form');
    const scheduleForm = document.getElementById('schedule-sync-form');
    const runScheduleNowBtn = document.getElementById('run-schedule-now-btn');
    const syncScope = document.getElementById('sync-scope');
    const scheduleScope = document.getElementById('schedule-scope');

    if (!manualForm || !scheduleForm) {
        return;
    }

    setDefaultSyncDates();
    syncScope.addEventListener('change', updateManualDateRequirements);
    scheduleScope.addEventListener('change', updateScheduleLookbackState);
    updateManualDateRequirements();
    updateScheduleLookbackState();

    manualForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        await submitManualSync();
    });

    scheduleForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        await saveSyncSchedule();
    });

    runScheduleNowBtn.addEventListener('click', async function() {
        await runScheduleNow();
    });

    loadSyncSchedule();
    loadSyncJobs();
}

function setDefaultSyncDates() {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 7);
    document.getElementById('sync-start-date').value = toDateInput(start);
    document.getElementById('sync-end-date').value = toDateInput(end);
}

function updateManualDateRequirements() {
    const scope = document.getElementById('sync-scope').value;
    const startInput = document.getElementById('sync-start-date');
    const endInput = document.getElementById('sync-end-date');
    const needsDates = scope !== 'stocks';
    startInput.required = needsDates;
    endInput.required = needsDates;
    startInput.disabled = !needsDates;
    endInput.disabled = !needsDates;
}

function updateScheduleLookbackState() {
    const scope = document.getElementById('schedule-scope').value;
    document.getElementById('schedule-lookback-days').disabled = scope === 'stocks';
}

async function submitManualSync() {
    const button = document.getElementById('manual-sync-btn');
    setButtonLoading(button, true, '提交中...');
    try {
        const payload = buildManualSyncPayload();
        const job = await apiFetch('/syncs', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        setSyncJob(job);
        await loadSyncJobs();
        pollSyncJob(job.job_id);
    } catch (error) {
        alert(`同步任务提交失败: ${error.message}`);
    } finally {
        setButtonLoading(button, false, '开始同步');
    }
}

function buildManualSyncPayload() {
    const scope = document.getElementById('sync-scope').value;
    const payload = {
        scope,
        stock_codes: parseStockCodes(document.getElementById('sync-stock-codes').value),
    };
    if (scope !== 'stocks') {
        payload.start = formatDate(document.getElementById('sync-start-date').value);
        payload.end = formatDate(document.getElementById('sync-end-date').value);
    }
    return payload;
}

async function loadSyncSchedule() {
    try {
        const schedule = await apiFetch('/sync-schedules/default');
        fillScheduleForm(schedule);
    } catch (error) {
        document.getElementById('schedule-next-run').textContent = `读取失败: ${error.message}`;
    }
}

function fillScheduleForm(schedule) {
    document.getElementById('schedule-enabled').value = String(schedule.enabled);
    document.getElementById('schedule-run-time').value = schedule.run_time || '18:30';
    document.getElementById('schedule-lookback-days').value = schedule.lookback_days || 7;
    document.getElementById('schedule-scope').value = schedule.scope || 'all';
    document.getElementById('schedule-stock-codes').value = (schedule.stock_codes || []).join(', ');
    document.getElementById('schedule-next-run').textContent = formatDateTime(schedule.next_run_at);
    document.getElementById('schedule-last-job').textContent = schedule.last_job_id || '--';
    updateScheduleLookbackState();
}

async function saveSyncSchedule() {
    const button = document.getElementById('save-schedule-btn');
    setButtonLoading(button, true, '保存中...');
    try {
        const schedule = await apiFetch('/sync-schedules/default', {
            method: 'PUT',
            body: JSON.stringify(buildSchedulePayload()),
        });
        fillScheduleForm(schedule);
        alert('定时同步设置已保存');
    } catch (error) {
        alert(`保存失败: ${error.message}`);
    } finally {
        setButtonLoading(button, false, '保存定时设置');
    }
}

function buildSchedulePayload() {
    return {
        enabled: document.getElementById('schedule-enabled').value === 'true',
        run_time: document.getElementById('schedule-run-time').value,
        lookback_days: parseInt(document.getElementById('schedule-lookback-days').value, 10),
        scope: document.getElementById('schedule-scope').value,
        stock_codes: parseStockCodes(document.getElementById('schedule-stock-codes').value),
    };
}

async function runScheduleNow() {
    const button = document.getElementById('run-schedule-now-btn');
    setButtonLoading(button, true, '提交中...');
    try {
        const job = await apiFetch('/sync-schedules/default/run', { method: 'POST' });
        setSyncJob(job);
        await loadSyncJobs();
        pollSyncJob(job.job_id);
        await loadSyncSchedule();
    } catch (error) {
        alert(`立即同步失败: ${error.message}`);
    } finally {
        setButtonLoading(button, false, '按定时参数立即同步');
    }
}

function pollSyncJob(jobId) {
    if (syncPollTimer) {
        clearInterval(syncPollTimer);
    }
    syncPollTimer = setInterval(async () => {
        try {
            const job = await apiFetch(`/jobs/${jobId}`);
            setSyncJob(job);
            if (job.status === 'completed' || job.status === 'failed') {
                clearInterval(syncPollTimer);
                syncPollTimer = null;
                await loadSyncResults(jobId);
                await loadSyncSchedule();
                await loadSyncJobs();
            }
        } catch (error) {
            clearInterval(syncPollTimer);
            syncPollTimer = null;
            document.getElementById('sync-job-error').textContent = error.message;
        }
    }, 1000);
}

function setSyncJob(job) {
    document.getElementById('sync-job-id').textContent = job.job_id || '--';
    document.getElementById('sync-job-status').innerHTML = renderStatus(job.status);
    document.getElementById('sync-job-progress').textContent =
        `${job.success_count || 0} 成功 / ${job.failed_count || 0} 失败 / ${job.total_items || 0} 项`;
    document.getElementById('sync-job-error').textContent = job.error || '--';
}

async function loadSyncJobs() {
    const tbody = document.getElementById('sync-jobs-tbody');
    if (!tbody) {
        return;
    }
    try {
        const jobs = await apiFetch('/jobs?type=sync&limit=20');
        renderSyncJobs(jobs);
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">同步任务读取失败: ${escapeHtml(error.message)}</td></tr>`;
    }
}

function renderSyncJobs(jobs) {
    const tbody = document.getElementById('sync-jobs-tbody');
    if (!jobs.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无同步任务</td></tr>';
        return;
    }

    tbody.innerHTML = jobs.map(job => {
        const progress = `${job.success_count || 0}/${job.failed_count || 0}/${job.total_items || 0}`;
        return `
            <tr>
                <td>${escapeHtml(shortJobId(job.job_id))}</td>
                <td>${escapeHtml(job.params?.scope || '--')}</td>
                <td>${renderStatus(job.status)}</td>
                <td>${progress}</td>
                <td>${escapeHtml(formatDateTime(job.created_at))}</td>
                <td>
                    <button class="btn btn-secondary compact-btn" onclick="selectSyncJob('${escapeHtml(job.job_id)}')">
                        查看
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function selectSyncJob(jobId) {
    try {
        const job = await apiFetch(`/jobs/${jobId}`);
        setSyncJob(job);
        await loadSyncResults(jobId);
        if (job.status !== 'completed' && job.status !== 'failed') {
            pollSyncJob(jobId);
        }
    } catch (error) {
        document.getElementById('sync-job-error').textContent = error.message;
    }
}

function shortJobId(jobId) {
    return jobId ? `${jobId.slice(0, 8)}...` : '--';
}

async function loadSyncResults(jobId) {
    const results = await apiFetch(`/syncs/${jobId}/results`);
    const tbody = document.getElementById('sync-results-tbody');
    if (!results.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">暂无同步结果</td></tr>';
        return;
    }
    tbody.innerHTML = results.map(item => `
        <tr>
            <td>${escapeHtml(item.scope)}</td>
            <td>${escapeHtml(item.code || '全部')}</td>
            <td>${renderStatus(item.status)}</td>
            <td>${item.rows_written}</td>
            <td>${escapeHtml(item.message || '')}</td>
        </tr>
    `).join('');
}

function initializeScanPage() {
    const form = document.getElementById('scan-form');
    if (!form) {
        return;
    }

    setDefaultScanDates();
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await submitScan();
    });

    loadEnabledStrategies();
    loadScanJobs();
}

function initializeRankingPage() {
    ensureRankingNavLink();
    const form = document.getElementById('ranking-form');
    if (!form) {
        return;
    }

    setDefaultRankingDates();
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await loadHighLowGainRanking();
    });
}

function ensureRankingNavLink() {
    const nav = document.querySelector('.nav');
    if (!nav || nav.querySelector('[data-page="ranking"]')) {
        return;
    }
    const backtestLink = nav.querySelector('[data-page="backtest"]');
    const rankingLink = document.createElement('a');
    rankingLink.href = '#';
    rankingLink.className = 'nav-link';
    rankingLink.dataset.page = 'ranking';
    rankingLink.textContent = '涨幅排行';
    if (backtestLink) {
        nav.insertBefore(rankingLink, backtestLink);
    } else {
        nav.appendChild(rankingLink);
    }
    rankingLink.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
        this.classList.add('active');
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        document.getElementById('ranking-page').classList.add('active');
    });
}

function setDefaultRankingDates() {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 60);
    document.getElementById('ranking-start-date').value = toDateInput(start);
    document.getElementById('ranking-end-date').value = toDateInput(end);
    document.getElementById('ranking-limit').value = 100;
    document.getElementById('ranking-direction-up').checked = true;
    document.getElementById('ranking-min-gain-percent').value = 30;
}

async function loadHighLowGainRanking() {
    const button = document.getElementById('ranking-query-btn');
    const tbody = document.getElementById('ranking-results-tbody');
    const start = formatDate(document.getElementById('ranking-start-date').value);
    const end = formatDate(document.getElementById('ranking-end-date').value);
    const limit = document.getElementById('ranking-limit').value || 100;
    const directionInput = document.querySelector('input[name="ranking-direction"]:checked');
    const direction = directionInput ? directionInput.value : 'up';
    const minGainPercent = document.getElementById('ranking-min-gain-percent').value;
    const params = new URLSearchParams({
        start,
        end,
        limit,
        direction,
    });
    if (minGainPercent !== '') {
        params.set('min_gain_percent', minGainPercent);
    }
    setButtonLoading(button, true, '查询中...');
    try {
        const results = await apiFetch(`/rankings/high-low-gain?${params.toString()}`);
        if (!results.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="empty-state">暂无排行结果，请先同步该区间日线数据</td></tr>';
            return;
        }
        tbody.innerHTML = results.map((item, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>${escapeHtml(item.code)}</td>
                <td>${escapeHtml(item.name)}</td>
                <td>${escapeHtml(formatNullableNumber(item.lowest_price))}</td>
                <td>${escapeHtml(item.lowest_date)}</td>
                <td>${escapeHtml(formatNullableNumber(item.highest_price))}</td>
                <td>${escapeHtml(item.highest_date)}</td>
                <td>${escapeHtml(formatGainPercent(item.gain_percent))}</td>
                <td>${escapeHtml(item.trade_days)}</td>
            </tr>
        `).join('');
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-state">涨幅排行查询失败: ${escapeHtml(error.message)}</td></tr>`;
    } finally {
        setButtonLoading(button, false, '查询排行');
    }
}

function setDefaultScanDates() {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 60);
    document.getElementById('scan-start-date').value = toDateInput(start);
    document.getElementById('scan-end-date').value = toDateInput(end);
    document.getElementById('scan-target-date').value = toDateInput(end);
}

async function loadEnabledStrategies() {
    const tbody = document.getElementById('enabled-strategies-tbody');
    if (!tbody) {
        return;
    }
    try {
        const strategies = await apiFetch('/strategies');
        enabledScanStrategies = strategies;
        if (!strategies.length) {
            tbody.innerHTML = '<tr><td colspan="3" class="empty-state">当前没有启用策略</td></tr>';
            return;
        }
        tbody.innerHTML = strategies.map(strategy => `
            <tr>
                <td>
                    <label class="checkbox-cell">
                        <input type="checkbox" class="scan-strategy-checkbox" value="${escapeHtml(strategy.class_name)}" checked>
                        执行
                    </label>
                </td>
                <td>${escapeHtml(strategy.class_name)}</td>
                <td>${escapeHtml(strategy.name)}</td>
            </tr>
        `).join('');
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="3" class="empty-state">策略读取失败: ${escapeHtml(error.message)}</td></tr>`;
    }
}

async function submitScan() {
    const button = document.getElementById('run-scan-btn');
    const strategyClasses = getSelectedScanStrategies();
    if (!strategyClasses.length) {
        alert('请至少选择一个选股策略');
        return;
    }
    setButtonLoading(button, true, '提交中...');
    try {
        const job = await apiFetch('/scans', {
            method: 'POST',
            body: JSON.stringify(buildScanPayload(strategyClasses)),
        });
        setScanJob(job);
        await loadScanJobs();
    } catch (error) {
        alert(`选股任务提交失败: ${error.message}`);
    } finally {
        setButtonLoading(button, false, '开始批量选股');
    }
}

function buildScanPayload(strategyClasses) {
    return {
        start: formatDate(document.getElementById('scan-start-date').value),
        end: formatDate(document.getElementById('scan-end-date').value),
        targets: [formatDate(document.getElementById('scan-target-date').value)],
        strategy_classes: strategyClasses,
    };
}

function getSelectedScanStrategies() {
    return Array.from(document.querySelectorAll('.scan-strategy-checkbox:checked'))
        .map(checkbox => checkbox.value)
        .filter(Boolean);
}

function setScanJob(job) {
    document.getElementById('scan-job-id').textContent = job.job_id || '--';
    document.getElementById('scan-job-status').innerHTML = renderStatus(job.status);
    document.getElementById('scan-job-progress').textContent =
        `${job.total_results ?? job.success_count ?? 0} 条命中`;
    document.getElementById('scan-job-period').textContent =
        `${job.start_date || '--'} ~ ${job.end_date || '--'} / ${formatTargetDates(job.target_dates)}`;
    document.getElementById('scan-job-error').textContent = job.error || '--';
}

async function loadScanJobs() {
    const tbody = document.getElementById('scan-jobs-tbody');
    if (!tbody) {
        return;
    }
    try {
        const jobs = await apiFetch('/jobs?type=scan&limit=20');
        renderScanJobs(jobs);
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">选股任务读取失败: ${escapeHtml(error.message)}</td></tr>`;
    }
}

function renderScanJobs(jobs) {
    const tbody = document.getElementById('scan-jobs-tbody');
    if (!jobs.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无选股任务</td></tr>';
        return;
    }

    tbody.innerHTML = jobs.map(job => `
        <tr>
            <td>${escapeHtml(shortJobId(job.job_id))}</td>
            <td>${renderStatus(job.status)}</td>
            <td>${job.success_count || 0}</td>
            <td>${escapeHtml(formatScanStrategySummary(job.params?.strategy_classes))}</td>
            <td>${escapeHtml(formatDateTime(job.created_at))}</td>
            <td>
                <button class="btn btn-secondary compact-btn" onclick="selectScanJob('${escapeHtml(job.job_id)}')">
                    查看
                </button>
            </td>
        </tr>
    `).join('');
}

async function selectScanJob(jobId) {
    try {
        const job = await apiFetch(`/scans/${jobId}`);
        setScanJob(job);
        await loadScanResults(jobId);
    } catch (error) {
        document.getElementById('scan-job-error').textContent = error.message;
    }
}

async function loadScanResults(jobId) {
    const tbody = document.getElementById('scan-results-tbody');
    if (!tbody) {
        return;
    }
    try {
        const results = await apiFetch(`/scans/${jobId}/results`);
        if (!results.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">暂无选股结果</td></tr>';
            return;
        }
        tbody.innerHTML = results.map(item => `
            <tr>
                <td>${escapeHtml(item.code)}</td>
                <td>${escapeHtml(item.name)}</td>
                <td>${escapeHtml(item.strategy)}</td>
                <td>${escapeHtml(item.target_date)}</td>
                <td>${escapeHtml(formatNullableNumber(item.current_price))}</td>
                <td>${escapeHtml(formatNullableNumber(item.current_volume))}</td>
                <td>${escapeHtml(formatDateTime(item.created_at))}</td>
            </tr>
        `).join('');
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">选股结果读取失败: ${escapeHtml(error.message)}</td></tr>`;
    }
}

function formatTargetDates(targetDates) {
    return Array.isArray(targetDates) && targetDates.length ? targetDates.join(', ') : '--';
}

function formatScanStrategySummary(strategyClasses) {
    if (!Array.isArray(strategyClasses) || !strategyClasses.length) {
        return '全部启用策略';
    }
    if (strategyClasses.length <= 2) {
        return strategyClasses.join(', ');
    }
    return `${strategyClasses.slice(0, 2).join(', ')} 等 ${strategyClasses.length} 个`;
}

function formatNullableNumber(value) {
    if (value === null || value === undefined || value === '') {
        return '--';
    }
    return String(value);
}

function formatGainPercent(value) {
    const parsed = parseFloat(value);
    if (!Number.isFinite(parsed)) {
        return '--';
    }
    return `${parsed.toFixed(2)}%`;
}

function renderStatus(status) {
    const textByStatus = {
        queued: '排队中',
        running: '运行中',
        completed: '已完成',
        failed: '失败',
    };
    const normalized = status || '--';
    return `<span class="status-badge status-${escapeHtml(normalized)}">${textByStatus[normalized] || normalized}</span>`;
}

function initializeBacktestForm() {
    const form = document.getElementById('backtest-form');
    const batchBtn = document.getElementById('batch-backtest-btn');

    if (!form) {
        return;
    }

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await runSingleBacktest();
    });

    batchBtn.addEventListener('click', function() {
        alert('批量回测功能开发中');
    });
}

async function runSingleBacktest() {
    const formData = getBacktestFormData();
    showLoading(true);
    hideResults();

    try {
        const result = await simulateBacktest(formData);
        displayBacktestResults(result);
        saveToHistory(result);
    } catch (error) {
        alert(`回测失败: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

function getBacktestFormData() {
    return {
        stockCode: document.getElementById('stock-code').value,
        strategy: document.getElementById('strategy-select').value,
        startDate: formatDate(document.getElementById('start-date').value),
        endDate: formatDate(document.getElementById('end-date').value),
        initialCash: parseFloat(document.getElementById('initial-cash').value),
        commission: parseFloat(document.getElementById('commission').value),
    };
}

async function simulateBacktest(params) {
    await new Promise(resolve => setTimeout(resolve, 800));

    const totalReturn = (Math.random() * 0.4 - 0.1).toFixed(4);
    const annualizedReturn = totalReturn;
    const sharpeRatio = (Math.random() * 2 + 0.5).toFixed(2);
    const maxDrawdown = (Math.random() * 0.15 + 0.05).toFixed(4);
    const totalTrades = Math.floor(Math.random() * 20 + 5);
    const winningTrades = Math.floor(totalTrades * (Math.random() * 0.3 + 0.5));
    const losingTrades = totalTrades - winningTrades;
    const winRate = (winningTrades / totalTrades).toFixed(2);
    const finalValue = params.initialCash * (1 + parseFloat(totalReturn));
    const equityData = generateEquityCurve(params.initialCash, totalReturn, 252);

    return {
        stockCode: params.stockCode,
        strategyName: params.strategy,
        startDate: params.startDate,
        endDate: params.endDate,
        initialCash: params.initialCash,
        finalValue: finalValue.toFixed(2),
        totalReturn,
        annualizedReturn,
        sharpeRatio,
        maxDrawdown,
        totalTrades,
        winningTrades,
        losingTrades,
        winRate,
        equityData,
    };
}

function generateEquityCurve(initialCash, totalReturn, days) {
    const data = [];
    const labels = [];
    let currentValue = initialCash;
    const dailyReturn = Math.pow(1 + parseFloat(totalReturn), 1 / days) - 1;

    for (let i = 0; i <= days; i++) {
        if (i % 5 === 0) {
            labels.push(`Day ${i}`);
            data.push(currentValue.toFixed(2));
        }
        currentValue *= 1 + dailyReturn + (Math.random() - 0.5) * 0.02;
    }

    return { labels, data };
}

function displayBacktestResults(result) {
    document.getElementById('metric-return').textContent = formatPercent(result.totalReturn);
    document.getElementById('metric-annualized').textContent = formatPercent(result.annualizedReturn);
    document.getElementById('metric-sharpe').textContent = result.sharpeRatio;
    document.getElementById('metric-drawdown').textContent = formatPercent(result.maxDrawdown);
    document.getElementById('metric-trades').textContent = result.totalTrades;
    document.getElementById('metric-winrate').textContent = formatPercent(result.winRate);

    document.getElementById('detail-stock').textContent = result.stockCode;
    document.getElementById('detail-strategy').textContent = result.strategyName;
    document.getElementById('detail-period').textContent = `${result.startDate} ~ ${result.endDate}`;
    document.getElementById('detail-initial').textContent = formatCurrency(result.initialCash);
    document.getElementById('detail-final').textContent = formatCurrency(result.finalValue);
    document.getElementById('detail-winning').textContent = result.winningTrades;
    document.getElementById('detail-losing').textContent = result.losingTrades;

    drawEquityChart(result.equityData);
    document.getElementById('backtest-results').classList.remove('hidden');
}

function drawEquityChart(equityData) {
    const ctx = document.getElementById('equity-chart').getContext('2d');
    if (equityChart) {
        equityChart.destroy();
    }

    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: equityData.labels,
            datasets: [{
                label: '账户资金',
                data: equityData.data,
                borderColor: '#1890ff',
                backgroundColor: 'rgba(24, 144, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    beginAtZero: false,
                },
            },
        },
    });
}

function initializeOptimizationForm() {
    const form = document.getElementById('optimization-form');
    if (!form) {
        return;
    }
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        alert('参数优化不在当前版本范围内');
    });
}

function showLoading(show) {
    const indicator = document.getElementById('loading-indicator');
    indicator.classList.toggle('hidden', !show);
}

function hideResults() {
    document.getElementById('backtest-results').classList.add('hidden');
}

function formatDate(dateStr) {
    return dateStr ? dateStr.replace(/-/g, '') : null;
}

function toDateInput(date) {
    return date.toISOString().slice(0, 10);
}

function formatDateTime(value) {
    if (!value) {
        return '--';
    }
    return value.replace('T', ' ').slice(0, 16);
}

function parseStockCodes(value) {
    const codes = value
        .split(/[\s,，;；]+/)
        .map(item => item.trim())
        .filter(Boolean);
    return codes.length ? codes : null;
}

function formatPercent(value) {
    return `${(parseFloat(value) * 100).toFixed(2)}%`;
}

function formatCurrency(value) {
    return `¥${parseFloat(value).toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
}

function saveToHistory(result) {
    backtestHistory.unshift({
        ...result,
        timestamp: new Date().toISOString(),
    });

    if (backtestHistory.length > 50) {
        backtestHistory.pop();
    }

    updateResultsTable();
}

function loadBacktestHistory() {
    const saved = localStorage.getItem('backtestHistory');
    if (saved) {
        backtestHistory = JSON.parse(saved);
        updateResultsTable();
    }
}

function updateResultsTable() {
    const tbody = document.getElementById('results-tbody');

    if (backtestHistory.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">暂无回测记录</td></tr>';
        return;
    }

    tbody.innerHTML = backtestHistory.map((record, index) => `
        <tr>
            <td>${escapeHtml(record.stockCode)}</td>
            <td>${escapeHtml(record.strategyName)}</td>
            <td>${escapeHtml(record.startDate)} ~ ${escapeHtml(record.endDate)}</td>
            <td style="color: ${parseFloat(record.totalReturn) >= 0 ? '#52c41a' : '#ff4d4f'}">
                ${formatPercent(record.totalReturn)}
            </td>
            <td>${escapeHtml(record.sharpeRatio)}</td>
            <td style="color: #ff4d4f">${formatPercent(record.maxDrawdown)}</td>
            <td>${escapeHtml(record.totalTrades)}</td>
            <td>
                <button class="btn btn-secondary compact-btn" onclick="viewDetail(${index})">
                    查看
                </button>
            </td>
        </tr>
    `).join('');

    localStorage.setItem('backtestHistory', JSON.stringify(backtestHistory));
}

function viewDetail(index) {
    const record = backtestHistory[index];
    displayBacktestResults(record);
    switchPage('backtest');
}

function switchPage(page) {
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelector(`[data-page="${page}"]`).classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`${page}-page`).classList.add('active');
}

async function apiFetch(path, options = {}) {
    const apiUrls = getApiBaseUrlCandidates();
    let lastError = null;

    for (const baseUrl of apiUrls) {
        try {
            const response = await fetchWithTimeout(`${baseUrl}${path}`, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...(options.headers || {}),
                },
            });
            const data = await response.json().catch(() => null);
            if (!response.ok) {
                const error = new Error(data?.detail || `HTTP ${response.status}`);
                error.status = response.status;
                throw error;
            }
            rememberApiBaseUrl(baseUrl);
            return data;
        } catch (error) {
            lastError = error;
            if (error.status && error.status < 500) {
                break;
            }
        }
    }

    throw lastError || new Error('API 请求失败');
}

function resolveApiBaseUrl() {
    const params = new URLSearchParams(window.location.search);
    const configuredUrl = params.get('api');
    if (configuredUrl) {
        const normalizedUrl = configuredUrl.replace(/\/$/, '');
        localStorage.setItem('apiBaseUrl', normalizedUrl);
        return normalizedUrl;
    }
    return (localStorage.getItem('apiBaseUrl') || inferLocalApiBaseUrl()).replace(/\/$/, '');
}

function getApiBaseUrlCandidates() {
    const candidates = [
        API_BASE_URL,
        inferLocalApiBaseUrl(),
        'http://127.0.0.1:8001/api/v1',
        'http://127.0.0.1:8000/api/v1',
    ];
    return [...new Set(candidates.map(url => url.replace(/\/$/, '')))];
}

function inferLocalApiBaseUrl() {
    const host = window.location.hostname || '127.0.0.1';
    if (['127.0.0.1', 'localhost'].includes(host) && window.location.port === '8080') {
        return `http://${host}:8001/api/v1`;
    }
    return 'http://127.0.0.1:8001/api/v1';
}

function rememberApiBaseUrl(baseUrl) {
    API_BASE_URL = baseUrl.replace(/\/$/, '');
    localStorage.setItem('apiBaseUrl', API_BASE_URL);
    return API_BASE_URL;
}

async function fetchWithTimeout(url, options, timeoutMs = 12000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await fetch(url, {
            ...options,
            signal: controller.signal,
        });
    } finally {
        clearTimeout(timer);
    }
}

function setButtonLoading(button, loading, loadingText) {
    if (!button) {
        return;
    }
    if (loading) {
        button.dataset.originalText = button.textContent;
        button.textContent = loadingText;
        button.disabled = true;
    } else {
        button.textContent = button.dataset.originalText || loadingText;
        button.disabled = false;
    }
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
