/**
 * frontend/static/js/app.js
 * ==========================
 * 클라이언트 로직 전체.
 *
 * 구조:
 *   CONFIG         — 상수 (모델 목록, 예시 데이터)
 *   utils          — 공통 유틸 함수
 *   api            — 백엔드 API 호출
 *   singlePage     — 단일 변환 페이지 로직
 *   comparePage    — 비교 페이지 로직
 *   init           — 초기화
 */

'use strict';

/* ══════════════════════════════════════════════════════════
   CONFIG
   ══════════════════════════════════════════════════════════ */
const CONFIG = {
  models: [
    { id: 'glm-4.7-flash-q4km',       label: 'GLM 4.7 Flash (Q4_K_M)', prov: 'Ollama', color: '#C2700A' },
    { id: 'gemma3-27',                label: 'Gemma3 27B',         prov: 'Ollama',    color: '#1D57C4' },
    { id: 'qwen2.5coder-32b',         label: 'Qwen2.5 Coder 32B', prov: 'Ollama',    color: '#6427C4' },
  ],
  examples: [
    {
      label: 'SELECT + JOIN',
      sql: `CREATE PROCEDURE GetEmployeeByDept
    @DeptID INT, @IsActive BIT = 1
AS BEGIN
    SET NOCOUNT ON;
    SELECT e.EmployeeID, e.FirstName, e.LastName,
           e.Salary, d.DeptName
    FROM   Employees e
    INNER JOIN Departments d ON e.DeptID = d.DeptID
    WHERE  e.DeptID = @DeptID AND e.IsActive = @IsActive
    ORDER BY e.LastName ASC;
END`,
    },
    {
      label: 'INSERT + OUTPUT',
      sql: `CREATE PROCEDURE CreateOrder
    @CustomerID  INT,
    @TotalAmount DECIMAL(18,2),
    @OrderID     INT OUTPUT
AS BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        INSERT INTO Orders (CustomerID, TotalAmount, OrderDate)
        VALUES (@CustomerID, @TotalAmount, GETDATE());
        SET @OrderID = SCOPE_IDENTITY();
    END TRY
    BEGIN CATCH
        RAISERROR('Insert failed', 16, 1);
    END CATCH
END`,
    },
    {
      label: '트랜잭션',
      sql: `CREATE PROCEDURE TransferFunds
    @FromAccountID INT,
    @ToAccountID   INT,
    @Amount        DECIMAL(18,2)
AS BEGIN
    BEGIN TRANSACTION;
    BEGIN TRY
        UPDATE Accounts SET Balance = Balance - @Amount
        WHERE  AccountID = @FromAccountID;
        UPDATE Accounts SET Balance = Balance + @Amount
        WHERE  AccountID = @ToAccountID;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END`,
    },
    {
      label: 'CURSOR 루프',
      sql: `CREATE PROCEDURE RecalcAllDiscounts
    @RatePercent FLOAT
AS BEGIN
    SET NOCOUNT ON;
    DECLARE @ProductID INT, @BasePrice DECIMAL(10,2);
    DECLARE cur CURSOR FOR
        SELECT ProductID, BasePrice FROM Products;
    OPEN cur;
    FETCH NEXT FROM cur INTO @ProductID, @BasePrice;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        UPDATE Products
        SET DiscountPrice = @BasePrice * (1 - @RatePercent/100)
        WHERE ProductID = @ProductID;
        FETCH NEXT FROM cur INTO @ProductID, @BasePrice;
    END
    CLOSE cur; DEALLOCATE cur;
END`,
    },
  ],
};

/* ══════════════════════════════════════════════════════════
   utils
   ══════════════════════════════════════════════════════════ */
