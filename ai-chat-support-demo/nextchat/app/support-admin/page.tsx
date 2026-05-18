"use client";

import { useEffect, useMemo, useState } from "react";

import styles from "./support-admin.module.scss";

type RiskLevel = "none" | "low" | "medium" | "high" | "crisis";

type Signal = {
  key: string;
  label: string;
  severity: RiskLevel;
  confidence: number;
  source: string;
  evidence: string[];
  suggested_action: string;
  diagnostic: boolean;
};

type ContextAnalysisRecord = {
  analysis_id: string;
  application_id: string;
  external_user_id: string;
  conversation_id: string;
  risk_level: RiskLevel;
  response: {
    risk_level: RiskLevel;
    risk_score: number;
    cluster: string;
    confidence: number;
    signals: Signal[];
    immediate_actions: string[];
    human_review_recommended: boolean;
    escalation_required: boolean;
    evidence_window: string[];
    diagnostic: boolean;
    created_at: string;
  };
  created_at: string;
};

const ADMIN_TOKEN_KEY = "distilled-ti-admin-token";
const PAGE_SIZE = 8;
const riskLabels: Record<RiskLevel, string> = {
  none: "无",
  low: "低",
  medium: "中",
  high: "高",
  crisis: "危机",
};

export default function SupportAdminPage() {
  const [items, setItems] = useState<ContextAnalysisRecord[]>([]);
  const [minRisk, setMinRisk] = useState<RiskLevel>("medium");
  const [adminToken, setAdminToken] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const highPriorityCount = useMemo(
    () =>
      items.filter((item) =>
        ["high", "crisis"].includes(item.response.risk_level),
      ).length,
    [items],
  );
  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const safePageIndex = Math.min(pageIndex, pageCount - 1);
  const visibleItems = useMemo(
    () =>
      items.slice(
        safePageIndex * PAGE_SIZE,
        safePageIndex * PAGE_SIZE + PAGE_SIZE,
      ),
    [items, safePageIndex],
  );
  const firstVisibleItem = items.length === 0 ? 0 : safePageIndex * PAGE_SIZE + 1;
  const lastVisibleItem = Math.min(items.length, (safePageIndex + 1) * PAGE_SIZE);

  async function loadAlerts(token = adminToken, risk = minRisk) {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/distilled/alerts?min_risk=${risk}&limit=50`,
        {
          headers: token ? { "X-Distilled-Admin-Token": token } : {},
          cache: "no-store",
        },
      );
      if (!response.ok) {
        throw new Error(`alerts_failed_${response.status}`);
      }
      const payload = await response.json();
      setItems(payload.items || []);
      setPageIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "unknown_error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const storedToken = window.localStorage.getItem(ADMIN_TOKEN_KEY) || "";
    setAdminToken(storedToken);
    loadAlerts(storedToken, minRisk);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function saveToken(value: string) {
    setAdminToken(value);
    window.localStorage.setItem(ADMIN_TOKEN_KEY, value);
  }

  function changeRisk(value: RiskLevel) {
    setMinRisk(value);
    setPageIndex(0);
    loadAlerts(adminToken, value);
  }

  function goToPage(nextIndex: number) {
    setPageIndex(Math.min(Math.max(nextIndex, 0), pageCount - 1));
  }

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <section className={styles.hero}>
          <div>
            <p className={styles.eyebrow}>Distilled TI Context API</p>
            <h1>NextChat 支持信号后台</h1>
            <p className={styles.subtitle}>
              前台用户正常聊天；这里只展示授权上下文分析产生的非诊断风险/支持信号，用于人工复核和产品安全流程。
            </p>
          </div>
          <div className={styles.metrics}>
            <div>
              <strong>{items.length}</strong>
              <span>当前命中</span>
            </div>
            <div>
              <strong>{highPriorityCount}</strong>
              <span>高优先级</span>
            </div>
          </div>
        </section>

        <section className={styles.toolbar}>
          <label>
            最低风险
            <select
              value={minRisk}
              onChange={(event) => changeRisk(event.target.value as RiskLevel)}
            >
              <option value="low">低及以上</option>
              <option value="medium">中及以上</option>
              <option value="high">高及以上</option>
              <option value="crisis">危机</option>
            </select>
          </label>
          <label>
            管理 token
            <input
              type="password"
              value={adminToken}
              onChange={(event) => saveToken(event.target.value)}
              placeholder="如配置 DISTILLED_TI_ADMIN_TOKEN 则填写"
            />
          </label>
          <button type="button" onClick={() => loadAlerts()}>
            {loading ? "加载中..." : "刷新"}
          </button>
        </section>

        {error && <div className={styles.error}>加载失败：{error}</div>}

        <section className={styles.cardsHeader}>
          <div>
            <p className={styles.eyebrow}>Review Queue</p>
            <h2>告警列表</h2>
          </div>
          <span>
            {items.length > 0
              ? `第 ${firstVisibleItem}-${lastVisibleItem} 条 / 共 ${items.length} 条`
              : "暂无记录"}
          </span>
        </section>

        {pageCount > 1 && (
          <nav className={styles.pager} aria-label="告警分页">
            <button
              type="button"
              disabled={safePageIndex === 0}
              onClick={() => goToPage(safePageIndex - 1)}
            >
              上一页
            </button>
            <div className={styles.pageButtons}>
              {Array.from({ length: pageCount }, (_, index) => (
                <button
                  key={index}
                  type="button"
                  className={index === safePageIndex ? styles.activePage : ""}
                  aria-current={index === safePageIndex ? "page" : undefined}
                  onClick={() => goToPage(index)}
                >
                  {index + 1}
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={safePageIndex >= pageCount - 1}
              onClick={() => goToPage(safePageIndex + 1)}
            >
              下一页
            </button>
          </nav>
        )}

        <section className={styles.list}>
          {visibleItems.map((item) => (
            <article
              key={item.analysis_id}
              className={`${styles.card} ${styles[item.response.risk_level]}`}
            >
              <header>
                <div>
                  <span className={styles.risk}>
                    {riskLabels[item.response.risk_level]}
                  </span>
                  <h2>{item.response.cluster}</h2>
                </div>
                <time>{new Date(item.created_at).toLocaleString()}</time>
              </header>
              <dl className={styles.meta}>
                <div>
                  <dt>用户</dt>
                  <dd>{item.external_user_id}</dd>
                </div>
                <div>
                  <dt>会话</dt>
                  <dd>{item.conversation_id}</dd>
                </div>
                <div>
                  <dt>分数</dt>
                  <dd>{item.response.risk_score.toFixed(3)}</dd>
                </div>
                <div>
                  <dt>置信</dt>
                  <dd>{item.response.confidence.toFixed(3)}</dd>
                </div>
              </dl>

              <div className={styles.block}>
                <h3>信号</h3>
                {item.response.signals.length === 0 ? (
                  <p>无结构化信号。</p>
                ) : (
                  <ul>
                    {item.response.signals.map((signal) => (
                      <li key={`${item.analysis_id}-${signal.key}`}>
                        <b>{signal.label}</b>
                        <span>
                          {signal.severity} / {signal.source} /{" "}
                          {signal.confidence.toFixed(2)}
                        </span>
                        <small>{signal.suggested_action}</small>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className={styles.block}>
                <h3>最近证据窗口</h3>
                <pre>{item.response.evidence_window.join("\n")}</pre>
              </div>

              {item.response.immediate_actions.length > 0 && (
                <div className={styles.block}>
                  <h3>建议动作</h3>
                  <ul>
                    {item.response.immediate_actions.map((action) => (
                      <li key={`${item.analysis_id}-${action}`}>{action}</li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          ))}
          {!loading && items.length === 0 && (
            <div className={styles.empty}>当前筛选下没有告警。</div>
          )}
        </section>
      </div>
    </main>
  );
}
