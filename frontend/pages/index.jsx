import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import path from 'path';
import fs from 'fs';
import { execFileSync } from 'child_process';
import GraphCanvas from '../components/GraphCanvas';

export default function Home({ initialData }) {
  const [repoInput, setRepoInput] = useState('sample_repo');
  const [kHops, setKHops] = useState(2);
  const [customDiff, setCustomDiff] = useState('');
  const [showDiffInput, setShowDiffInput] = useState(false);
  const [activeTab, setActiveTab] = useState('ranking');
  const [nodeSearch, setNodeSearch] = useState('');

  const [loading, setLoading] = useState(!initialData);
  const [analysisData, setAnalysisData] = useState(initialData || null);
  const [errorMsg, setErrorMsg] = useState('');

  // Hover state from graph
  const [hoveredNode, setHoveredNode] = useState(null);
  const [affectedList, setAffectedList] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);

  // If no initial data, run on mount
  useEffect(() => {
    if (!initialData) {
      runAnalysis('sample_repo');
    }
  }, [initialData]);

  const runAnalysis = async (target = repoInput) => {
    setLoading(true);
    setErrorMsg('');
    try {
      const isGithub = target.includes('/') && !target.startsWith('/') && !target.startsWith('.');
      const payload = {
        k: kHops,
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

  return (
    <div style={{ minHeight: '100vh', background: '#030712', color: '#f8fafc', fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
      <Head>
        <title>Codelysis — RepoGraph Impact & Co-Change Intelligence</title>
        <meta name="description" content="Graph-RAG Code Change Impact Analysis, Error Prediction & Co-Change Recommendations" />
      </Head>

      {/* Top Navigation Bar */}
      <header style={{
        borderBottom: '1px solid #1e293b',
        background: 'rgba(3, 7, 18, 0.85)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        padding: '12px 28px'
      }}>
        <div style={{ maxWidth: 1680, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20 }}>
          
          {/* Logo & Academic Foundation */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
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
                <span style={{ fontSize: 19, fontWeight: 700, letterSpacing: '-0.02em', color: '#f8fafc' }}>
                  Codelysis
                </span>
                <span style={{
                  fontSize: 10,
                  background: 'rgba(56, 189, 248, 0.12)',
                  color: '#38bdf8',
                  padding: '3px 8px',
                  borderRadius: 9999,
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  fontWeight: 600
                }}>
                  RepoGraph ICLR 2025 Extension
                </span>
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>
                Change-Conditioned Impact Localization & Error Risk Intelligence
              </div>
            </div>
          </div>

          {/* Key Metrics KPI Strip */}
          {analysisData && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 18, background: '#0b1329', padding: '6px 16px', borderRadius: 10, border: '1px solid #1e293b' }}>
              <div>
                <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Ego Subgraph</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#38bdf8' }}>
                  {analysisData.ego_nodes_count} nodes · {analysisData.ego_edges_count} edges
                </div>
              </div>
              <div style={{ width: 1, height: 24, background: '#1e293b' }} />
              <div>
                <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Direct Callers</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f97316' }}>
                  {analysisData.direct_callers_count} critical
                </div>
              </div>
              <div style={{ width: 1, height: 24, background: '#1e293b' }} />
              <div>
                <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Predicted Errors</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#ef4444' }}>
                  {analysisData.predicted_errors?.length || 0} locations
                </div>
              </div>
            </div>
          )}

        </div>
      </header>

      {/* Main App Body */}
      <main style={{ maxWidth: 1680, margin: '0 auto', padding: '20px 28px' }}>
        
        {/* Repo Search & Control Panel */}
        <div style={{
          background: '#0b1329',
          border: '1px solid #1e293b',
          borderRadius: 12,
          padding: '16px 20px',
          marginBottom: 20
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center' }}>
            
            {/* Input Box */}
            <div style={{ flex: 1, minWidth: 340, display: 'flex', alignItems: 'center', background: '#030712', border: '1px solid #334155', borderRadius: 8, padding: '0 12px' }}>
              <span style={{ fontSize: 14, color: '#64748b', marginRight: 8 }}>📁</span>
              <input
                type="text"
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runAnalysis(repoInput)}
                placeholder="Repository link or path (e.g. 'sample_repo', 'bottlepy/bottle', 'pallets/flask')..."
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

            {/* Traversal Depth (k) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#030712', padding: '6px 12px', borderRadius: 8, border: '1px solid #334155' }}>
              <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 500 }}>Depth:</span>
              {[1, 2, 3].map(h => (
                <button
                  key={h}
                  onClick={() => setKHops(h)}
                  style={{
                    background: kHops === h ? '#0284c7' : 'transparent',
                    color: kHops === h ? '#fff' : '#94a3b8',
                    border: 'none',
                    borderRadius: 6,
                    padding: '3px 8px',
                    cursor: 'pointer',
                    fontSize: 12,
                    fontWeight: 600
                  }}
                >
                  k={h}
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
                padding: '9px 14px',
                borderRadius: 8,
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 500
              }}
            >
              {showDiffInput ? 'Hide Git Diff' : 'Custom Git Diff ▾'}
            </button>

            {/* Analyze Trigger Button */}
            <button
              onClick={() => runAnalysis(repoInput)}
              disabled={loading}
              style={{
                background: loading ? '#334155' : 'linear-gradient(135deg, #0284c7, #4f46e5)',
                color: '#fff',
                border: 'none',
                padding: '9px 24px',
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
                  <span style={{ animation: 'spin 1s linear infinite' }}>⟳</span>
                  Analyzing Graph...
                </>
              ) : (
                'Analyze Impact'
              )}
            </button>

          </div>

          {/* Quick Presets */}
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: '#64748b' }}>
            <span>Quick Presets:</span>
            <button
              onClick={() => { setRepoInput('sample_repo'); runAnalysis('sample_repo'); }}
              style={{ background: '#030712', border: '1px solid #1e293b', color: '#38bdf8', padding: '3px 8px', borderRadius: 4, cursor: 'pointer' }}
            >
              sample_repo (Live Demo)
            </button>
            <button
              onClick={() => { setRepoInput('bottlepy/bottle'); runAnalysis('bottlepy/bottle'); }}
              style={{ background: '#030712', border: '1px solid #1e293b', color: '#38bdf8', padding: '3px 8px', borderRadius: 4, cursor: 'pointer' }}
            >
              bottlepy/bottle (GitHub)
            </button>
            <button
              onClick={() => { setRepoInput('pallets/flask'); runAnalysis('pallets/flask'); }}
              style={{ background: '#030712', border: '1px solid #1e293b', color: '#38bdf8', padding: '3px 8px', borderRadius: 4, cursor: 'pointer' }}
            >
              pallets/flask (GitHub)
            </button>
          </div>

          {/* Custom Diff Box */}
          {showDiffInput && (
            <div style={{ marginTop: 12 }}>
              <textarea
                rows={5}
                value={customDiff}
                onChange={(e) => setCustomDiff(e.target.value)}
                placeholder="Paste Unified Git Diff (e.g. @@ -3,4 +3,4 @@ ...) or leave blank to analyze active codebase diff"
                style={{
                  width: '100%',
                  background: '#030712',
                  border: '1px solid #334155',
                  borderRadius: 8,
                  padding: 10,
                  color: '#cbd5e1',
                  fontFamily: 'monospace',
                  fontSize: 12,
                  outline: 'none'
                }}
              />
            </div>
          )}

          {errorMsg && (
            <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', borderRadius: 8, fontSize: 13 }}>
              ⚠️ {errorMsg}
            </div>
          )}
        </div>

        {/* 2-Column Split Workspace */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.85fr) minmax(0, 1.15fr)', gap: 20, alignItems: 'start' }}>
          
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
                <span style={{ fontWeight: 600, color: '#f8fafc' }}>Interactive Subgraph</span>
                <span style={{ color: '#64748b' }}>({analysisData?.nodes?.length || 0} nodes rendered)</span>
              </div>

              {/* Node Search Box */}
              <div style={{ display: 'flex', alignItems: 'center', background: '#030712', border: '1px solid #334155', borderRadius: 6, padding: '2px 8px' }}>
                <span style={{ fontSize: 11, color: '#64748b', marginRight: 4 }}>🔍</span>
                <input
                  type="text"
                  value={nodeSearch}
                  onChange={(e) => setNodeSearch(e.target.value)}
                  placeholder="Filter symbol in graph..."
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
                onSelectNode={setSelectedNode}
                searchQuery={nodeSearch}
              />
            </div>

            {/* Floating Interactive Hover HUD: Which other nodes can affect */}
            {hoveredNode && (
              <div style={{
                position: 'absolute',
                top: 50,
                left: 14,
                width: 330,
                maxHeight: 480,
                overflowY: 'auto',
                background: 'rgba(15, 23, 42, 0.96)',
                backdropFilter: 'blur(16px)',
                border: '1px solid #38bdf8',
                borderRadius: 12,
                padding: 16,
                boxShadow: '0 12px 36px rgba(0, 0, 0, 0.75)',
                zIndex: 30
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 10, textTransform: 'uppercase', color: '#38bdf8', fontWeight: 700, letterSpacing: '0.05em' }}>
                    Inspected Node
                  </span>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    background: hoveredNode.status === 'seed' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(56, 189, 248, 0.2)',
                    color: hoveredNode.status === 'seed' ? '#ef4444' : '#38bdf8',
                    padding: '2px 8px',
                    borderRadius: 4
                  }}>
                    {hoveredNode.category.toUpperCase()}
                  </span>
                </div>

                <div style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc', wordBreak: 'break-word' }}>
                  {hoveredNode.name}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                  {hoveredNode.file}:{hoveredNode.line}
                </div>

                {hoveredNode.signature && (
                  <div style={{ marginTop: 8, padding: '4px 8px', background: '#030712', borderRadius: 6, fontFamily: 'monospace', fontSize: 11, color: '#38bdf8' }}>
                    {hoveredNode.signature}
                  </div>
                )}

                {hoveredNode.snippet && (
                  <div style={{ marginTop: 6, padding: '4px 8px', background: '#0b1329', border: '1px solid #1e293b', borderRadius: 4, fontFamily: 'monospace', fontSize: 10, color: '#cbd5e1' }}>
                    {hoveredNode.snippet}
                  </div>
                )}

                {/* Downstream Affected Nodes Section */}
                <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #334155' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#f97316' }}>
                      ⚡ Affects if Modified ({affectedList.length})
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                    Downstream callers & services broken:
                  </div>

                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
                    {affectedList.length === 0 ? (
                      <span style={{ fontSize: 11, color: '#64748b' }}>No downstream callers in this neighborhood.</span>
                    ) : (
                      affectedList.map(aff => (
                        <div key={aff.id} style={{ background: '#030712', padding: '6px 8px', borderRadius: 6, border: '1px solid #1e293b' }}>
                          <div style={{ fontSize: 11, fontWeight: 600, color: aff.status === 'test' ? '#06b6d4' : '#f8fafc' }}>
                            {aff.name}
                          </div>
                          <div style={{ fontSize: 10, color: '#64748b' }}>
                            {aff.file}:{aff.line} ({aff.category})
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>
            )}
          </div>

          {/* Right Column: Multi-Tab Intelligence Panel */}
          <div style={{
            background: '#0b1329',
            border: '1px solid #1e293b',
            borderRadius: 12,
            height: 720,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            
            {/* Tab Navigation Header */}
            <div style={{ display: 'flex', borderBottom: '1px solid #1e293b', background: '#030712' }}>
              {[
                { id: 'ranking', label: 'Impact Ranking', icon: '🎯', badge: analysisData?.ranked_impact_nodes?.length },
                { id: 'tests', label: 'Test Impact', icon: '🧪', badge: analysisData?.test_recommendations?.length },
                { id: 'errors', label: 'Potential Errors', icon: '⚠', badge: analysisData?.predicted_errors?.length },
                { id: 'evolution', label: 'Git Evolution', icon: '🧬', badge: analysisData?.git_co_changes?.length },
                { id: 'paths', label: 'Evidence Paths', icon: '⤹', badge: Object.keys(analysisData?.evidence_paths || {}).length },
                { id: 'report', label: 'Checklist', icon: '📄' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    flex: 1,
                    padding: '12px 4px',
                    border: 'none',
                    background: activeTab === tab.id ? '#0b1329' : 'transparent',
                    color: activeTab === tab.id ? '#38bdf8' : '#94a3b8',
                    borderBottom: activeTab === tab.id ? '2px solid #38bdf8' : 'none',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 5
                  }}
                >
                  <span style={{ fontSize: 12 }}>{tab.icon}</span>
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && tab.badge > 0 && (
                    <span style={{ fontSize: 9, background: activeTab === tab.id ? '#0284c7' : '#334155', color: '#fff', padding: '1px 5px', borderRadius: 9999 }}>
                      {tab.badge}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Tab Contents Area */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 18 }}>

              {/* TAB 0: WEIGHTED CAUSAL IMPACT RANKING */}
              {activeTab === 'ranking' && (
                <div>
                  <div style={{ marginBottom: 14 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                      Change-Conditioned Impact Ranking
                    </h3>
                    <p style={{ fontSize: 11, color: '#94a3b8', margin: '4px 0 0 0' }}>
                      Personalized PageRank & Causal Decay ranking across typed dependency edges.
                    </p>
                  </div>

                  {!analysisData?.ranked_impact_nodes || analysisData.ranked_impact_nodes.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b', fontSize: 13 }}>
                      No ranked downstream nodes computed.
                    </div>
                  ) : (
                    analysisData.ranked_impact_nodes.map((node) => {
                      const sevColor = node.severity === 'CRITICAL' ? '#ef4444' :
                                       node.severity === 'HIGH' ? '#f97316' :
                                       node.severity === 'MEDIUM' ? '#eab308' : '#64748b';
                      const sevBg = node.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.15)' :
                                    node.severity === 'HIGH' ? 'rgba(249, 115, 22, 0.15)' :
                                    node.severity === 'MEDIUM' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(100, 116, 139, 0.15)';
                      const scorePct = Math.round(node.impact_score * 100);

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
                              <span style={{ fontSize: 11, fontWeight: 800, color: '#94a3b8' }}>
                                #{node.rank}
                              </span>
                              <span style={{
                                fontSize: 10,
                                fontWeight: 700,
                                padding: '2px 7px',
                                borderRadius: 4,
                                background: sevBg,
                                color: sevColor
                              }}>
                                {node.severity}
                              </span>
                              <span style={{ fontSize: 10, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 6px', borderRadius: 4 }}>
                                {node.hop_distance}-hop
                              </span>
                            </div>
                            <span style={{ fontSize: 11, fontWeight: 700, color: sevColor }}>
                              Score: {node.impact_score}
                            </span>
                          </div>

                          <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc', marginTop: 4 }}>
                            {node.name}
                          </div>
                          <div style={{ fontSize: 10, color: '#64748b', marginTop: 1 }}>
                            {node.file}:{node.line} ({node.category})
                          </div>

                          {/* Impact score progress bar */}
                          <div style={{ width: '100%', height: 4, background: '#1e293b', borderRadius: 2, marginTop: 8, overflow: 'hidden' }}>
                            <div style={{ width: `${Math.max(5, scorePct)}%`, height: '100%', background: sevColor, borderRadius: 2 }} />
                          </div>

                          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8, lineHeight: 1.4 }}>
                            {node.causal_explanation}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* TAB: TEST IMPACT ANALYSIS */}
              {activeTab === 'tests' && (
                <div>
                  <div style={{ marginBottom: 14 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                      Test Impact Analysis (Suggested Tests)
                    </h3>
                    <p style={{ fontSize: 11, color: '#94a3b8', margin: '4px 0 0 0' }}>
                      Identifies relevant test suites based on direct invocations, transitive paths, and historical co-changes.
                    </p>
                  </div>

                  {!analysisData?.test_recommendations || analysisData.test_recommendations.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b', fontSize: 13 }}>
                      No relevant test suites identified.
                    </div>
                  ) : (
                    analysisData.test_recommendations.map((tr, idx) => {
                      const clsColor = tr.classification === 'directly_related' ? '#06b6d4' :
                                       tr.classification === 'indirectly_related' ? '#eab308' :
                                       tr.classification === 'historically_associated' ? '#a855f7' : '#94a3b8';
                      const clsBg = tr.classification === 'directly_related' ? 'rgba(6, 182, 212, 0.15)' :
                                    tr.classification === 'indirectly_related' ? 'rgba(234, 179, 8, 0.15)' :
                                    tr.classification === 'historically_associated' ? 'rgba(168, 85, 247, 0.15)' : 'rgba(148, 163, 184, 0.15)';
                      const scorePct = Math.round(tr.impact_score * 100);

                      return (
                        <div
                          key={idx}
                          style={{
                            background: '#030712',
                            border: `1px solid ${tr.classification === 'directly_related' ? 'rgba(6, 182, 212, 0.4)' : '#1e293b'}`,
                            borderRadius: 8,
                            padding: 12,
                            marginBottom: 10
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{
                              fontSize: 10,
                              fontWeight: 700,
                              padding: '2px 7px',
                              borderRadius: 4,
                              background: clsBg,
                              color: clsColor,
                              textTransform: 'uppercase'
                            }}>
                              {tr.classification.replace('_', ' ')}
                            </span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8' }}>
                              Score: {scorePct}%
                            </span>
                          </div>

                          <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc', marginTop: 4 }}>
                            {tr.test_name}
                          </div>
                          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                            {tr.test_file}
                          </div>

                          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8 }}>
                            <strong>Evidence:</strong> {tr.reason}
                          </div>

                          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{
                              fontSize: 10,
                              padding: '2px 6px',
                              borderRadius: 4,
                              background: tr.requires_execution ? 'rgba(239, 68, 68, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                              color: tr.requires_execution ? '#f87171' : '#94a3b8',
                              fontWeight: 600
                            }}>
                              {tr.requires_execution ? '⚡ Execution Recommended' : '🔍 Review Only'}
                            </span>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* TAB 1: WHERE POSSIBLE ERRORS ARRIVE */}
              {activeTab === 'errors' && (
                <div>
                  <div style={{ marginBottom: 14 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                      Predicted Runtime & Compile-Time Breakages
                    </h3>
                    <p style={{ fontSize: 11, color: '#94a3b8', margin: '4px 0 0 0' }}>
                      Exact locations where downstream calls or unit assertions will fail.
                    </p>
                  </div>

                  {!analysisData?.predicted_errors || analysisData.predicted_errors.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b', fontSize: 13 }}>
                      No breaking errors detected in the current ego neighborhood.
                    </div>
                  ) : (
                    analysisData.predicted_errors.map((err, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: '#030712',
                          border: err.severity === 'CRITICAL' ? '1px solid rgba(239, 68, 68, 0.45)' : '1px solid #1e293b',
                          borderRadius: 8,
                          padding: 12,
                          marginBottom: 12
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 7px',
                            borderRadius: 4,
                            background: err.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(249, 115, 22, 0.2)',
                            color: err.severity === 'CRITICAL' ? '#ef4444' : '#f97316'
                          }}>
                            {err.severity} RISK · {err.error_type}
                          </span>
                          <span style={{ fontSize: 11, color: '#64748b' }}>
                            {err.file}:{err.line}
                          </span>
                        </div>

                        <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc', marginTop: 4 }}>
                          {err.symbol}
                        </div>

                        {err.snippet && (
                          <div style={{ marginTop: 6, padding: '4px 8px', background: '#0b1329', borderRadius: 4, fontFamily: 'monospace', fontSize: 11, color: '#cbd5e1' }}>
                            {err.snippet}
                          </div>
                        )}

                        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8 }}>
                          <strong>Root Cause:</strong> {err.cause}
                        </div>

                        <div style={{ fontSize: 11, color: '#38bdf8', marginTop: 4 }}>
                          <strong>Recommended Fix:</strong> {err.recommended_fix}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* TAB 2: CAUSAL EVIDENCE PATHS */}
              {activeTab === 'paths' && (
                <div>
                  <div style={{ marginBottom: 14 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                      Causal Propagation Chains
                    </h3>
                    <p style={{ fontSize: 11, color: '#94a3b8', margin: '4px 0 0 0' }}>
                      Step-by-step causal paths from seed modifications to impacted callers.
                    </p>
                  </div>

                  {Object.keys(analysisData?.evidence_paths || {}).length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b', fontSize: 13 }}>
                      No multi-hop propagation chains recorded.
                    </div>
                  ) : (
                    Object.entries(analysisData.evidence_paths).map(([targetId, paths], idx) => (
                      <div key={idx} style={{ background: '#030712', border: '1px solid #1e293b', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: '#38bdf8', marginBottom: 8 }}>
                          Target: {targetId.split(':').slice(-1)[0]}
                        </div>
                        {paths.map((p, pIdx) => (
                          <div key={pIdx} style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
                            {p.map((step, sIdx) => (
                              <div key={sIdx} style={{ display: 'flex', alignItems: 'center', gap: 6, color: sIdx === 0 ? '#ef4444' : sIdx === p.length - 1 ? '#f97316' : '#cbd5e1' }}>
                                {sIdx > 0 && <span style={{ color: '#64748b' }}>↳ [{step.edge_type || 'calls'}]</span>}
                                <span>{step.name} ({step.file}:{step.line})</span>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* TAB 3: GIT EVOLUTION & CO-CHANGE INTELLIGENCE */}
              {activeTab === 'evolution' && (
                <div>
                  <div style={{ marginBottom: 14 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                      Git Evolution & Historical Co-Changes
                    </h3>
                    <p style={{ fontSize: 11, color: '#94a3b8', margin: '4px 0 0 0' }}>
                      Files historically committed together in past evolution with Jaccard coupling.
                    </p>
                  </div>

                  {!analysisData?.git_co_changes || analysisData.git_co_changes.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b', fontSize: 13 }}>
                      No historical Git co-change couplings found for seed files in recent commit history.
                    </div>
                  ) : (
                    analysisData.git_co_changes.map((co, idx) => (
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
                          <span style={{ fontSize: 11, fontWeight: 700, color: '#06b6d4' }}>
                            Co-Changed Target
                          </span>
                          <span style={{ fontSize: 10, background: 'rgba(6, 182, 212, 0.15)', color: '#06b6d4', padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>
                            Jaccard: {(co.jaccard_score * 100).toFixed(1)}%
                          </span>
                        </div>

                        <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>
                          {co.target_file}
                        </div>
                        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                          Paired with modified file: <span style={{ color: '#ef4444' }}>{co.source_file}</span>
                        </div>

                        <div style={{ display: 'flex', gap: 12, marginTop: 8, fontSize: 10, color: '#64748b' }}>
                          <span>Shared Commits: <strong style={{ color: '#cbd5e1' }}>{co.co_change_count}</strong></span>
                          <span>Confidence: <strong style={{ color: '#cbd5e1' }}>{(co.confidence * 100).toFixed(1)}%</strong></span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* TAB 4: RECOMMENDATION REPORT */}
              {activeTab === 'report' && (
                <div style={{ background: '#030712', border: '1px solid #1e293b', borderRadius: 8, padding: 14 }}>
                  <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: 11, color: '#cbd5e1', margin: 0 }}>
                    {analysisData?.markdown_report || 'No report generated.'}
                  </pre>
                </div>
              )}

            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

export async function getServerSideProps() {
  try {
    const cwd = process.cwd();
    const rootDir = fs.existsSync(path.join(cwd, 'main.py'))
      ? cwd
      : path.resolve(cwd, '..');
    const pythonBin = path.join(rootDir, 'venv', 'bin', 'python3');
    const mainScript = path.join(rootDir, 'main.py');
    const sampleRepo = path.join(rootDir, 'sample_repo');

    const stdout = execFileSync(pythonBin, [mainScript, '--json', '--hops', '2', '--repo', sampleRepo], {
      cwd: rootDir,
      encoding: 'utf-8',
      maxBuffer: 20 * 1024 * 1024
    });

    const jsonStart = stdout.indexOf('{');
    const jsonEnd = stdout.lastIndexOf('}');
    if (jsonStart !== -1 && jsonEnd !== -1) {
      const initialData = JSON.parse(stdout.substring(jsonStart, jsonEnd + 1));
      return { props: { initialData } };
    }
  } catch (err) {
    console.error('SSR Error:', err);
  }
  return { props: { initialData: null } };
}