const utils = {
  esc(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },

  modelColor(modelId) {
    return CONFIG.models.find(m => m.id === modelId)?.color ?? '#888';
  },

  modelLabel(modelId) {
    return CONFIG.models.find(m => m.id === modelId)?.label ?? modelId;
  },

  scoreBar(value, max, color) {
    const pct = Math.round(value / max * 100);
    return `
      <div style="display:flex;align-items:center;gap:5px">
        <div class="score-bar-wrap">
          <div class="score-bar" style="width:${pct}%;background:${color}"></div>
        </div>
        <span style="font-size:11px;font-family:var(--font-mono)">${value}</span>
      </div>`;
  },

  copyToClipboard(text) {
    navigator.clipboard.writeText(text ?? '');
  },

  formatElapsed(elapsedMs) {
    if (!elapsedMs || elapsedMs <= 0) return '';
    return `${(elapsedMs / 1000).toFixed(1)}초`;
  },
};

/* ══════════════════════════════════════════════════════════
   api — 백엔드 호출
   ══════════════════════════════════════════════════════════ */
const api = {
  async convert(payload) {
    const res = await fetch('/api/convert', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? err.message ?? res.statusText);
    }
    return res.json();
  },

  async compare(payload) {
    const res = await fetch('/api/compare', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? err.message ?? res.statusText);
    }
    return res.json();
  },
};

/* ══════════════════════════════════════════════════════════
   singlePage — 단일 변환 페이지
   ══════════════════════════════════════════════════════════ */
