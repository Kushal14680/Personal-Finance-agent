"use client";

import { useState, useEffect, useRef } from "react";
import { 
  TrendingUp, 
  TrendingDown, 
  Upload, 
  Settings, 
  ShieldAlert, 
  CheckCircle, 
  Calendar, 
  ArrowUpRight, 
  Percent, 
  Zap, 
  BookOpen, 
  Plus, 
  X, 
  RefreshCw, 
  AlertCircle, 
  HelpCircle, 
  CreditCard,
  ChevronRight,
  Info
} from "lucide-react";
import { 
  fetchProfile, 
  updateProfile, 
  fetchTransactions, 
  fetchBriefings, 
  uploadStatementFile,
  Transaction,
  Profile,
  Briefing
} from "./api";
import { 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  Cell
} from "recharts";

export default function Dashboard() {
  // App State
  const [profile, setProfile] = useState<Profile | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [briefings, setBriefings] = useState<Briefing[]>([]);
  const [selectedBriefing, setSelectedBriefing] = useState<Briefing | null>(null);
  
  // Loading & Action States
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  
  // Form fields
  const [currency, setCurrency] = useState("GBP");
  const [savingsGoal, setSavingsGoal] = useState(500);

  // File Upload Reference
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Profile ID defaults to mock UUID
  const PROFILE_ID = "00000000-0000-0000-0000-000000000000";

  // Currency symbols mapper
  const currencySymbol = (code: string) => {
    switch (code?.toUpperCase()) {
      case "USD": return "$";
      case "EUR": return "€";
      case "GBP": return "£";
      default: return code || "£";
    }
  };

  // Initial load
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const p = await fetchProfile(PROFILE_ID);
        setProfile(p);
        setCurrency(p.currency);
        setSavingsGoal(p.savings_goal);

        const txs = await fetchTransactions(PROFILE_ID);
        setTransactions(txs);

        const b = await fetchBriefings(PROFILE_ID);
        setBriefings(b);
        if (b.length > 0) {
          setSelectedBriefing(b[0]);
        }
      } catch (err) {
        console.error("Failed to load initial data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Update profile
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const updated = await updateProfile(currency, savingsGoal, PROFILE_ID);
      setProfile(updated);
      setShowSettingsModal(false);
      setSuccessMessage("Settings updated successfully!");
      
      // Reload briefings / transactions to apply home currency changes
      const txs = await fetchTransactions(PROFILE_ID);
      setTransactions(txs);
      const b = await fetchBriefings(PROFILE_ID);
      setBriefings(b);
      if (b.length > 0) {
        setSelectedBriefing(b[0]);
      }
      
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (err) {
      setErrorMessage("Failed to save settings");
      setTimeout(() => setErrorMessage(""), 3000);
    } finally {
      setLoading(false);
    }
  };

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await processUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await processUpload(e.target.files[0]);
    }
  };

  const processUpload = async (file: File) => {
    setUploading(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const response = await uploadStatementFile(file, PROFILE_ID);
      setSuccessMessage(`Success: ${response.summary}`);
      setShowUploadModal(false);
      
      // Reload everything
      const p = await fetchProfile(PROFILE_ID);
      setProfile(p);
      const txs = await fetchTransactions(PROFILE_ID);
      setTransactions(txs);
      const b = await fetchBriefings(PROFILE_ID);
      setBriefings(b);
      if (b.length > 0) {
        setSelectedBriefing(b[0]);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to parse statement");
    } finally {
      setUploading(false);
    }
  };

  // Formatting helpers
  const fmtCurrency = (amount: number) => {
    const sym = currencySymbol(profile?.currency || "GBP");
    return `${sym}${Math.abs(amount).toFixed(2)}`;
  };

  // Simple Markdown Parsing for briefing text
  const renderBriefing = (text: string) => {
    if (!text) return <p className="text-muted">No briefing text available.</p>;
    
    const lines = text.split("\n");
    return (
      <div className="briefing-content">
        {lines.map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={idx} className="h-2" />;

          // Check if bullet point
          if (trimmed.startsWith("•") || trimmed.startsWith("-")) {
            const content = trimmed.substring(1).trim();
            // Split observation and implication/action
            const splitIdx = content.indexOf(" — ");
            if (splitIdx !== -1) {
              const obs = content.substring(0, splitIdx);
              const imp = content.substring(splitIdx + 3);
              return (
                <div key={idx} className="flex gap-2 items-start py-2 border-b border-white/5 last:border-b-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                  <span className="text-sm leading-relaxed">
                    <strong className="text-white">{obs}</strong> — <span className="text-slate-300">{imp}</span>
                  </span>
                </div>
              );
            }
            return (
              <div key={idx} className="flex gap-2 items-start py-2 border-b border-white/5 last:border-b-0">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                <span className="text-sm text-slate-200 leading-relaxed">{content}</span>
              </div>
            );
          }
          
          // Check if Numbered Move
          const moveMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
          if (moveMatch) {
            const num = moveMatch[1];
            const content = moveMatch[2];
            const arrowIdx = content.indexOf(" → ");
            if (arrowIdx !== -1) {
              const action = content.substring(0, arrowIdx);
              const savings = content.substring(arrowIdx + 3);
              return (
                <div key={idx} className="flex gap-3 items-start py-3 bg-white/5 rounded-lg px-4 my-2 border border-white/5">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-300 font-bold text-xs flex-shrink-0">
                    {num}
                  </span>
                  <div className="text-sm">
                    <strong className="text-white font-semibold block text-base">{action}</strong>
                    <span className="text-indigo-400 font-bold">{savings}</span>
                  </div>
                </div>
              );
            }
            return (
              <div key={idx} className="flex gap-3 items-start py-2 bg-white/5 rounded-lg px-4 my-2">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-300 font-bold text-xs flex-shrink-0">
                  {num}
                </span>
                <span className="text-sm text-slate-200">{content}</span>
              </div>
            );
          }

          // Check if Bold title or section headers
          if (trimmed.startsWith("**") && trimmed.endsWith("**")) {
            return (
              <h3 key={idx} className="text-lg font-bold text-white mt-6 mb-2 border-b border-indigo-500/20 pb-1 font-title">
                {trimmed.replace(/\*\*/g, "")}
              </h3>
            );
          }

          // Regular headers based on exact briefing section names
          const sections = ["Month in numbers", "What stood out", "Subscriptions to review", "Your top 3 moves this month", "Heads up"];
          if (sections.includes(trimmed)) {
            return (
              <h4 key={idx} className="text-base font-bold text-indigo-300 uppercase tracking-wider mt-6 mb-3 font-title border-l-2 border-indigo-500 pl-3">
                {trimmed}
              </h4>
            );
          }

          // Bold text highlights
          if (trimmed.startsWith("**") || trimmed.includes("**")) {
            // Very simple replacement of double stars with bold HTML
            const parts = trimmed.split("**");
            return (
              <p key={idx} className="text-sm leading-relaxed my-2 text-slate-200">
                {parts.map((part, pIdx) => pIdx % 2 === 1 ? <strong key={pIdx} className="text-indigo-300 font-bold">{part}</strong> : part)}
              </p>
            );
          }

          return (
            <p key={idx} className="text-sm leading-relaxed my-2 text-slate-300">
              {trimmed}
            </p>
          );
        })}
      </div>
    );
  };

  // Safe checks for active analysis
  const activeAnalysis = selectedBriefing?.analysis;
  
  // Format chart data
  const chartData = activeAnalysis?.categories ? Object.entries(activeAnalysis.categories).map(([name, data]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    amount: data.total
  })).sort((a, b) => b.amount - a.amount) : [];

  const topCategory = chartData[0]?.name || "None";
  const savingsRate = activeAnalysis?.savings_rate ?? 0;
  const isSavingsGoalMet = (activeAnalysis?.saved ?? 0) >= savingsGoal;

  return (
    <div className="min-h-screen pb-16">
      {/* Header Panel */}
      <header className="border-b border-white/5 bg-slate-950/40 backdrop-blur-md sticky top-0 z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white font-title">FinSense</h1>
              <p className="text-xs text-slate-400">Autonomous Finance Agent</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {briefings.length > 0 && (
              <div className="flex items-center gap-2 bg-slate-900/60 border border-white/5 rounded-lg px-3 py-1.5 text-sm">
                <Calendar className="w-4 h-4 text-slate-400" />
                <select 
                  className="bg-transparent border-none text-white outline-none cursor-pointer"
                  value={selectedBriefing?.month || ""}
                  onChange={(e) => {
                    const found = briefings.find(b => b.month === e.target.value);
                    if (found) setSelectedBriefing(found);
                  }}
                >
                  {briefings.map(b => (
                    <option key={b.id} value={b.month} className="bg-slate-900 text-white">
                      {b.month}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <button 
              onClick={() => setShowSettingsModal(true)}
              className="btn-secondary"
              title="Configure Goals"
              style={{ padding: "10px" }}
            >
              <Settings className="w-5 h-5 text-slate-300" />
            </button>

            <button 
              onClick={() => setShowUploadModal(true)}
              className="btn-primary"
            >
              <Upload className="w-4 h-4" />
              <span>Import Statement</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 mt-8">
        
        {/* Banner Alert Messages */}
        {successMessage && (
          <div className="mb-6 flex items-center gap-3 bg-emerald-950/40 border border-emerald-500/20 text-emerald-400 px-4 py-3 rounded-lg text-sm shadow-md animate-fadeIn">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}
        
        {errorMessage && (
          <div className="mb-6 flex items-center gap-3 bg-rose-950/40 border border-rose-500/20 text-rose-400 px-4 py-3 rounded-lg text-sm shadow-md animate-fadeIn">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
            <p className="text-slate-400 text-sm font-title">Loading dashboard analytics...</p>
          </div>
        ) : !selectedBriefing ? (
          /* Empty State */
          <div className="glass-card flex flex-col items-center text-center py-20 max-w-xl mx-auto mt-12">
            <div className="w-16 h-16 rounded-full bg-indigo-500/10 flex items-center justify-center mb-6 border border-indigo-500/20">
              <BookOpen className="w-8 h-8 text-indigo-400" />
            </div>
            <h2 className="text-2xl font-bold font-title text-white mb-2">No Transactions Ingested Yet</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-8">
              Upload your bank statement (CSV, PDF, or Excel) to activate your AI finance agent. We will automatically map merchants, check for subscription burn, highlight anomalies, and write a monthly briefing.
            </p>
            <button 
              onClick={() => setShowUploadModal(true)}
              className="btn-primary"
            >
              <Upload className="w-4 h-4" />
              <span>Import Your First Statement</span>
            </button>
          </div>
        ) : (
          /* Active Dashboard state */
          <>
            {/* KPI Cards Container */}
            <div className="kpi-container">
              <div className="glass-card kpi-card">
                <span className="kpi-label">Total Outflows</span>
                <span className="kpi-value text-white">
                  {fmtCurrency(activeAnalysis?.spent || 0)}
                </span>
                <span className="kpi-subtext flex items-center gap-1">
                  {activeAnalysis?.mom_spent_change_pct && activeAnalysis.mom_spent_change_pct !== 0 ? (
                    <>
                      {activeAnalysis.mom_spent_change_pct > 0 ? (
                        <span className="kpi-trend-up flex items-center text-xs">
                          <TrendingUp className="w-3.5 h-3.5 mr-0.5" />
                          +{activeAnalysis.mom_spent_change_pct.toFixed(1)}% MoM
                        </span>
                      ) : (
                        <span className="kpi-trend-down flex items-center text-xs">
                          <TrendingDown className="w-3.5 h-3.5 mr-0.5" />
                          {activeAnalysis.mom_spent_change_pct.toFixed(1)}% MoM
                        </span>
                      )}
                    </>
                  ) : (
                    <span>No prior history</span>
                  )}
                </span>
              </div>

              <div className="glass-card kpi-card">
                <span className="kpi-label">Net Saved</span>
                <span className="kpi-value text-emerald-400">
                  {fmtCurrency(activeAnalysis?.saved || 0)}
                </span>
                <span className="kpi-subtext">
                  Target: {fmtCurrency(savingsGoal)}
                </span>
              </div>

              <div className="glass-card kpi-card">
                <span className="kpi-label">Savings Rate</span>
                <span className="kpi-value text-white">
                  {savingsRate.toFixed(1)}%
                </span>
                <span className="kpi-subtext flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${isSavingsGoalMet ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                  {isSavingsGoalMet ? 'Savings Target Met' : 'Under Goal'}
                </span>
              </div>

              <div className="glass-card kpi-card">
                <span className="kpi-label">Top Category</span>
                <span className="kpi-value text-indigo-300">
                  {topCategory}
                </span>
                <span className="kpi-subtext">
                  Total: {fmtCurrency(chartData[0]?.amount || 0)}
                </span>
              </div>
            </div>

            {/* Dashboard grid layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              
              {/* Left Column: Briefing & Opportunities */}
              <div className="lg:col-span-2 flex flex-col gap-8">
                
                {/* Monthly Briefing Card */}
                <div className="glass-card">
                  <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-5 h-5 text-indigo-400" />
                      <h2 className="text-lg font-bold font-title text-white">Monthly Briefing ({selectedBriefing.month})</h2>
                    </div>
                    {selectedBriefing.analysis?.month && (
                      <span className="text-xs px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-bold uppercase">
                        AI Verified
                      </span>
                    )}
                  </div>
                  {renderBriefing(selectedBriefing.briefing_text)}
                </div>

                {/* Savings Opportunities */}
                <div className="glass-card">
                  <div className="flex items-center gap-2 border-b border-white/5 pb-4 mb-6">
                    <Zap className="w-5 h-5 text-amber-400" />
                    <h2 className="text-lg font-bold font-title text-white">Ranked Savings Moves</h2>
                  </div>
                  <div className="flex flex-col gap-4">
                    {activeAnalysis?.opportunities && activeAnalysis.opportunities.length > 0 ? (
                      activeAnalysis.opportunities.map((opp, idx) => (
                        <div key={idx} className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-slate-900/40 rounded-xl border border-white/5 gap-4 hover:border-indigo-500/25 transition-all">
                          <div className="flex items-start gap-3">
                            <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-indigo-500/10 text-indigo-400 font-bold text-sm mt-0.5">
                              {idx + 1}
                            </span>
                            <div>
                              <h4 className="font-semibold text-white text-sm mb-1">{opp.action}</h4>
                              <p className="text-xs text-slate-400 flex items-center gap-1">
                                <Info className="w-3.5 h-3.5 flex-shrink-0 text-slate-500" />
                                {opp.evidence}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-4 justify-between md:justify-end border-t md:border-t-0 border-white/5 pt-3 md:pt-0">
                            <div>
                              <span className="text-xs text-slate-500 block text-left md:text-right">Estimated Saving</span>
                              <span className="font-bold text-emerald-400 font-title">
                                +{fmtCurrency(opp.saving)}/mo
                              </span>
                            </div>
                            <div className="text-right">
                              <span className="text-xs text-slate-500 block text-left md:text-right">Effort</span>
                              <span className={`badge ${opp.effort.toLowerCase() === 'low' ? 'badge-high' : opp.effort.toLowerCase() === 'medium' ? 'badge-medium' : 'badge-low'}`}>
                                {opp.effort}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-muted text-sm text-center py-4">No specific opportunities identified this month.</p>
                    )}
                  </div>
                </div>

              </div>

              {/* Right Column: Categories & Subscriptions */}
              <div className="flex flex-col gap-8">
                
                {/* Visual Category Distribution */}
                <div className="glass-card">
                  <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
                    <h2 className="text-lg font-bold font-title text-white">Outflow Breakdown</h2>
                  </div>
                  {chartData.length > 0 ? (
                    <>
                      <div className="h-48 mt-2 mb-4">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={chartData} margin={{ top: 0, right: 0, left: -25, bottom: 0 }}>
                            <XAxis 
                              dataKey="name" 
                              stroke="#64748b" 
                              fontSize={10} 
                              tickLine={false}
                              axisLine={false} 
                            />
                            <YAxis 
                              stroke="#64748b" 
                              fontSize={10} 
                              tickLine={false}
                              axisLine={false} 
                            />
                            <Tooltip 
                              cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }} 
                              contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px' }}
                              labelStyle={{ color: '#fff', fontWeight: 'bold' }}
                            />
                            <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
                              {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={index === 0 ? '#6366f1' : '#4f46e5'} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      <div className="flex flex-col gap-3">
                        {Object.entries(activeAnalysis?.categories || {}).map(([name, data]) => (
                          <div key={name} className="flex items-center justify-between text-xs py-2 border-b border-white/5 last:border-0">
                            <div>
                              <span className="font-semibold text-slate-300 capitalize">{name}</span>
                              {data.flagged_high && (
                                <span className="ml-2 text-[10px] font-bold text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20">
                                  +20% Above Avg
                                </span>
                              )}
                            </div>
                            <div className="text-right">
                              <span className="text-white font-bold block">{fmtCurrency(data.total)}</span>
                              <span className="text-slate-500">{data.pct_of_income.toFixed(1)}% of income</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="text-muted text-sm text-center py-10">No categories data.</p>
                  )}
                </div>

                {/* Subscriptions Audit */}
                <div className="glass-card">
                  <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
                    <div className="flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-indigo-400" />
                      <h2 className="text-lg font-bold font-title text-white">Subscription Burn</h2>
                    </div>
                    <span className="font-bold text-white font-title text-sm">
                      {fmtCurrency(activeAnalysis?.subscriptions?.total_monthly_burn || 0)}/mo
                    </span>
                  </div>
                  
                  <div className="flex flex-col gap-3">
                    {activeAnalysis?.subscriptions?.items && activeAnalysis.subscriptions.items.length > 0 ? (
                      activeAnalysis.subscriptions.items.map((sub, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-white/5">
                          <div>
                            <span className="font-semibold text-white text-sm block">{sub.merchant}</span>
                            {sub.flags.map(f => (
                              <span key={f} className={`flag-pill ${f.toLowerCase().includes('new') ? 'new_sub' : 'price_inc'}`} style={{ margin: "2px 4px 0 0", fontSize: "9px" }}>
                                {f.replace("_", " ")}
                              </span>
                            ))}
                          </div>
                          <span className="font-bold text-white text-sm">{fmtCurrency(sub.amount)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-400 text-xs text-center py-6">All subscriptions look normal.</p>
                    )}
                  </div>
                </div>

              </div>

            </div>

            {/* Transactions History Section */}
            <div className="glass-card mt-8">
              <div className="flex items-center justify-between pb-4 mb-6 border-b border-white/5">
                <h2 className="text-lg font-bold font-title text-white">Ingested Transaction Details</h2>
                <span className="text-xs text-slate-400">{transactions.length} items parsed</span>
              </div>

              <div className="premium-table-container">
                <table className="premium-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Description</th>
                      <th>Merchant</th>
                      <th>Category</th>
                      <th>Amount</th>
                      <th>Flags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx) => {
                      const isDebit = tx.amount > 0;
                      const strippedCat = tx.category.replace("?", "");
                      const isIncome = strippedCat === "income";
                      
                      return (
                        <tr key={tx.id}>
                          <td className="text-slate-400 font-medium whitespace-nowrap">{tx.date}</td>
                          <td className="text-slate-200">{tx.description}</td>
                          <td className="text-white font-semibold">{tx.merchant}</td>
                          <td className="whitespace-nowrap">
                            <span className="flex items-center gap-1 text-slate-300">
                              <span className="capitalize">{strippedCat}</span>
                              {tx.category.includes("?") && (
                                <HelpCircle 
                                  className="w-3.5 h-3.5 text-amber-400" 
                                  title="Categorised with Medium confidence. Click to confirm." 
                                />
                              )}
                            </span>
                          </td>
                          <td className={`font-bold whitespace-nowrap ${isIncome ? 'text-emerald-400' : 'text-slate-200'}`}>
                            {isIncome ? '-' : ''}{fmtCurrency(tx.amount)}
                          </td>
                          <td>
                            {tx.flags && tx.flags.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {tx.flags.map(f => (
                                  <span key={f} className={`flag-pill ${f.toLowerCase().includes('new') ? 'new_sub' : ''}`}>
                                    {f.replace("_", " ")}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-slate-600">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

      </main>

      {/* Upload File Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={() => !uploading && setShowUploadModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold font-title text-white">Import Bank Statement</h3>
              <button 
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-white"
                disabled={uploading}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div 
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                dragActive ? 'border-indigo-500 bg-indigo-500/5' : 'border-white/10 hover:border-white/20'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => !uploading && fileInputRef.current?.click()}
            >
              <input 
                ref={fileInputRef}
                type="file" 
                className="hidden" 
                accept=".csv,.pdf,.xlsx,.xls"
                onChange={handleFileChange}
                disabled={uploading}
              />
              
              {uploading ? (
                <div className="flex flex-col items-center py-6 gap-3">
                  <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
                  <p className="text-sm font-semibold text-white font-title">Analyzing Statement...</p>
                  <p className="text-xs text-slate-400">Parsing items, identifying anomalies, generating briefing</p>
                </div>
              ) : (
                <div className="flex flex-col items-center py-4">
                  <div className="w-12 h-12 rounded-lg bg-indigo-500/10 flex items-center justify-center mb-4 border border-indigo-500/25">
                    <Upload className="w-6 h-6 text-indigo-400" />
                  </div>
                  <p className="text-sm font-semibold text-white mb-1">Drag and drop file here</p>
                  <p className="text-xs text-slate-400 mb-4">CSV, PDF, Excel statements up to 10MB</p>
                  <span className="text-xs px-3 py-1.5 rounded bg-white/5 border border-white/5 text-slate-300 font-semibold font-title">
                    Select File
                  </span>
                </div>
              )}
            </div>

            <div className="mt-6 flex items-start gap-2 bg-indigo-950/20 border border-indigo-500/15 p-3 rounded-lg text-xs text-indigo-300">
              <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>
                Statement files are parsed and normalised locally. No sensitive account numbers or credentials are saved or echoed.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      {showSettingsModal && (
        <div className="modal-overlay" onClick={() => setShowSettingsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold font-title text-white">Agent Configuration</h3>
              <button 
                onClick={() => setShowSettingsModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveSettings} className="flex flex-col gap-4">
              <div>
                <label className="form-label">Default Home Currency</label>
                <select 
                  className="form-input"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                >
                  <option value="GBP">GBP (£)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Monthly Savings Goal ({currencySymbol(currency)})</label>
                <input 
                  type="number" 
                  className="form-input"
                  value={savingsGoal}
                  onChange={(e) => setSavingsGoal(parseInt(e.target.value) || 0)}
                  min="0"
                />
              </div>

              <div className="mt-6 flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setShowSettingsModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn-primary"
                >
                  Save Configuration
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
