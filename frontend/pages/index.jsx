import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import GraphCanvas from '../components/GraphCanvas';

const PRESETS = [
  { label: '♟️ Chess (Local)', value: 'C:\\Users\\Naman Sanotiya\\OneDrive\\Desktop\\PROJECTS\\chess\\Chess', k: 2 },
  { label: '🧪 Auth Demo (Built-in)', value: 'sample_repo', k: 2 },
  { label: '🍾 Bottle (GitHub)', value: 'bottlepy/bottle', k: 1 },
  { label: '⚡ Flask (GitHub)', value: 'pallets/flask', k: 1 }
];

export default function Home() {
  const [repoInput, setRepoInput] = useState('sample_repo');
  const [kHops, setKHops] = useState(2);
  const [customDiff, setCustomDiff] = useState('');
  const [showDiffInput, setShowDiffInput] = useState(false);
  const [activeTab, setActiveTab] = useState('risks');
  const [nodeSearch, setNodeSearch] = useState('');
  const [copiedTest, setCopiedTest] = useState(null);

  const [loading, setLoading] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [loadingStep, setLoadingStep] = useState(0);

  // Selected/Hovered state from graph
  const [hoveredNode, setHoveredNode] = useState(null);
  const [affectedList, setAffectedList] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);

  // Run on initial mount
  useEffect(() => {
    runAnalysis('sample_repo', 2);
  }, []);

  // Step ticker while loading
  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      return;
    }
    const interval = setInterval(() => {
      setLoadingStep(s => (s < 3 ? s + 1 : s));
    }, 4500);
    return () => clearInterval(interval);
  }, [loading]);

  const runAnalysis = async (target = repoInput, hops = kHops) => {
    setLoading(true);
    setErrorMsg('');
    setLoadingStep(0);
    try {
      const isGithub = target.includes('/') && !target.startsWith('/') && !target.startsWith('.') && !target.includes(':');
      const payload = {
        k: hops,
        diff_text: customDiff.trim() || undefined
      };
      if (isGithub) {
        payload.github_url = target;
      } else {
        payload.repo_path = target;
      }

      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || 'Failed to analyze repository');
      }

      setAnalysisData(data);
      setSelectedNode(null);
      setHoveredNode(null);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleNodeHover = (node, affected) => {
    setHoveredNode(node);
    setAffectedList(affected || []);
  };

  const copyToClipboard = (text, id) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      setCopiedTest(id);
      setTimeout(() => setCopiedTest(null), 2000);
    }
  };

  const activeInspectNode = selectedNode || hoveredNode;

  // File breakdown grouping
  const fileSummary = React.useMemo(() => {
    if (!analysisData?.nodes) return [];
    const map = new Map();
    analysisData.nodes.forEach(n => {
      const f = n.file || 'unknown';
      if (!map.has(f)) {
        map.set(f, { file: f, seeds: 0, callers: 0, total: 0, nodes: [] });
      }
      const entry = map.get(f);
      entry.total++;
      if (n.status === 'seed') entry.seeds++;
      else entry.callers++;
      entry.nodes.push(n);
    });
    return Array.from(map.values()).sort((a, b) => (b.seeds * 10 + b.callers) - (a.seeds * 10 + a.callers));
  }, [analysisData]);

  const loadingSteps = [
    '📂 Ingesting repository files & building Symbol Index...',
    '🌲 Parsing AST definitions, references & typed invocation edges...',
    '🕸️ Computing Weighted Graph Traversal & Personalized PageRank...',
    '⚡ Synthesizing Test Recommendations & Co-Change Intelligence...'
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#030712', color: '#f8fafc', fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
      <Head>
        <title>Codelysis — Code Change Impact & Risk Intelligence</title>
        <meta name="description" content="Graph-RAG Code Change Impact Analysis, Error Prediction & Co-Change Recommendations" />
      </Head>

      {/* Modern Top Header */}
      <header style={{
        borderBottom: '1px solid #1e293b',
        background: 'rgba(3, 7, 18, 0.92)',
        backdropFilter: 'blur(16px)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        padding: '12px 24px'
      }}>
        <div style={{ maxWidth: 1720, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          
          {/* Logo & Product Tagline */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: 'linear-gradient(135deg, #0284c7, #6366f1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: 20,
              color: '#fff',
              boxShadow: '0 4px 14px rgba(2, 132, 199, 0.4)'
            }}>
              C
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em', color: '#f8fafc' }}>
                  Codelysis
                </span>
                <span style={{
                  fontSize: 10,
                  background: 'rgba(56, 189, 248, 0.12)',
                  color: '#38bdf8',
                  padding: '2px 8px',
                  borderRadius: 9999,
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  fontWeight: 600
                }}>
                  RepoGraph ICLR 2025
                </span>
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>
                Change-Conditioned Impact Analysis & Test Selection
              </div>
            </div>
          </div>

          {/* 4 Clean Metric Cards */}
          {analysisData && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ background: '#0b1329', border: '1px solid #1e293b', padding: '6px 14px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>🎯</span>
                <div>
                  <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Changed Code</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#ef4444' }}>
                    {analysisData.seed_nodes?.length || 0} modified
                  </div>
                </div>
              </div>

              <div style={{ background: '#0b1329', border: '1px solid #1e293b', padding: '6px 14px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>⚡</span>
                <div>
                  <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Critical Callers</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#f97316' }}>
                    {analysisData.direct_callers_count || 0} direct
                  </div>
                </div>
              </div>

              <div style={{ background: '#0b1329', border: '1px solid #1e293b', padding: '6px 14px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>🧪</span>
                <div>
                  <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Tests to Run</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#06b6d4' }}>
                    {analysisData.test_recommendations?.length || 0} suites
                  </div>
                </div>
              </div>

              <div style={{ background: '#0b1329', border: '1px solid #1e293b', padding: '6px 14px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>🕸️</span>
                <div>
                  <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Ego Network</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#a855f7' }}>
                    {analysisData.nodes?.length || 0} nodes · {analysisData.edges?.length || 0} edges
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </header>

      {/* Main Workspace */}
      <main style={{ maxWidth: 1720, margin: '0 auto', padding: '18px 24px' }}>
        
        {/* Repo Search & Control Strip */}
        <div style={{
          background: '#0b1329',
          border: '1px solid #1e293b',
          borderRadius: 12,
          padding: '14px 18px',
          marginBottom: 16
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
            
            {/* Input Box */}
            <div style={{ flex: 1, minWidth: 320, display: 'flex', alignItems: 'center', background: '#030712', border: '1px solid #334155', borderRadius: 8, padding: '0 12px' }}>
              <span style={{ fontSize: 14, color: '#64748b', marginRight: 8 }}>📁</span>
              <input
                type="text"
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runAnalysis(repoInput, kHops)}
                placeholder="Enter repository folder path or GitHub repo (e.g. sample_repo, bottlepy/bottle)..."
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: 'none',
                  padding: '10px 0',
                  color: '#f8fafc',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
            </div>

            {/* Depth Selector with friendly labels */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#030712', padding: '5px 10px', borderRadius: 8, border: '1px solid #334155' }}>
              <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }}>Trace Depth:</span>
              {[
                { k: 1, label: 'k=1 Quick' },
                { k: 2, label: 'k=2 Recommended' },
                { k: 3, label: 'k=3 Deep' }
              ].map(item => (
                <button
                  key={item.k}
                  onClick={() => setKHops(item.k)}
                  style={{
                    background: kHops === item.k ? '#0284c7' : 'transparent',
                    color: kHops === item.k ? '#fff' : '#94a3b8',
                    border: 'none',
                    borderRadius: 6,
                    padding: '4px 9px',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontWeight: 600
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* Custom Diff Button */}
            <button
              onClick={() => setShowDiffInput(!showDiffInput)}
              style={{
                background: showDiffInput ? '#1e293b' : '#030712',
                border: '1px solid #334155',
                color: '#cbd5e1',
                padding: '8px 12px',
                borderRadius: 8,
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 500
              }}
            >
              {showDiffInput ? 'Hide Git Diff' : 'Custom Git Diff ▾'}
            </button>

            {/* Primary Action Button */}
            <button
              onClick={() => runAnalysis(repoInput, kHops)}
              disabled={loading}
              style={{
                background: loading ? '#334155' : 'linear-gradient(135deg, #0284c7, #4f46e5)',
                color: '#fff',
                border: 'none',
                padding: '9px 22px',
                borderRadius: 8,
                cursor: loading ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                fontSize: 13,
                boxShadow: '0 4px 14px rgba(2, 132, 199, 0.35)',
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}
            >
              {loading ? (
                <>
                  <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⟳</span>
                  Analyzing...
                </>
              ) : (
                '🚀 Analyze Impact'
              )}
            </button>

          </div>

          {/* Quick Presets for Instant 1-Click Testing */}
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748b', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 500 }}>Quick Presets:</span>
            {PRESETS.map((p, i) => (
              <button
                key={i}
                onClick={() => {
                  setRepoInput(p.value);
                  setKHops(p.k);
                  runAnalysis(p.value, p.k);
                }}
                style={{
                  background: '#030712',
                  border: '1px solid #1e293b',
                  color: '#38bdf8',
                  padding: '3px 10px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 11,
                  fontWeight: 500,
                  transition: 'all 0.2s'
                }}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Custom Diff Box */}
          {showDiffInput && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                Paste a unified Git diff (e.g. <code>@@ -4,7 +4,7 @@</code>) or leave blank to automatically detect modified lines:
              </div>
              <textarea
                rows={4}
                value={customDiff}
                onChange={(e) => setCustomDiff(e.target.value)}
                placeholder="diff --git a/file.cpp b/file.cpp ..."
                style={{
                  width: '100%',
                  background: '#030712',
                  border: '1px solid #334155',
                  borderRadius: 8,
                  padding: 10,
                  color: '#cbd5e1',
                  fontFamily: 'monospace',
                  fontSize: 11,
                  outline: 'none'
                }}
              />
            </div>
          )}

          {/* Friendly Error Display */}
          {errorMsg && (
            <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', borderRadius: 8, fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <div>⚠️ <strong>Notice:</strong> {errorMsg}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  onClick={() => { setKHops(1); runAnalysis(repoInput, 1); }}
                  style={{ background: '#1e293b', border: '1px solid #ef4444', color: '#fff', borderRadius: 4, padding: '3px 8px', fontSize: 11, cursor: 'pointer' }}
                >
                  Retry with k=1
                </button>
                <button
                  onClick={() => setErrorMsg('')}
                  style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 14, cursor: 'pointer', padding: '0 4px', lineHeight: 1 }}
                  title="Dismiss notice"
                >
                  ✕
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Loading Banner when analyzing */}
        {loading && (
          <div style={{
            background: 'linear-gradient(90deg, rgba(2, 132, 199, 0.15), rgba(99, 102, 241, 0.15))',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: 10,
            padding: '14px 20px',
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 14
          }}>
            <div style={{ fontSize: 24, animation: 'spin 1.5s linear infinite' }}>⚙️</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#38bdf8' }}>
                Analyzing codebase impact with RepoGraph...
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                {loadingSteps[loadingStep]}
              </div>
            </div>
          </div>
        )}

        {/* 2-Column Split Workspace */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(0, 1.2fr)', gap: 16, alignItems: 'start' }}>
          
          {/* Left Column: Interactive Graph Viewport */}
          <div style={{ position: 'relative', height: 720, display: 'flex', flexDirection: 'column' }}>
            
            {/* Top Toolbar in Graph */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 8,
              background: '#0b1329',
              padding: '6px 14px',
              borderRadius: 8,
              border: '1px solid #1e293b'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
                <span style={{ fontWeight: 600, color: '#f8fafc' }}>Interactive Impact Graph</span>
                <span style={{ color: '#64748b' }}>({analysisData?.nodes?.length || 0} symbols in ego-network)</span>
              </div>

              {/* Node Search Box */}
              <div style={{ display: 'flex', alignItems: 'center', background: '#030712', border: '1px solid #334155', borderRadius: 6, padding: '2px 8px' }}>
                <span style={{ fontSize: 11, color: '#64748b', marginRight: 4 }}>🔍</span>
                <input
                  type="text"
                  value={nodeSearch}
                  onChange={(e) => setNodeSearch(e.target.value)}
                  placeholder="Find function in graph..."
                  style={{ background: 'transparent', border: 'none', color: '#f8fafc', fontSize: 11, outline: 'none', width: 140 }}
                />
              </div>
            </div>

            {/* Canvas Container */}
            <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
              <GraphCanvas
                nodes={analysisData?.nodes || []}
                edges={analysisData?.edges || []}
                onNodeHover={handleNodeHover}
                selectedNodeId={selectedNode?.id}
                onSelectNode={(node) => setSelectedNode(node)}
                searchQuery={nodeSearch}
              />
            </div>

            {/* Floating Interactive Inspect Card */}
            {activeInspectNode && (
              <div style={{
                position: 'absolute',
                top: 50,
                left: 14,
                width: 340,
                background: 'rgba(11, 19, 41, 0.94)',
                backdropFilter: 'blur(14px)',
                border: '1px solid #334155',
                borderRadius: 10,
                padding: 14,
                boxShadow: '0 12px 32px rgba(0, 0, 0, 0.65)',
                zIndex: 20
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: activeInspectNode.status === 'seed' ? '#ef4444' : activeInspectNode.status?.includes('direct') ? '#f97316' : '#0284c7',
                    color: '#fff'
                  }}>
                    {activeInspectNode.status === 'seed' ? '⚡ MODIFIED SEED' : activeInspectNode.status?.includes('direct') ? '⚡ DIRECT CALLER' : 'SYMBOL'}
                  </span>
                  {selectedNode && (
                    <button
                      onClick={() => setSelectedNode(null)}
                      style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 12 }}
                    >
                      ✕ Close
                    </button>
                  )}
                </div>

                <div style={{ fontSize: 14, fontWeight: 700, color: '#f8fafc', marginTop: 8 }}>
                  {activeInspectNode.name}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2, fontFamily: 'monospace' }}>
                  {activeInspectNode.file}:{activeInspectNode.line}
                </div>

                {activeInspectNode.snippet && (
                  <div style={{ marginTop: 8, padding: '6px 8px', background: '#030712', border: '1px solid #1e293b', borderRadius: 6, fontFamily: 'monospace', fontSize: 10, color: '#cbd5e1', overflowX: 'auto' }}>
                    {activeInspectNode.snippet}
                  </div>
                )}

                {/* Downstream Affected Nodes */}
                <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid #1e293b' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#f97316' }}>
                    ⚡ Impacted Callers in Graph ({affectedList.length})
                  </div>
                  <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 130, overflowY: 'auto' }}>
                    {affectedList.length === 0 ? (
                      <span style={{ fontSize: 10, color: '#64748b' }}>No downstream callers in this neighborhood.</span>
                    ) : (
                      affectedList.slice(0, 10).map(aff => (
                        <div key={aff.id} style={{ background: '#030712', padding: '4px 6px', borderRadius: 4, fontSize: 10, display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ fontWeight: 600, color: '#f8fafc' }}>{aff.name}</span>
                          <span style={{ color: '#64748b' }}>{aff.file?.split('/').pop()}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: 4 Streamlined Tabs */}
          <div style={{
            background: '#0b1329',
            border: '1px solid #1e293b',
            borderRadius: 12,
            height: 720,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            
            {/* Clean Tab Header */}
            <div style={{ display: 'flex', borderBottom: '1px solid #1e293b', background: '#030712' }}>
              {[
                { id: 'risks', label: 'Priority Risks', icon: '🚨', count: analysisData?.ranked_impact_nodes?.length },
                { id: 'tests', label: 'Tests to Run', icon: '🧪', count: analysisData?.test_recommendations?.length },
                { id: 'files', label: 'Affected Files', icon: '📁', count: fileSummary.length },
                { id: 'summary', label: 'Report', icon: '📝' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    flex: 1,
                    padding: '12px 6px',
                    border: 'none',
                    background: activeTab === tab.id ? '#0b1329' : 'transparent',
                    color: activeTab === tab.id ? '#38bdf8' : '#94a3b8',
                    borderBottom: activeTab === tab.id ? '2px solid #38bdf8' : 'none',
                    cursor: 'pointer',
                    fontSize: 12,
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                    transition: 'all 0.15s'
                  }}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                  {tab.count !== undefined && tab.count > 0 && (
                    <span style={{ fontSize: 10, background: activeTab === tab.id ? '#0284c7' : '#1e293b', color: '#fff', padding: '1px 6px', borderRadius: 9999 }}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Tab Contents */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>

              {/* TAB 1: PRIORITY RISKS & IMPACTED FUNCTIONS */}
              {activeTab === 'risks' && (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>
                      Impacted Functions & Call Sites
                    </div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>
                      Ranked by graph connection strength and co-change frequency.
                    </div>
                  </div>

                  {!analysisData?.ranked_impact_nodes || analysisData.ranked_impact_nodes.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b', fontSize: 13 }}>
                      No impacted downstream functions detected for this changeset.
                    </div>
                  ) : (
                    analysisData.ranked_impact_nodes.map((node) => {
                      const sevColor = node.severity === 'CRITICAL' ? '#ef4444' :
                                       node.severity === 'HIGH' ? '#f97316' :
                                       node.severity === 'MEDIUM' ? '#eab308' : '#64748b';
                      const sevBg = node.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.15)' :
                                    node.severity === 'HIGH' ? 'rgba(249, 115, 22, 0.15)' :
                                    node.severity === 'MEDIUM' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(100, 116, 139, 0.15)';

                      return (
                        <div
                          key={node.node_id}
                          style={{
                            background: '#030712',
                            border: `1px solid ${node.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.4)' : '#1e293b'}`,
                            borderRadius: 8,
                            padding: 12,
                            marginBottom: 10
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b' }}>#{node.rank}</span>
                              <span style={{
                                fontSize: 10,
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: 4,
                                background: sevBg,
                                color: sevColor
                              }}>
                                {node.severity} IMPACT
                              </span>
                            </div>
                            <span style={{ fontSize: 11, color: '#38bdf8', fontWeight: 600 }}>
                              Score: {(node.hybrid_score || node.impact_score || 0).toFixed(2)}
                            </span>
                          </div>

                          <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>
                            {node.name}
                          </div>

                          <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace', marginTop: 2 }}>
                            {node.file}:{node.line}
                          </div>

                          {node.explanation && (
                            <div style={{ fontSize: 11, color: '#cbd5e1', marginTop: 6, lineHeight: 1.4 }}>
                              <strong>Reason:</strong> {node.explanation}
                            </div>
                          )}

                          {node.is_modification_required && (
                            <div style={{ marginTop: 6, padding: '4px 8px', background: 'rgba(239, 68, 68, 0.15)', borderRadius: 4, fontSize: 10, color: '#fca5a5', fontWeight: 600 }}>
                              ⚠️ Signature or interface updated: callers must be verified
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* TAB 2: TESTS TO RUN */}
              {activeTab === 'tests' && (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>
                      Recommended Tests to Execute
                    </div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>
                      Test Impact Analysis (TIA) identifies tests exercising changed functions.
                    </div>
                  </div>

                  {!analysisData?.test_recommendations || analysisData.test_recommendations.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px 20px', color: '#94a3b8', fontSize: 12, background: '#030712', borderRadius: 8, border: '1px solid #1e293b' }}>
                      <div style={{ fontSize: 24, marginBottom: 8 }}>🧪</div>
                      <div style={{ fontWeight: 600, color: '#f8fafc' }}>No automated test suites identified for this changeset.</div>
                      <div style={{ marginTop: 4, color: '#64748b' }}>
                        If this repository uses manual testing or custom harnesses, verify the modified functions directly.
                      </div>
                    </div>
                  ) : (
                    analysisData.test_recommendations.map((t, idx) => {
                      const testCmd = t.test_file ? `pytest ${t.test_file} -k ${t.test_name}` : `npm test`;
                      return (
                        <div
                          key={idx}
                          style={{
                            background: '#030712',
                            border: '1px solid #1e293b',
                            borderRadius: 8,
                            padding: 12,
                            marginBottom: 10
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                            <span style={{
                              fontSize: 10,
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 4,
                              background: t.classification === 'directly_related' ? 'rgba(6, 182, 212, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                              color: t.classification === 'directly_related' ? '#38bdf8' : '#94a3b8'
                            }}>
                              {t.classification === 'directly_related' ? '⚡ DIRECT TEST' : 'TRANSITIVE TEST'}
                            </span>
                            <span style={{ fontSize: 11, color: '#38bdf8', fontWeight: 600 }}>
                              Score: {Math.round((t.impact_score || 0.8) * 100)}%
                            </span>
                          </div>

                          <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>
                            {t.test_name}
                          </div>
                          <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace', marginTop: 2 }}>
                            {t.test_file}
                          </div>

                          {t.evidence && (
                            <div style={{ fontSize: 11, color: '#cbd5e1', marginTop: 6 }}>
                              {t.evidence}
                            </div>
                          )}

                          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#0b1329', padding: '6px 10px', borderRadius: 6 }}>
                            <code style={{ fontSize: 11, color: '#38bdf8' }}>{testCmd}</code>
                            <button
                              onClick={() => copyToClipboard(testCmd, idx)}
                              style={{
                                background: '#1e293b',
                                border: 'none',
                                color: copiedTest === idx ? '#4ade80' : '#cbd5e1',
                                padding: '3px 8px',
                                borderRadius: 4,
                                cursor: 'pointer',
                                fontSize: 10,
                                fontWeight: 600
                              }}
                            >
                              {copiedTest === idx ? '✓ Copied' : 'Copy'}
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* TAB 3: AFFECTED FILES */}
              {activeTab === 'files' && (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>
                      Affected Files Overview ({fileSummary.length})
                    </div>
                    <div style={{ fontSize: 11, color: '#94a3b8' }}>
                      All files with modified code or impacted callers.
                    </div>
                  </div>

                  {fileSummary.map((item, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: '#030712',
                        border: '1px solid #1e293b',
                        borderRadius: 8,
                        padding: 10,
                        marginBottom: 8
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: item.seeds > 0 ? '#fca5a5' : '#f8fafc', fontFamily: 'monospace' }}>
                          {item.file}
                        </span>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {item.seeds > 0 && (
                            <span style={{ fontSize: 9, background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>
                              {item.seeds} modified
                            </span>
                          )}
                          <span style={{ fontSize: 9, background: '#1e293b', color: '#94a3b8', padding: '1px 6px', borderRadius: 4 }}>
                            {item.callers} callers
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 4: EXECUTIVE REPORT */}
              {activeTab === 'summary' && (
                <div>
                  <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>
                      Action Checklist & Impact Report
                    </div>
                    <button
                      onClick={() => copyToClipboard(analysisData?.markdown_report || '', 'report')}
                      style={{ background: '#0284c7', border: 'none', color: '#fff', padding: '4px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600 }}
                    >
                      {copiedTest === 'report' ? '✓ Copied' : '📋 Copy Report'}
                    </button>
                  </div>

                  <div style={{ background: '#030712', border: '1px solid #1e293b', borderRadius: 8, padding: 14 }}>
                    <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: 11, color: '#cbd5e1', margin: 0, lineHeight: 1.5 }}>
                      {analysisData?.markdown_report || 'No report generated.'}
                    </pre>
                  </div>
                </div>
              )}

            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