const singlePage = (() => {
  const RECENT_SQL_KEY = 'sql2python_recent_sql';
  const RECENT_SQL_LIMIT = 5;
  // 상태
  let selectedModelId = CONFIG.models[0].id;
  let selectedDb      = 'mssql';
  let outputData      = {};
  let activeTab       = 'main';

  // ── 초기화 ────────────────────────────────────────────
  function init() {
    _renderExamples();
    _renderRecentSql();
    _bindModelCards();
    _bindDbButtons();
  }

  function _renderExamples() {
    const list = document.getElementById('s-example-list');
    list.innerHTML = '';
    CONFIG.examples.forEach(ex => {
      const el = document.createElement('div');
      el.className = 'example-item';
      el.textContent = ex.label;
      el.onclick = () => {
        document.getElementById('s-sql-input').value = ex.sql;
        list.querySelectorAll('.example-item').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
      };
      list.appendChild(el);
    });
  }

  function _getRecentSql() {
    try {
      const raw = localStorage.getItem(RECENT_SQL_KEY);
      const parsed = JSON.parse(raw ?? '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function _saveRecentSql(sql) {
    const normalized = (sql ?? '').trim();
    if (!normalized) return;
    const next = [normalized, ..._getRecentSql().filter(item => item !== normalized)]
      .slice(0, RECENT_SQL_LIMIT);
    localStorage.setItem(RECENT_SQL_KEY, JSON.stringify(next));
  }

  function _renderRecentSql() {
    const list = document.getElementById('s-recent-list');
    if (!list) return;
    const items = _getRecentSql();
    list.innerHTML = '';

    if (!items.length) {
      list.innerHTML = '<div class="example-item" style="cursor:default;opacity:.7">최근 입력 없음</div>';
      return;
    }

    items.forEach(sql => {
      const preview = sql.replace(/\s+/g, ' ').trim();
      const el = document.createElement('div');
      el.className = 'example-item';
      el.textContent = preview;
      el.title = preview;
      el.onclick = () => {
        document.getElementById('s-sql-input').value = sql;
        document.querySelectorAll('#s-example-list .example-item').forEach(e => e.classList.remove('active'));
      };
      list.appendChild(el);
    });
  }

  function _bindModelCards() {
    document.querySelectorAll('#s-model-cards .model-card').forEach(card => {
      card.onclick = () => {
        const nextModelId = card.dataset.modelId;
        if (nextModelId === selectedModelId) return;
        document.querySelectorAll('#s-model-cards .model-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedModelId = nextModelId;
        clearAll(); // 모델 변경 시 입력/출력 초기화
      };
    });
  }

  function _bindDbButtons() {
    document.querySelectorAll('#s-db-seg .db-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('#s-db-seg .db-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedDb = btn.dataset.db;
      };
    });
  }

  // ── 상태 표시 ──────────────────────────────────────────
  function _setStatus(state, text, meta = '') {
    document.getElementById('s-status-dot').className  = `status-dot ${state}`;
    document.getElementById('s-status-text').textContent = text;
    document.getElementById('s-status-meta').textContent = meta;
  }

  // ── 출력 탭 ───────────────────────────────────────────
  function _renderOutputTabs() {
    const bar = document.getElementById('s-output-tabs');
    bar.innerHTML = '';
    const tabs = [['main', 'main.py']];
    if (outputData.test_code)   tabs.push(['test',   'test_procedure.py']);
    if (outputData.router_code) tabs.push(['router', 'router.py']);

    tabs.forEach(([id, label]) => {
      const btn = document.createElement('button');
      btn.className   = `output-tab ${id === activeTab ? 'active' : ''}`;
      btn.textContent = label;
      btn.onclick     = () => {
        activeTab = id;
        bar.querySelectorAll('.output-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _renderCode();
      };
      bar.appendChild(btn);
    });
  }

  function _renderCode() {
    const code =
      activeTab === 'main'   ? outputData.python_code  :
      activeTab === 'test'   ? outputData.test_code    :
      activeTab === 'router' ? outputData.router_code  : '';

    const scroll = document.getElementById('s-output-scroll');
    if (!code) {
      scroll.innerHTML = '<div class="output-placeholder"><div class="output-placeholder-icon">⌥</div>출력 없음</div>';
      return;
    }
    scroll.innerHTML = `<div class="code-block"><pre>${utils.esc(code)}</pre></div>`;
  }

  function _setOutputMeta(text = '') {
    const el = document.getElementById('s-output-meta');
    if (el) el.textContent = text;
  }

  // ── 퍼블릭 액션 ───────────────────────────────────────
  function clearInput() {
    document.getElementById('s-sql-input').value = '';
    document.querySelectorAll('#s-example-list .example-item').forEach(e => e.classList.remove('active'));
  }

  function clearAll() {
    clearInput();
    outputData = {};
    activeTab  = 'main';
    _setOutputMeta('');
    _renderOutputTabs();
    document.getElementById('s-output-scroll').innerHTML =
      '<div class="output-placeholder"><div class="output-placeholder-icon">⌥</div>모델을 선택하고 변환 시작을 누르세요</div>';
    _setStatus('', '대기');
  }

  function copyOutput() {
    const code =
      activeTab === 'main'   ? outputData.python_code  :
      activeTab === 'test'   ? outputData.test_code    :
      activeTab === 'router' ? outputData.router_code  : '';
    utils.copyToClipboard(code);
  }

  async function run() {
    const sql = document.getElementById('s-sql-input').value.trim();
    if (!sql) { _setStatus('error', 'SQL을 입력하세요'); return; }

    const runBtn = document.getElementById('s-run-btn');
    runBtn.disabled = true;
    _setStatus('loading', '변환 중...');

    try {
      const data = await api.convert({
        sql_code:               sql,
        target_db:              selectedDb,
        model_id:               selectedModelId,
        include_tests:          document.getElementById('s-opt-tests').checked,
        include_fastapi_router: document.getElementById('s-opt-router').checked,
      });

      outputData = data;
      _saveRecentSql(sql);
      _renderRecentSql();
      activeTab  = 'main';
      _renderOutputTabs();
      _renderCode();
      _setOutputMeta(utils.formatElapsed(data.elapsed_ms));

      const label = utils.modelLabel(data.model_id);
      const meta  = [
        data.tokens     ? `${data.tokens.toLocaleString()} tokens` : '',
        utils.formatElapsed(data.elapsed_ms),
      ].filter(Boolean).join(' · ');

      _setStatus('ok', `완료 · ${label} · ${data.line_count}줄`, meta);
    } catch (err) {
      _setStatus('error', err.message);
      _setOutputMeta('');
      document.getElementById('s-output-scroll').innerHTML =
        `<div class="output-placeholder" style="color:#ef4444">${utils.esc(err.message)}</div>`;
    } finally {
      runBtn.disabled = false;
    }
  }

  return { init, clearInput, clearAll, copyOutput, run };
})();

/* ══════════════════════════════════════════════════════════
   comparePage — 비교 페이지
   ══════════════════════════════════════════════════════════ */
const comparePage = (() => {
  let selectedDb = 'mssql';

  function init() {
    _renderExamplePills();
    _bindDbButtons();
    _bindModelChecks();
  }

  function _renderExamplePills() {
    const wrap = document.getElementById('c-example-pills');
    wrap.innerHTML = '';
    CONFIG.examples.forEach(ex => {
      const btn = document.createElement('button');
      btn.className   = 'btn-sm';
      btn.textContent = ex.label;
      btn.onclick     = () => { document.getElementById('c-sql-input').value = ex.sql; };
      wrap.appendChild(btn);
    });
  }

  function _bindDbButtons() {
    document.querySelectorAll('#c-db-seg .db-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('#c-db-seg .db-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedDb = btn.dataset.db;
      };
    });
  }

  function _bindModelChecks() {
    document.querySelectorAll('.model-check-label input').forEach(cb => {
      cb.onchange = () => cb.closest('.model-check-label').classList.toggle('checked', cb.checked);
    });
  }

  function _setStatus(state, text) {
    document.getElementById('c-status-dot').className    = `status-dot ${state}`;
    document.getElementById('c-status-text').textContent = text;
  }

  // ── 결과 렌더링 ──────────────────────────────────────
  function _renderResults(data) {
    // AI 요약
    document.getElementById('c-ai-summary').textContent = data.ai_summary ?? '';
    document.getElementById('c-winner-badge').textContent = `🏆 ${data.winner_label}`;

    // 채점 테이블
    const bestTotal = Math.max(...data.results.map(r => r.score.total));
    const tbody     = document.getElementById('c-score-tbody');
    tbody.innerHTML = '';

    data.results.forEach(({ convert: cr, score: s }) => {
      const color  = utils.modelColor(cr.model_id);
      const label  = utils.modelLabel(cr.model_id);
      const isBest = s.total === bestTotal;
      const tags   = [
        ...s.strengths.slice(0, 2).map(t => `<span class="tag tag-good">${utils.esc(t)}</span>`),
        ...s.weaknesses.slice(0, 1).map(t => `<span class="tag tag-bad">${utils.esc(t)}</span>`),
      ].join('');

      tbody.innerHTML += `
        <tr>
          <td>
            <div class="score-model-cell">
              <div style="width:7px;height:7px;border-radius:50%;background:${color};flex-shrink:0"></div>
              <span style="font-weight:500">${utils.esc(label)}</span>
              ${isBest ? '<span style="font-size:10px;color:#15803d;margin-left:4px">★ 1위</span>' : ''}
            </div>
            ${cr.elapsed_ms ? `<div style="font-size:10px;color:var(--gray-400);font-family:var(--font-mono);margin-top:2px;padding-left:15px">${utils.formatElapsed(cr.elapsed_ms)} · ${cr.line_count}줄</div>` : ''}
          </td>
          <td>${utils.scoreBar(s.correctness,    25, color)}</td>
          <td>${utils.scoreBar(s.type_hints,     20, color)}</td>
          <td>${utils.scoreBar(s.sql_safety,     20, color)}</td>
          <td>${utils.scoreBar(s.error_handling, 20, color)}</td>
          <td>${utils.scoreBar(s.readability,    15, color)}</td>
          <td><span class="score-total ${isBest ? 'score-best' : ''}">${s.total}</span></td>
          <td><div class="tag-list">${tags}</div></td>
        </tr>`;
    });

    // 항목별 미니 바차트
    const dims = [
      { key: 'correctness',    label: '문법 정확성', max: 25 },
      { key: 'type_hints',     label: '타입 힌트',   max: 20 },
      { key: 'sql_safety',     label: 'SQL 안전성',  max: 20 },
      { key: 'error_handling', label: '예외 처리',   max: 20 },
      { key: 'readability',    label: '가독성',       max: 15 },
    ];
    const grid = document.getElementById('c-mini-chart-grid');
    grid.innerHTML = '';
    dims.forEach(dim => {
      const card = document.createElement('div');
      card.className = 'mini-chart-card';
      card.innerHTML = `<div class="mini-chart-title">${dim.label} (/${dim.max})</div>` +
        data.results.map(({ convert: cr, score: s }) => {
          const color = utils.modelColor(cr.model_id);
          const label = utils.modelLabel(cr.model_id);
          const val   = s[dim.key];
          const pct   = Math.round(val / dim.max * 100);
          return `
            <div class="mini-bar-row">
              <span class="mini-bar-label" title="${utils.esc(label)}">${utils.esc(label)}</span>
              <div class="mini-bar-bg"><div class="mini-bar" style="width:${pct}%;background:${color}"></div></div>
              <span class="mini-bar-val">${val}</span>
            </div>`;
        }).join('');
      grid.appendChild(card);
    });

    // 코드 결과 카드
    const cards = document.getElementById('c-result-cards');
    cards.innerHTML = '';
    data.results.forEach(({ convert: cr, score: s }) => {
      const color  = utils.modelColor(cr.model_id);
      const label  = utils.modelLabel(cr.model_id);
      const isBest = s.total === bestTotal;
      const card   = document.createElement('div');
      card.className = 'result-card';
      card.innerHTML = `
        <div class="result-card-header">
          <div style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0"></div>
          <span class="result-model-name">${utils.esc(label)}</span>
          <div class="result-meta">
            ${s ? `<span class="meta-badge">${s.total}/100</span>` : ''}
            ${cr.elapsed_ms ? `<span class="meta-badge">${utils.formatElapsed(cr.elapsed_ms)}</span>` : ''}
            <span class="meta-badge">${cr.line_count}줄</span>
          </div>
          <button class="btn-sm" style="margin-left:6px;font-size:10px;padding:2px 8px"
            onclick="utils.copyToClipboard(${JSON.stringify(cr.python_code ?? '')})">복사</button>
        </div>
        ${cr.success && cr.python_code
          ? `<div class="result-code"><pre>${utils.esc(cr.python_code)}</pre></div>`
          : `<div class="result-error">변환 실패: ${utils.esc(cr.error ?? '알 수 없는 오류')}</div>`}
        ${isBest ? '<div class="result-winner-banner">🏆 최우수 변환 결과</div>' : ''}`;
      cards.appendChild(card);
    });

    document.getElementById('c-results').classList.add('visible');
  }

  // ── 퍼블릭 액션 ──────────────────────────────────────
  function clearAll() {
    document.getElementById('c-sql-input').value = '';
    document.getElementById('c-results').classList.remove('visible');
    document.getElementById('c-loading').classList.remove('visible');
    _setStatus('', '대기');
  }

  async function run() {
    const sql = document.getElementById('c-sql-input').value.trim();
    if (!sql) { _setStatus('error', 'SQL을 입력하세요'); return; }

    const modelIds = Array.from(
      document.querySelectorAll('.model-check-label input:checked')
    ).map(cb => cb.value);
    if (modelIds.length < 2) { _setStatus('error', '모델 2개 이상 선택'); return; }

    const runBtn = document.getElementById('c-run-btn');
    runBtn.disabled = true;
    document.getElementById('c-results').classList.remove('visible');

    const loading = document.getElementById('c-loading');
    loading.classList.add('visible');
    document.getElementById('c-loading-detail').textContent =
      modelIds.map(id => utils.modelLabel(id)).join(', ');
    _setStatus('loading', '분석 중...');

    try {
      const data = await api.compare({
        sql_code:  sql,
        target_db: selectedDb,
        model_ids: modelIds,
      });
      _renderResults(data);
      _setStatus('ok', `완료 · 🏆 ${data.winner_label}`);
    } catch (err) {
      _setStatus('error', err.message);
    } finally {
      loading.classList.remove('visible');
      runBtn.disabled = false;
    }
  }

  return { init, clearAll, run };
})();

/* ══════════════════════════════════════════════════════════
   init — 페이지 전환 + 초기화
   ══════════════════════════════════════════════════════════ */
function showPage(pageId, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.page-tab').forEach(b => b.classList.remove('active'));
  document.getElementById(`page-${pageId}`).classList.add('active');
  btn.classList.add('active');
}

document.addEventListener('DOMContentLoaded', () => {
  singlePage.init();
  comparePage.init();
});
