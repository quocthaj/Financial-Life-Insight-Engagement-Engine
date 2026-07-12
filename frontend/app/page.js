"use client";

import React, { useState, useEffect } from "react";

const API_URL = "http://localhost:8000/api";

export default function Home() {
  const [customers, setCustomers] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [selectedCustomerProfile, setSelectedCustomerProfile] = useState(null);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [activeTab, setActiveTab] = useState("balances"); // raw data tab
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [selectedAuditLog, setSelectedAuditLog] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [safetyText, setSafetyText] = useState("");
  const [safetyTestResult, setSafetyTestResult] = useState(null);
  const [checkingSafety, setCheckingSafety] = useState(false);
  const [showLlmDecisions, setShowLlmDecisions] = useState(false);
  const [expandedTraceSteps, setExpandedTraceSteps] = useState({});

  const toggleTraceStep = (stepId) => {
    setExpandedTraceSteps(prev => ({
      ...prev,
      [stepId]: !prev[stepId]
    }));
  };

  // Fetch customers and audit logs on load
  useEffect(() => {
    fetchCustomers();
    fetchAuditLogs();
  }, []);

  const fetchCustomers = async () => {
    try {
      const res = await fetch(`${API_URL}/customers`);
      if (!res.ok) throw new Error("Failed to fetch customers");
      const data = await res.json();
      setCustomers(data);
      if (data.length > 0) {
        handleSelectCustomer(data[0].customer_id);
      }
    } catch (err) {
      setErrorMsg("Error connecting to backend API. Please make sure the FastAPI server is running.");
      console.error(err);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await fetch(`${API_URL}/audit-logs`);
      if (!res.ok) throw new Error("Failed to fetch audit logs");
      const data = await res.json();
      setAuditLogs(data);
    } catch (err) {
      console.error("Error fetching audit logs", err);
    }
  };

  const handleSelectCustomer = async (id) => {
    setSelectedCustomerId(id);
    setPipelineResult(null);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_URL}/customers/${id}`);
      if (!res.ok) throw new Error("Failed to fetch customer profile");
      const data = await res.json();
      setSelectedCustomerProfile(data);
    } catch (err) {
      setErrorMsg("Failed to load customer profile details.");
      console.error(err);
    }
  };

  const handleRunPipeline = async () => {
    if (!selectedCustomerId) return;
    setRunningPipeline(true);
    setPipelineResult(null);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_URL}/pipeline/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id: selectedCustomerId })
      });
      if (!res.ok) throw new Error("Pipeline run failed");
      const data = await res.json();
      setPipelineResult(data);
      fetchAuditLogs(); // Refresh the audit table
    } catch (err) {
      setErrorMsg("An error occurred during pipeline execution.");
      console.error(err);
    } finally {
      setRunningPipeline(false);
    }
  };

  const handleClearAuditLogs = async () => {
    if (!confirm("Are you sure you want to clear all persisted audit logs?")) return;
    try {
      const res = await fetch(`${API_URL}/audit-logs/clear`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to clear logs");
      setAuditLogs([]);
      setSelectedAuditLog(null);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCheckSafety = async () => {
    if (!safetyText.trim()) return;
    setCheckingSafety(true);
    setSafetyTestResult(null);
    try {
      const res = await fetch(`${API_URL}/safety/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: safetyText })
      });
      if (!res.ok) throw new Error("Safety check failed");
      const data = await res.json();
      setSafetyTestResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setCheckingSafety(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "published":
        return <span className="px-3 py-1 text-xs font-semibold rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">Published</span>;
      case "rejected_by_policy":
        return <span className="px-3 py-1 text-xs font-semibold rounded-full bg-amber-950 text-amber-400 border border-amber-800">Rejected by Policy</span>;
      case "blocked_by_safety":
        return <span className="px-3 py-1 text-xs font-semibold rounded-full bg-rose-950 text-rose-400 border border-rose-800">Blocked by Safety</span>;
      case "no_facts":
        return <span className="px-3 py-1 text-xs font-semibold rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800">No Facts (Missing Data)</span>;
      default:
        return <span className="px-3 py-1 text-xs font-semibold rounded-full bg-zinc-800 text-zinc-400">Unknown</span>;
    }
  };

  const getActualStatus = (result) => {
    if (!result) return null;
    if (result.data_availability && !result.data_availability.can_generate_financial_observations) {
      return "no_facts";
    }
    if (result.facts_count === 0) {
      return "no_facts";
    }
    const hasBlocked = result.audit_entries && result.audit_entries.some(e => e.final_status === "blocked_by_safety");
    if (hasBlocked) return "blocked_by_safety";

    const hasPublished = result.audit_entries && result.audit_entries.some(e => e.final_status === "published");
    if (hasPublished) return "published";

    const hasRejected = result.audit_entries && result.audit_entries.some(e => e.final_status === "rejected_by_policy");
    if (hasRejected) return "rejected_by_policy";

    return "unknown";
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 sm:p-10 selection:bg-indigo-500 selection:text-white">
      {/* Container */}
      <div className="max-w-7xl mx-auto space-y-10">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
          <div>
            <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
              FINANCIAL MIRROR
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Modular Monolithic Pipeline Orchestrator — Factual Observations & Safety-Guarded Engagement Nudges
            </p>
            {/* Non-advisory Boundary Disclaimer */}
            <div className="mt-2 text-xs text-slate-500 italic bg-slate-900/30 px-3 py-1.5 rounded border border-slate-900/50 max-w-2xl">
              <strong>Disclaimer:</strong> Financial Mirror provides non-advisory observations and educational nudges only. It does not recommend financial actions or decide what customers should do.
            </div>
          </div>
          <div className="flex gap-4 items-center">
            <div className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-center">
              <span className="block text-2xl font-bold text-indigo-400">{customers.length}</span>
              <span className="text-[10px] text-slate-400 uppercase tracking-widest">Personas</span>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-center">
              <span className="block text-2xl font-bold text-purple-400">{auditLogs.length}</span>
              <span className="text-[10px] text-slate-400 uppercase tracking-widest">Audit Traces</span>
            </div>
          </div>
        </header>

        {errorMsg && (
          <div className="bg-rose-950/50 border border-rose-800 text-rose-300 px-4 py-3 rounded-lg flex items-center gap-3">
            <span className="text-xl font-bold">⚠️</span>
            <span className="text-sm font-medium">{errorMsg}</span>
          </div>
        )}

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* LEFT COLUMN: Customer Selection & Raw Data (5 cols) */}
          <div className="lg:col-span-5 space-y-8">
            
            {/* Customer List Card */}
            <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-xl">
              <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                <span className="text-indigo-400">👤</span> Select Customer Persona
              </h2>
              
              <div className="space-y-3">
                {customers.map((c) => {
                  const isSelected = selectedCustomerId === c.customer_id;
                  return (
                    <button
                      key={c.customer_id}
                      onClick={() => handleSelectCustomer(c.customer_id)}
                      className={`w-full text-left p-4 rounded-lg border transition-all duration-200 ${
                        isSelected
                          ? "bg-slate-800/80 border-indigo-500 shadow-md shadow-indigo-950/50 translate-x-1"
                          : "bg-slate-900 border-slate-800 hover:border-slate-700 hover:bg-slate-800/30"
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-semibold text-slate-100">{c.display_name}</h3>
                          <p className="text-xs text-slate-400 mt-1">
                            {c.life_stage.toUpperCase()} • {c.age_band} • {c.income_band.replace("_", " ")}
                          </p>
                        </div>
                        {c.opted_out_of_education_nudges ? (
                          <span className="text-[10px] bg-slate-950 text-slate-500 border border-slate-800 px-2 py-0.5 rounded font-mono">OPT-OUT</span>
                        ) : (
                          <span className="text-[10px] bg-indigo-950/50 text-indigo-400 border border-indigo-900/50 px-2 py-0.5 rounded font-mono">ACTIVE</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Raw Profile Context View */}
            {selectedCustomerProfile && (
              <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <span className="text-purple-400">📊</span> Raw Data Context
                  </h2>
                  <span className="text-xs text-slate-400 font-mono">{selectedCustomerProfile.profile.customer_id}</span>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-slate-800">
                  {["balances", "borrowings", "app_usage"].map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`flex-1 py-2 text-center text-xs font-semibold border-b-2 capitalize transition-all ${
                        activeTab === tab
                          ? "border-indigo-500 text-indigo-400"
                          : "border-transparent text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {tab.replace("_", " ")}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="pt-2 max-h-[280px] overflow-y-auto space-y-3 text-sm">
                  
                  {activeTab === "balances" && (
                    <div className="space-y-3">
                      {selectedCustomerProfile.savings.map((s, idx) => (
                        <div key={idx} className="bg-slate-950/60 p-3 rounded-lg border border-slate-800 flex justify-between items-center">
                          <div>
                            <span className="text-xs text-slate-400 block capitalize">{s.account_type.replace("_", " ")}</span>
                            <span className="font-mono text-slate-300 text-xs">As of: {s.as_of_date}</span>
                          </div>
                          <div className="text-right">
                            <span className="font-bold text-indigo-300">{s.balance.toLocaleString()} PHP</span>
                            {s.savings_goal && <span className="block text-[10px] text-emerald-400">Goal: {s.savings_goal}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === "borrowings" && (
                    <div className="space-y-3">
                      {selectedCustomerProfile.borrowings.length === 0 ? (
                        <p className="text-slate-500 text-center py-4">No borrowing records found.</p>
                      ) : (
                        selectedCustomerProfile.borrowings.map((b, idx) => (
                          <div key={idx} className="bg-slate-950/60 p-3 rounded-lg border border-slate-800 space-y-2">
                            <div className="flex justify-between items-center border-b border-slate-900 pb-1.5">
                              <span className="font-semibold text-slate-200 capitalize">{b.loan_type}</span>
                              <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${b.status === "current" ? "bg-emerald-950/50 text-emerald-400" : "bg-rose-950/50 text-rose-400"}`}>{b.status}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              <div>
                                <span className="text-slate-400 block">Principal</span>
                                <span className="text-slate-200">{b.principal.toLocaleString()} PHP</span>
                              </div>
                              <div>
                                <span className="text-slate-400 block">Outstanding</span>
                                <span className="text-slate-200">{b.outstanding_balance.toLocaleString()} PHP</span>
                              </div>
                              <div>
                                <span className="text-slate-400 block">Monthly Due</span>
                                <span className="text-slate-200">{b.monthly_payment.toLocaleString()} PHP</span>
                              </div>
                              <div>
                                <span className="text-slate-400 block">Next Due Date</span>
                                <span className="text-indigo-400 font-mono">{b.next_due_date}</span>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {activeTab === "app_usage" && (
                    <div className="space-y-2">
                      {selectedCustomerProfile.app_usage.map((e, idx) => (
                        <div key={idx} className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 text-xs flex justify-between items-start gap-4">
                          <div className="space-y-1">
                            <div className="flex items-center gap-1.5">
                              <span className="bg-slate-900 px-1.5 py-0.5 rounded text-[10px] text-indigo-400 border border-slate-800 uppercase font-bold">{e.event_type}</span>
                              <span className="font-semibold text-slate-200">{e.feature_name}</span>
                            </div>
                            {e.metadata && Object.keys(e.metadata).length > 0 && (
                              <div className="text-[10px] text-slate-400 bg-slate-900/30 p-1.5 rounded font-mono">
                                {Object.entries(e.metadata).map(([k, v]) => (
                                  <span key={k} className="block">{k}: {String(v)}</span>
                                ))}
                              </div>
                            )}
                          </div>
                          <span className="text-slate-500 font-mono text-[10px] whitespace-nowrap">{e.timestamp.split(" ")[0]}</span>
                        </div>
                      ))}
                    </div>
                  )}

                </div>
              </div>
            )}

            {/* Real-time Safety Playground Card */}
            <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
              <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                <span className="text-rose-455">🛡️</span> Real-time Safety Playground
              </h2>
              <p className="text-xs text-slate-400">
                Type any custom observation, nudge, or advice copy to verify compliance with non-advisory policies.
              </p>
              <textarea
                value={safetyText}
                onChange={(e) => setSafetyText(e.target.value)}
                placeholder="e.g. You should move 5% of your savings to maximize returns..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 h-20 resize-none"
              />
              <div className="flex justify-between items-center">
                <button
                  onClick={handleCheckSafety}
                  disabled={checkingSafety || !safetyText.trim()}
                  className="px-4 py-2 bg-rose-900/85 hover:bg-rose-800 text-white text-xs font-semibold rounded-lg transition-all"
                >
                  {checkingSafety ? "Checking..." : "Verify Safety"}
                </button>
                {safetyTestResult && (
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${safetyTestResult.passed ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800"}`}>
                    {safetyTestResult.passed ? "Passed" : "Blocked"}
                  </span>
                )}
              </div>
              {safetyTestResult && !safetyTestResult.passed && (
                <div className="bg-rose-950/20 border border-rose-900/40 p-3 rounded-lg text-xs space-y-1">
                  <span className="text-rose-400 font-semibold">Policy Violations:</span>
                  <ul className="list-disc list-inside text-rose-300 space-y-0.5 text-[11px]">
                    {safetyTestResult.violations.map((v, i) => (
                      <li key={i}>{v}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

          </div>

          {/* RIGHT COLUMN: Pipeline Output and Visual Flow (7 cols) */}
          <div className="lg:col-span-7 space-y-8">
            
            {/* Run Panel */}
            <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-100">Pipeline Execution</h2>
                <p className="text-xs text-slate-400 mt-1">Execute the modular rule-based engines for the selected customer.</p>
              </div>
              <button
                onClick={handleRunPipeline}
                disabled={runningPipeline || !selectedCustomerId}
                className={`px-6 py-3 rounded-lg font-semibold text-sm transition-all duration-200 flex items-center gap-2 ${
                  runningPipeline
                    ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                    : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-900/40 hover:-translate-y-0.5 active:translate-y-0 cursor-pointer"
                }`}
              >
                {runningPipeline ? (
                  <>
                    <span className="animate-spin text-lg">⏳</span> Executing Pipeline...
                  </>
                ) : (
                  <>
                    <span>⚡</span> Run Pipeline
                  </>
                )}
              </button>
            </div>

            {/* Compliance & Stress Test Verification Card */}
            {selectedCustomerId && (
              (() => {
                const customerMeta = customers.find(c => c.customer_id === selectedCustomerId);
                if (!customerMeta) return null;
                const actualStatus = getActualStatus(pipelineResult);
                
                return (
                  <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
                    <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                      <span className="text-emerald-400">🛡️</span> Compliance & Stress Test Verification
                    </h2>
                    <div className="bg-slate-950/60 p-4 rounded-lg border border-slate-850 space-y-3">
                      <div>
                        <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold">Testing Goal / Persona Purpose</span>
                        <p className="text-slate-350 text-xs mt-0.5">{customerMeta.purpose || "Happy path testing"}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-900">
                        <div>
                          <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold block mb-1">Expected Outcome</span>
                          {getStatusBadge(customerMeta.expected_status || "published")}
                        </div>
                        <div>
                          <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold block mb-1">Actual Outcome</span>
                          {pipelineResult ? getStatusBadge(actualStatus) : <span className="text-slate-500 italic text-xs">Run pipeline to verify</span>}
                        </div>
                      </div>
                      {pipelineResult && (
                        <div className="pt-2.5 border-t border-slate-900 flex items-center justify-between">
                          <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold">Verification Node Status</span>
                          {actualStatus === customerMeta.expected_status ? (
                            <span className="px-3 py-1 text-xs font-bold rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800 flex items-center gap-1">
                              ✅ VERIFIED MATCH
                            </span>
                          ) : (
                            <span className="px-3 py-1 text-xs font-bold rounded-full bg-rose-950/80 text-rose-400 border border-rose-800 flex items-center gap-1">
                              ❌ MISMATCH
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()
            )}

            {/* Agentic Diagnostics & Plan Trace Card */}
            {pipelineResult && (
              <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-xl space-y-6">
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <span className="text-indigo-400">🤖</span> Agentic Diagnostics & Plan Trace
                  </h2>
                  <span className="text-xs text-slate-400 font-mono capitalize">Mode: {pipelineResult.planner_mode || "dynamic"}</span>
                </div>

                {/* Agent Goal */}
                <div className="space-y-1.5">
                  <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold">Agent Objective / Goal</span>
                  <p className="text-xs text-slate-200 bg-slate-950/60 p-3 rounded-lg border border-slate-850 italic">
                    "{pipelineResult.agent_goal || "No goal specified"}"
                  </p>
                </div>

                {/* Model Details */}
                <div className="grid grid-cols-2 gap-4 text-xs bg-slate-950/40 p-3 rounded-lg border border-slate-900">
                  <div>
                    <span className="text-slate-400 block font-semibold">Model Provider</span>
                    <span className="text-indigo-400 font-mono text-[11px] block mt-0.5">
                      {pipelineResult.model_used?.provider || "mock_provider"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-semibold">Model Name</span>
                    <span className="text-purple-400 font-mono text-[11px] block mt-0.5">
                      {pipelineResult.model_used?.model_name || "mock_llm"}
                    </span>
                  </div>
                  <div className="col-span-2 pt-2 border-t border-slate-900">
                    <span className="text-slate-400 block font-semibold">Prompt Template Version</span>
                    <span className="text-cyan-400 font-mono text-[11px] block mt-0.5">
                      {pipelineResult.model_used?.prompt_version || "n/a"}
                    </span>
                  </div>
                </div>

                {/* Base Plan */}
                {pipelineResult.base_plan && pipelineResult.base_plan.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold">Formulated Base Plan</span>
                    <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
                      {pipelineResult.base_plan.map((step, idx) => (
                        <div key={idx} className="bg-slate-950/50 p-2.5 rounded border border-slate-850 text-xs flex gap-3 items-start">
                          <span className="bg-indigo-950 text-indigo-400 border border-indigo-900/50 px-1.5 py-0.5 rounded text-[10px] font-mono shrink-0">
                            {step.step_id || `Step ${idx + 1}`}
                          </span>
                          <div className="space-y-1">
                            <span className="font-semibold text-slate-350">{step.tool || "Generic Step"}</span>
                            <p className="text-[11px] text-slate-400">{step.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Execution Trace Timeline */}
                {pipelineResult.execution_trace && pipelineResult.execution_trace.length > 0 && (
                  <div className="space-y-3">
                    <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold">Actual Execution Trace (Timeline)</span>
                    <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                      {pipelineResult.execution_trace.map((step, idx) => {
                        const isExpanded = expandedTraceSteps[step.step_id];
                        const hasMetadata = step.metadata && Object.keys(step.metadata).length > 0;
                        const isSuccess = step.status === "completed" || step.status === "success" || step.status === "done";
                        
                        return (
                          <div key={idx} className="bg-slate-950/40 p-3 rounded-lg border border-slate-850 text-xs space-y-2">
                            <div className="flex justify-between items-center gap-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="bg-slate-900 text-slate-300 border border-slate-800 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase">
                                  {step.step_id}
                                </span>
                                <span className="font-semibold text-slate-200">
                                  {step.tool}
                                </span>
                              </div>
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                isSuccess ? "bg-emerald-950/60 text-emerald-400" : "bg-rose-950/60 text-rose-400"
                              }`}>
                                {step.status}
                              </span>
                            </div>

                            <p className="text-slate-300 text-[11px] leading-relaxed">
                              {step.summary}
                            </p>

                            {step.decision && (
                              <div className="bg-slate-950/80 p-2 rounded border border-slate-900 flex flex-col gap-0.5">
                                <span className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Decision / Next Action</span>
                                <span className="text-indigo-300 font-mono text-[10px]">{step.decision}</span>
                              </div>
                            )}

                            {hasMetadata && (
                              <div className="pt-1.5 border-t border-slate-900/60 flex flex-col gap-1.5">
                                <button
                                  onClick={() => toggleTraceStep(step.step_id)}
                                  className="text-[10px] text-slate-400 hover:text-indigo-400 text-left font-semibold flex items-center gap-1 transition-colors"
                                >
                                  {isExpanded ? "▼ Hide Step Context Data" : "▶ Show Step Context Data"}
                                </button>
                                {isExpanded && (
                                  <pre className="text-[9px] text-slate-400 bg-slate-950 p-2 rounded border border-slate-900 overflow-x-auto font-mono max-h-[150px]">
                                    {JSON.stringify(step.metadata, null, 2)}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* LLM Decisions Logs (Expandable) */}
                {pipelineResult.llm_decisions && Object.keys(pipelineResult.llm_decisions).length > 0 && (
                  <div className="pt-3 border-t border-slate-800/80 space-y-3">
                    <button
                      onClick={() => setShowLlmDecisions(!showLlmDecisions)}
                      className="w-full flex justify-between items-center text-xs font-bold text-indigo-400 hover:text-indigo-300 transition-colors"
                    >
                      <span>💬 VIEW LLM DECISIONS & LOGS</span>
                      <span>{showLlmDecisions ? "▲ Hide" : "▼ Show"}</span>
                    </button>
                    {showLlmDecisions && (
                      <div className="space-y-3 bg-slate-950/80 p-3 rounded-lg border border-slate-850">
                        {Object.entries(pipelineResult.llm_decisions).map(([key, val], idx) => (
                          <div key={idx} className="space-y-1.5 border-b border-slate-900 last:border-b-0 pb-3 last:pb-0">
                            <span className="text-[10px] text-purple-400 font-mono block font-bold uppercase">{key}</span>
                            <div className="space-y-2 bg-slate-900/40 p-2.5 rounded border border-slate-955 text-[10px]">
                              {val.prompt && (
                                <div>
                                  <span className="text-slate-500 font-semibold uppercase block text-[9px]">Prompt Context</span>
                                  <pre className="mt-1 whitespace-pre-wrap font-mono text-slate-400 bg-slate-950 p-2 rounded border border-slate-900 max-h-[120px] overflow-y-auto">
                                    {val.prompt}
                                  </pre>
                                </div>
                              )}
                              {val.completion && (
                                <div className="mt-2">
                                  <span className="text-emerald-400/80 font-semibold uppercase block text-[9px]">LLM Raw Response</span>
                                  <pre className="mt-1 whitespace-pre-wrap font-mono text-indigo-300 bg-slate-950 p-2 rounded border border-slate-900 max-h-[120px] overflow-y-auto">
                                    {val.completion}
                                  </pre>
                                </div>
                              )}
                              {val.error && (
                                <div className="mt-2 text-rose-400 font-semibold">
                                  Error: {val.error}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Visual Flow results */}
            {pipelineResult ? (
              <div className="space-y-6">
                <div className="flex justify-between items-center">
                  <h2 className="text-xl font-bold text-slate-200 flex items-center gap-2">
                    <span className="text-indigo-400">🔄</span> Execution Outcome
                  </h2>
                  <span className="text-xs text-slate-400 font-mono">Customer: {pipelineResult.customer_id}</span>
                </div>

                {/* Data Checker Report */}
                {pipelineResult.data_availability && (
                  <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3 shadow-md">
                    <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Data Checker Guard Status</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${pipelineResult.data_availability.can_generate_financial_observations ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800"}`}>
                        {pipelineResult.data_availability.can_generate_financial_observations ? "DATA VALIDATED" : "INSUFFICIENT DATA"}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-xs">
                      <div>
                        <span className="text-slate-400 block font-semibold">Available Data Groups</span>
                        <span className="text-slate-300 font-mono text-[11px] block mt-0.5">
                          {pipelineResult.data_availability.available_data_groups.join(", ") || "None"}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block font-semibold">Missing Data Groups</span>
                        <span className="text-rose-400 font-mono text-[11px] block mt-0.5">
                          {pipelineResult.data_availability.missing_data_groups.join(", ") || "None"}
                        </span>
                      </div>
                    </div>
                    {pipelineResult.data_availability.notes && pipelineResult.data_availability.notes.length > 0 && (
                      <div className="bg-slate-950/60 p-2.5 rounded border border-slate-900 text-[10px] text-slate-400 space-y-0.5">
                        {pipelineResult.data_availability.notes.map((n, i) => (
                          <div key={i}>• {n}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {pipelineResult.facts.length === 0 ? (
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center space-y-2">
                    <span className="text-4xl block">🔍</span>
                    <h3 className="font-semibold text-slate-300">No Facts Detected</h3>
                    <p className="text-xs text-slate-500">The customer data doesn't match any behavioral fact pattern criteria.</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {pipelineResult.facts.map((fact, index) => {
                      const dec = pipelineResult.policies.find(p => p.candidate_id === fact.fact_id);
                      const isAccepted = dec && dec.decision === "accepted";
                      const output = pipelineResult.outputs.find(o => o.candidate_id === fact.fact_id);
                      const challengeItem = pipelineResult.challenges.find(c => c.based_on_nudge === fact.fact_id);
                      const auditEntry = pipelineResult.audit_entries.find(e => e.candidate_id === fact.fact_id);
                      
                      return (
                        <div key={fact.fact_id} className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
                          
                          {/* Fact Header */}
                          <div className="bg-slate-900 p-4 border-b border-slate-800 flex justify-between items-center gap-4">
                            <div>
                              <span className="text-[10px] bg-indigo-950/80 text-indigo-400 border border-indigo-900/50 px-2 py-0.5 rounded font-mono font-bold tracking-wider uppercase">{fact.fact_type}</span>
                              <h3 className="text-sm font-semibold text-slate-200 mt-1.5">{fact.description}</h3>
                            </div>
                            <span className="text-xs text-slate-500 font-mono shrink-0">{fact.fact_id}</span>
                          </div>

                          {/* Fact Details (collapsible style/expanded) */}
                          <div className="p-4 space-y-4 text-xs">
                            
                            {/* Evidence / Metrics */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-950/40 p-3 rounded-lg border border-slate-900">
                              <div>
                                <span className="text-slate-400 block font-semibold mb-1">Metrics (Value)</span>
                                <pre className="text-[10px] text-indigo-300 bg-slate-950 p-2 rounded overflow-x-auto font-mono">
                                  {JSON.stringify(fact.value, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <span className="text-slate-400 block font-semibold mb-1">Scope & Evidence</span>
                                <div className="space-y-1">
                                  {fact.evidence_ids && fact.evidence_ids.length > 0 ? (
                                    <div className="text-[10px] text-slate-300">
                                      <span className="block font-semibold text-emerald-400">Evidence IDs:</span>
                                      <span className="font-mono">{fact.evidence_ids.join(", ")}</span>
                                    </div>
                                  ) : (
                                    <div className="text-[10px] text-slate-400 italic">
                                      {fact.evidence_note}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Node Path Steps */}
                            <div className="space-y-3 pt-2">
                              
                              {/* Step 1: Policy Engine */}
                              <div className="flex gap-3">
                                <div className="flex flex-col items-center">
                                  <div className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${isAccepted ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800"}`}>
                                    P
                                  </div>
                                  <div className="w-0.5 h-full bg-slate-800"></div>
                                </div>
                                <div className="pb-3 flex-1">
                                  <span className="font-semibold text-slate-300">Policy Check:</span>
                                  {dec ? (
                                    <div className="mt-1 space-y-1">
                                      <div className="flex items-center gap-2">
                                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${isAccepted ? "bg-emerald-950 text-emerald-400" : "bg-rose-950 text-rose-400"}`}>
                                          {dec.decision.toUpperCase()}
                                        </span>
                                        <span className="text-slate-400 font-mono text-[10px]">{dec.rule_ids_triggered.join(", ")}</span>
                                      </div>
                                      <p className="text-slate-400 text-[11px]">{dec.reasons.join(". ")}</p>
                                    </div>
                                  ) : (
                                    <span className="text-slate-500 italic block">Skipped</span>
                                  )}
                                </div>
                              </div>

                              {/* Step 2: Nudge Generation & Safety */}
                              <div className="flex gap-3">
                                <div className="flex flex-col items-center">
                                  <div className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${output && output.nudge_safety?.passed ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : output ? "bg-rose-950 text-rose-400 border border-rose-800" : "bg-slate-900 text-slate-500 border border-slate-800"}`}>
                                    N
                                  </div>
                                  <div className="w-0.5 h-full bg-slate-800"></div>
                                </div>
                                <div className="pb-3 flex-1">
                                  <span className="font-semibold text-slate-300">Educational Copy (Nudge):</span>
                                  {output ? (
                                    <div className="mt-1 space-y-2 bg-slate-950/60 p-3 rounded-lg border border-slate-900">
                                      <div>
                                        <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold">Factual Observation</span>
                                        <p className="text-slate-200 mt-0.5 italic">"{output.observation.text}"</p>
                                      </div>
                                      <div>
                                        <span className="text-[10px] uppercase text-slate-400 tracking-wider font-semibold">Actionable Nudge</span>
                                        <p className="text-slate-200 mt-0.5 italic">"{output.nudge.text}"</p>
                                      </div>
                                      <div className="flex justify-between items-center pt-1.5 border-t border-slate-900">
                                        <span className="text-[10px] text-slate-400">Safety Check:</span>
                                        {output.nudge_safety?.passed ? (
                                          <span className="text-[10px] text-emerald-400 font-semibold">✅ Passed Safety Engine</span>
                                        ) : (
                                          <div className="text-right">
                                            <span className="text-[10px] text-rose-400 font-semibold">❌ Blocked</span>
                                            {output.nudge_safety?.violations.map((v, i) => (
                                              <span key={i} className="block text-[9px] text-rose-500 font-mono mt-0.5">{v}</span>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ) : (
                                    <span className="text-slate-500 italic block mt-1">Not generated (Policy rejected or out of scope)</span>
                                  )}
                                </div>
                              </div>

                              {/* Step 3: Challenge & Rewards */}
                              <div className="flex gap-3">
                                <div className="flex flex-col items-center">
                                  <div className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${challengeItem && challengeItem.passed_safety_check ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : challengeItem ? "bg-rose-950 text-rose-400 border border-rose-800" : "bg-slate-900 text-slate-500 border border-slate-800"}`}>
                                    C
                                  </div>
                                  <div className="w-0.5 h-full bg-slate-800"></div>
                                </div>
                                <div className="pb-3 flex-1">
                                  <span className="font-semibold text-slate-300">Engagement Challenge (P6):</span>
                                  {challengeItem ? (
                                    <div className="mt-1 bg-slate-950/60 p-3 rounded-lg border border-slate-900 space-y-2">
                                      <div className="flex justify-between items-start">
                                        <h4 className="font-bold text-indigo-400">{challengeItem.challenge.title}</h4>
                                        <div className="flex gap-1.5">
                                          <span className="bg-purple-950 text-purple-400 px-1.5 py-0.5 rounded text-[9px] font-bold font-mono uppercase">{challengeItem.challenge.difficulty_tier}</span>
                                          <span className="bg-emerald-950 text-emerald-400 px-1.5 py-0.5 rounded text-[9px] font-bold font-mono font-semibold">+{challengeItem.challenge.reward_points} pts</span>
                                        </div>
                                      </div>
                                      <p className="text-slate-300 text-[11px]">{challengeItem.challenge.description}</p>
                                      <div className="text-[10px] bg-slate-900 p-2 rounded border border-slate-800/50">
                                        <span className="text-slate-400 font-semibold block uppercase tracking-wider text-[9px] mb-0.5">Success Criteria:</span>
                                        <span className="text-slate-200">{challengeItem.challenge.criteria}</span>
                                      </div>
                                      <div className="flex justify-between items-center pt-1.5 border-t border-slate-900">
                                        <span className="text-[10px] text-slate-400">Safety Check:</span>
                                        {challengeItem.passed_safety_check ? (
                                          <span className="text-[10px] text-emerald-400 font-semibold">✅ Passed Safety Engine</span>
                                        ) : (
                                          <div className="text-right">
                                            <span className="text-[10px] text-rose-400 font-semibold">❌ Blocked</span>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ) : (
                                    <span className="text-slate-500 italic block mt-1">Not generated</span>
                                  )}
                                </div>
                              </div>

                              {/* Step 4: Audit Logger */}
                              <div className="flex gap-3">
                                <div className="flex flex-col items-center">
                                  <div className="w-6 h-6 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-800 flex items-center justify-center font-bold text-xs">
                                    A
                                  </div>
                                </div>
                                <div className="flex-1">
                                  <div className="flex items-center justify-between">
                                    <span className="font-semibold text-slate-300">Audit Status:</span>
                                    {auditEntry && getStatusBadge(auditEntry.final_status)}
                                  </div>
                                  {auditEntry && (
                                    <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                                      <span>ID: {auditEntry.trace_id}</span>
                                      <span>{new Date(auditEntry.timestamp).toLocaleString()}</span>
                                    </div>
                                  )}
                                </div>
                              </div>

                            </div>
                          </div>

                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-12 text-center space-y-3">
                <span className="text-5xl block animate-pulse">🚀</span>
                <h3 className="font-bold text-slate-300 text-lg">Orchestration Ready</h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  Click "Run Pipeline" above to run the customer profile through the modular monolithic engines and view the safety audit trail.
                </p>
              </div>
            )}

          </div>

        </div>

        {/* BOTTOM SECTION: Historical Audit Trail (Persisted DB) */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center border-b border-slate-800 pb-4 gap-4">
            <div>
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                <span className="text-cyan-400">📜</span> Historical Audit Trail Logs
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Persisted in-process trace logs for all transactions and evaluations (updates in real-time).
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={fetchAuditLogs}
                className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-750 text-xs font-semibold rounded-lg transition-all"
              >
                🔄 Refresh Logs
              </button>
              <button
                onClick={handleClearAuditLogs}
                className="px-3.5 py-1.5 bg-rose-950/30 hover:bg-rose-950/75 text-rose-300 border border-rose-900/40 text-xs font-semibold rounded-lg transition-all"
              >
                🗑️ Clear DB
              </button>
            </div>
          </div>

          {auditLogs.length === 0 ? (
            <div className="text-center py-10 text-slate-500 italic text-sm">
              No audit logs recorded yet. Run the pipeline to populate traces.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto rounded-lg border border-slate-850">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-900 text-slate-300 border-b border-slate-800">
                      <th className="p-3 font-semibold">Trace ID</th>
                      <th className="p-3 font-semibold">Timestamp</th>
                      <th className="p-3 font-semibold">Customer ID</th>
                      <th className="p-3 font-semibold">Candidate Type</th>
                      <th className="p-3 font-semibold text-center">Policy Status</th>
                      <th className="p-3 font-semibold text-center">Safety Gate</th>
                      <th className="p-3 font-semibold text-center">Outcome</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-850 bg-slate-900/20">
                    {auditLogs.map((log) => {
                      const isSelected = selectedAuditLog && selectedAuditLog.trace_id === log.trace_id;
                      return (
                        <React.Fragment key={log.trace_id}>
                          <tr
                            onClick={() => setSelectedAuditLog(isSelected ? null : log)}
                            className={`hover:bg-slate-800/40 cursor-pointer transition-colors ${
                              isSelected ? "bg-slate-800/70" : ""
                            }`}
                          >
                            <td className="p-3 font-mono text-[11px] text-indigo-400">{log.trace_id}</td>
                            <td className="p-3 text-slate-400 font-mono text-[10px]">
                              {new Date(log.timestamp).toLocaleString()}
                            </td>
                            <td className="p-3 font-mono text-slate-300">{log.customer_id}</td>
                            <td className="p-3">
                              <span className="bg-slate-950 px-2 py-0.5 rounded text-[10px] text-slate-400 border border-slate-850 capitalize font-mono">
                                {log.candidate_type}
                              </span>
                            </td>
                            <td className="p-3 text-center">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                log.policy_result === "accepted" ? "bg-emerald-950 text-emerald-400" : "bg-rose-950 text-rose-400"
                              }`}>
                                {log.policy_result}
                              </span>
                            </td>
                            <td className="p-3 text-center">
                              {log.policy_result === "rejected" ? (
                                <span className="text-slate-500">—</span>
                              ) : log.nudge_safety_passed && log.challenge_safety_passed ? (
                                <span className="text-emerald-400 font-bold">PASS</span>
                              ) : (
                                <span className="text-rose-400 font-bold">BLOCKED</span>
                              )}
                            </td>
                            <td className="p-3 text-center">{getStatusBadge(log.final_status)}</td>
                          </tr>

                          {/* Expanded JSON view */}
                          {isSelected && (
                            <tr>
                              <td colSpan="7" className="p-4 bg-slate-950 border-t border-b border-slate-800">
                                <div className="space-y-3">
                                  <div className="flex justify-between items-center">
                                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Full JSON Audit Record Trace</span>
                                    <span className="text-[10px] text-slate-500 font-mono">Trace: {log.trace_id}</span>
                                  </div>
                                  <pre className="text-[10px] bg-slate-900 p-4 rounded-lg border border-slate-850 overflow-x-auto text-indigo-300 font-mono max-h-[300px]">
                                    {JSON.stringify(log, null, 2)}
                                  </pre>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

      </div>
    </div>
  );
}
