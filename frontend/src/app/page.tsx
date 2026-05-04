"use client";

import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  MessageSquareDiff,
  CheckSquare,
  Settings,
  Book,
  LogOut,
  Bell,
  MonitorPlay,
  HelpCircle,
  Check,
  X,
  MessageCircle,
  Sparkles,
  ArrowUpRight,
  ExternalLink,
  Play,
  Square,
  MoreVertical
} from "lucide-react";

interface Opportunity {
  id: string;
  subreddit: string;
  title: string;
  body: string;
  url: string;
  score: number;
  status: string;
  reasons: string[];
  drafts: string[];
  created_at: string;
}

interface Summary {
  pending: number;
  approved: number;
  rejected: number;
}

interface Playbook {
  subreddit: string;
  rules_text: string;
  notes: string;
  updated_at: string;
}

interface AuditLog {
  id: number;
  opportunity_id: string;
  action: string;
  actor: string;
  note: string;
  created_at: string;
}

interface BotProfile {
  subreddits: string[];
  keywords: string[];
  knowledge_block: string;
}

type AuditActionFilter = "all" | "approved" | "rejected";
type ConfigTab = "profile" | "playbooks";

export default function Gatekeeper() {
  const [currentView, setCurrentView] = useState("triage");
  
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selectedOppId, setSelectedOppId] = useState<string | null>(null);
  
  const [summary, setSummary] = useState<Summary>({ pending: 0, approved: 0, rejected: 0 });
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [selectedSubreddit, setSelectedSubreddit] = useState<string | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditActionFilter, setAuditActionFilter] = useState<AuditActionFilter>("approved");
  
  const [configTab, setConfigTab] = useState<ConfigTab>("profile");
  const [profile, setProfile] = useState<BotProfile | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");

  const [note, setNote] = useState<string>("");
  const [botRunning, setBotRunning] = useState<boolean>(false);
  const [triageMenuOpen, setTriageMenuOpen] = useState<boolean>(false);
  const [runtimeLoading, setRuntimeLoading] = useState<boolean>(false);

  const [subredditInput, setSubredditInput] = useState("");
  const [subredditSuggestions, setSubredditSuggestions] = useState<string[]>([]);
  const [suggestingKeywords, setSuggestingKeywords] = useState(false);
  const [keywordSuggestions, setKeywordSuggestions] = useState<string[]>([]);

  const fetchOpportunities = async () => {
    setLoading(true);
    try {
      const statusParam = filter !== "all" ? `?status=${filter}` : "";
      const res = await fetch(`/api/opportunities${statusParam}`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setOpportunities(data.opportunities);
      setSummary(data.summary);

      // Keep current selection stable across refreshes.
      setSelectedOppId((prevSelectedId) => {
        if (data.opportunities.length === 0) {
          return null;
        }
        if (prevSelectedId && data.opportunities.some((o: Opportunity) => o.id === prevSelectedId)) {
          return prevSelectedId;
        }
        return data.opportunities[0].id;
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPlaybooks = async () => {
    try {
      const res = await fetch(`/api/playbooks`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setPlaybooks(data.playbooks);
      if (data.playbooks.length > 0) {
        setSelectedSubreddit(prev => prev || data.playbooks[0].subreddit);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await fetch(`/api/audit`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setAuditLogs(data.logs);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchRuntimeStatus = async () => {
    try {
      const res = await fetch("/api/runtime");
      if (!res.ok) throw new Error("Failed to fetch runtime status");
      const data = await res.json();
      setBotRunning(Boolean(data.running));
    } catch (err) {
      console.error(err);
    }
  };

  const fetchProfile = async () => {
    try {
      const res = await fetch("/api/profile");
      if (!res.ok) throw new Error("Failed to fetch profile");
      const data = await res.json();
      setProfile(data);
    } catch (err) {
      console.error(err);
    }
  };

  const saveProfile = async () => {
    if (!profile) return;
    setSavingProfile(true);
    setProfileMessage("");
    try {
      const res = await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile)
      });
      if (res.ok) {
        setProfileMessage("Profile saved successfully. Engine restarting...");
        setTimeout(() => setProfileMessage(""), 5000);
      } else {
        setProfileMessage("Error saving profile.");
      }
    } catch (err) {
      console.error(err);
      setProfileMessage("Error saving profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      if (currentView === "triage") {
        void fetchOpportunities();
        void fetchRuntimeStatus();
      } else if (currentView === "config") {
        void fetchPlaybooks();
        void fetchProfile();
      } else if (currentView === "approvals") {
        void fetchAuditLogs();
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [filter, currentView]);

  useEffect(() => {
    if (currentView !== "triage") {
      return;
    }

    const runtimeTimer = setInterval(fetchRuntimeStatus, 5000);
    const dataTimer = botRunning ? setInterval(fetchOpportunities, 10000) : null;
    return () => {
      clearInterval(runtimeTimer);
      if (dataTimer) {
        clearInterval(dataTimer);
      }
    };
  }, [currentView, filter, botRunning]);

  useEffect(() => {
    if (!subredditInput || subredditInput.length < 2) {
      setSubredditSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search_subreddits?q=${encodeURIComponent(subredditInput)}`);
        const data = await res.json();
        setSubredditSuggestions(data.results || []);
      } catch(e) {}
    }, 400);
    return () => clearTimeout(timer);
  }, [subredditInput]);

  const generateKeywords = async () => {
    setSuggestingKeywords(true);
    try {
      const res = await fetch("/api/suggest_keywords", { method: "POST" });
      const data = await res.json();
      if (data.suggestions) {
        setKeywordSuggestions(data.suggestions);
      }
    } catch(e) {}
    setSuggestingKeywords(false);
  };

  const toggleRuntime = async () => {
    setRuntimeLoading(true);
    try {
      const endpoint = botRunning ? "/api/runtime/stop" : "/api/runtime/start";
      const res = await fetch(endpoint, { method: "POST" });
      if (!res.ok) throw new Error("Failed to change runtime state");
      const data = await res.json();
      const isRunning = Boolean(data.running);
      setBotRunning(isRunning);
      if (isRunning) {
        void fetchOpportunities();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setRuntimeLoading(false);
    }
  };

  const handleAction = async (id: string, action: "approve" | "reject") => {
    try {
      const res = await fetch(`/api/opportunity/${id}/${action}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ note }),
      });
      if (res.ok) {
        setNote(""); // clear note
        fetchOpportunities(); // will auto-select next item
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDiscardAll = async () => {
    try {
      const res = await fetch("/api/opportunities/reject_all", { method: "POST" });
      if (res.ok) {
        setTriageMenuOpen(false);
        fetchOpportunities();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const activeOpp = opportunities.find(o => o.id === selectedOppId);
  const filteredAuditLogs = auditLogs.filter((log) => {
    if (auditActionFilter === "all") return true;
    return log.action === auditActionFilter;
  });

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">SOLOA AI</div>
          <div className="sidebar-subtitle">REDDIT ENGINE</div>
        </div>

        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${currentView === "dashboard" ? "active" : ""}`}
            onClick={() => setCurrentView("dashboard")}
          >
            <LayoutDashboard className="nav-icon" /> DASHBOARD
          </button>
          <button 
            className={`nav-item ${currentView === "triage" ? "active" : ""}`}
            onClick={() => setCurrentView("triage")}
          >
            <MessageSquareDiff className="nav-icon" /> MENTIONS & TRIAGE
          </button>
          <button 
            className={`nav-item ${currentView === "approvals" ? "active" : ""}`}
            onClick={() => setCurrentView("approvals")}
          >
            <CheckSquare className="nav-icon" /> APPROVALS (AUDIT)
          </button>
          <button 
            className={`nav-item ${currentView === "config" ? "active" : ""}`}
            onClick={() => setCurrentView("config")}
          >
            <Settings className="nav-icon" /> CONFIGURATION
          </button>
        </nav>

        <div className="sidebar-footer">
          <a href="#" className="nav-item">
            <Book className="nav-icon" /> DOCS
          </a>
          <a href="#" className="nav-item">
            <LogOut className="nav-icon" /> LOGOUT
          </a>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="topbar">
          <div className="page-title">
            The Gatekeeper <span className="page-version">v2.5.0-master</span>
          </div>
          <div className="topbar-actions">
            <div className="bot-controls">
              <div className="bot-state">
                <div className={`status-dot ${botRunning ? "running" : "stopped"}`}></div>
                {botRunning ? "BOT: RUNNING" : "BOT: STOPPED"}
              </div>
              <button 
                className={`btn-start-bot ${botRunning ? "active" : ""}`}
                onClick={toggleRuntime}
                disabled={runtimeLoading}
              >
                {runtimeLoading
                  ? "WAIT..."
                  : botRunning
                    ? <><Square size={14} fill="currentColor" /> STOP ENGINE</>
                    : <><Play size={14} fill="currentColor" /> START ENGINE</>}
              </button>
            </div>
            <Bell className="topbar-icon" />
            <MonitorPlay className="topbar-icon" />
            <HelpCircle className="topbar-icon" />
            <div className="user-avatar"></div>
          </div>
        </header>

        {currentView === "triage" && (
          <>
            <div className="content-header">
              <div className="filters">
                <button
                  className={`filter-btn ${filter === "all" ? "active" : ""}`}
                  onClick={() => setFilter("all")}
                >
                  <LayoutDashboard size={14} /> ALL
                </button>
                <button
                  className={`filter-btn ${filter === "pending" ? "active" : ""}`}
                  onClick={() => setFilter("pending")}
                >
                  <div className="filter-dot"></div> PENDING ({summary.pending})
                </button>
                <button
                  className={`filter-btn ${filter === "rejected" ? "active" : ""}`}
                  onClick={() => setFilter("rejected")}
                >
                  DISCARDED
                </button>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                <div className="processing-rate">PROCESSING RATE: 42/min</div>
                <div style={{ position: "relative" }}>
                  <button 
                    onClick={() => setTriageMenuOpen(!triageMenuOpen)}
                    style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "4px" }}
                  >
                    <MoreVertical size={16} />
                  </button>
                  {triageMenuOpen && (
                    <div style={{ position: "absolute", top: "100%", right: "0", marginTop: "4px", background: "var(--bg-card)", border: "1px solid var(--border-color)", borderRadius: "6px", padding: "4px", zIndex: 10, minWidth: "140px", boxShadow: "0 4px 12px rgba(0,0,0,0.2)" }}>
                      <button 
                        onClick={handleDiscardAll}
                        style={{ display: "flex", width: "100%", alignItems: "center", gap: "8px", padding: "8px 12px", background: "transparent", border: "none", color: "#FCA5A5", fontSize: "0.85rem", fontWeight: "600", cursor: "pointer", borderRadius: "4px", textAlign: "left" }}
                        onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)"}
                        onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                      >
                        <X size={14} /> Discard All
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="triage-layout">
              {/* Inbox List (Left Pane) */}
              <div className="inbox-list">
                {loading ? (
                  <div style={{ padding: "2rem", color: "var(--text-muted)", textAlign: "center" }}>Loading...</div>
                ) : opportunities.length === 0 ? (
                  <div style={{ padding: "2rem", color: "var(--text-muted)", textAlign: "center" }}>No mentions found.</div>
                ) : (
                  opportunities.map((opp) => (
                    <div 
                      key={opp.id} 
                      className={`list-item ${selectedOppId === opp.id ? "active" : ""}`}
                      onClick={() => setSelectedOppId(opp.id)}
                    >
                      <div className="list-item-header">
                        <span className="list-item-meta">r/{opp.subreddit}</span>
                        <a
                          href={opp.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="list-open-link"
                          onClick={(e) => e.stopPropagation()}
                          title="Open post in Reddit"
                        >
                          <ExternalLink size={12} />
                        </a>
                        <span className={`card-pill ${opp.status === "pending" ? "triage" : opp.status}`}>
                          {opp.status === "pending" ? "Triage" : opp.status}
                        </span>
                      </div>
                      <div className="list-item-title">{opp.title}</div>
                      <div className="list-item-preview">{opp.body}</div>
                    </div>
                  ))
                )}
              </div>

              {/* Detail View (Right Pane) */}
              <div className="inbox-detail">
                {!activeOpp ? (
                  <div className="empty-state">
                    <div>Select a mention from the list to review</div>
                  </div>
                ) : (
                  <>
                    <div className="detail-scroll-area">
                      <div className="detail-header-meta">
                        <span className="detail-subreddit">r/{activeOpp.subreddit}</span>
                        <span className="detail-score">Score: {activeOpp.score}</span>
                        <a href={activeOpp.url} target="_blank" rel="noopener noreferrer" className="detail-link">
                          Open in Reddit <ArrowUpRight size={14} style={{ marginLeft: "4px" }}/>
                        </a>
                      </div>
                      
                      <h1 className="detail-title">{activeOpp.title}</h1>
                      <div className="detail-body">{activeOpp.body}</div>

                      <div className="ai-insight-box">
                        <div className="insight-header">
                          <Sparkles size={14} /> MODEL REASONING
                        </div>
                        <div className="insight-content">
                          {activeOpp.reasons && activeOpp.reasons.length > 0
                            ? activeOpp.reasons.map((r, i) => <div key={i} style={{marginBottom: "0.5rem"}}>• {r}</div>)
                            : "No specific reasoning available."}
                        </div>
                      </div>

                      {activeOpp.drafts && activeOpp.drafts.length > 0 && (
                        <div className="ai-insight-box" style={{ background: "transparent" }}>
                          <div className="insight-header">
                            <MessageCircle size={14} /> GENERATED DRAFTS
                          </div>
                          <div className="insight-content">
                            {activeOpp.drafts.map((draft, i) => (
                              <div key={i} className="draft-item">{draft}</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Fixed Action Bar at Bottom */}
                    {activeOpp.status === "pending" && (
                      <div className="detail-action-bar">
                        <input 
                          type="text" 
                          className="action-input" 
                          placeholder="Add an optional note (e.g. adjust tone, use draft 2)..."
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          onKeyDown={(e) => {
                            if(e.key === 'Enter') handleAction(activeOpp.id, "approve")
                          }}
                        />
                        <button className="btn btn-discard" onClick={() => handleAction(activeOpp.id, "reject")}>
                          <X size={16} /> DISCARD
                        </button>
                        <a
                          href={activeOpp.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-open"
                        >
                          <ExternalLink size={16} /> OPEN POST
                        </a>
                        <button className="btn btn-approve" onClick={() => handleAction(activeOpp.id, "approve")}>
                          <Check size={16} /> APPROVE
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </>
        )}

        {currentView === "approvals" && (
          <div className="scroll-container">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
              <h2 style={{ fontSize: "1.2rem", color: "var(--text-primary)" }}>Audit Log</h2>
              <div className="filters">
                <button className={`filter-btn ${auditActionFilter === "all" ? "active" : ""}`} onClick={() => setAuditActionFilter("all")}>
                  ALL ({auditLogs.length})
                </button>
                <button className={`filter-btn ${auditActionFilter === "approved" ? "active" : ""}`} onClick={() => setAuditActionFilter("approved")}>
                  APPROVED ({auditLogs.filter((l) => l.action === "approved").length})
                </button>
                <button className={`filter-btn ${auditActionFilter === "rejected" ? "active" : ""}`} onClick={() => setAuditActionFilter("rejected")}>
                  DISCARDED ({auditLogs.filter((l) => l.action === "rejected").length})
                </button>
              </div>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>OPPORTUNITY</th>
                  <th>ACTION</th>
                  <th>ACTOR</th>
                  <th>NOTE</th>
                  <th>DATE</th>
                </tr>
              </thead>
              <tbody>
                {filteredAuditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: "center", color: "var(--text-muted)", padding: "3rem" }}>No logs found.</td>
                  </tr>
                ) : (
                  filteredAuditLogs.map((log) => (
                    <tr key={log.id}>
                      <td>{log.id}</td>
                      <td>{log.opportunity_id}</td>
                      <td>
                        <span className={`card-pill ${log.action === "approved" ? "approved" : log.action === "rejected" ? "rejected" : "triage"}`}>
                          {log.action}
                        </span>
                      </td>
                      <td>{log.actor}</td>
                      <td>{log.note || "-"}</td>
                      <td>{new Date(log.created_at).toLocaleString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {currentView === "config" && (
          <>
            <div className="content-header">
              <div className="filters">
                <button
                  className={`filter-btn ${configTab === "profile" ? "active" : ""}`}
                  onClick={() => setConfigTab("profile")}
                >
                  BOT PROFILE
                </button>
                <button
                  className={`filter-btn ${configTab === "playbooks" ? "active" : ""}`}
                  onClick={() => setConfigTab("playbooks")}
                >
                  PLAYBOOKS
                </button>
              </div>
            </div>

            {configTab === "profile" && profile && (
              <div className="scroll-container" style={{ paddingBottom: "100px" }}>
                <h2 style={{ fontSize: "1.2rem", color: "var(--text-primary)", marginBottom: "2rem" }}>Bot Identity & Engine Rules</h2>
                
                <div className="profile-grid">
                  <div className="profile-column" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                    <div className="profile-card">
                      <div>
                        <div className="profile-card-title">
                          Target Subreddits
                        </div>
                        <div className="profile-card-desc">
                          The communities the bot will actively monitor for pain points.
                        </div>
                      </div>
                      
                      <div className="tag-input-container">
                        <div className="tags-wrapper">
                          {profile.subreddits.map((tag, i) => (
                            <span key={i} className="tag-pill">
                              {tag}
                              <button 
                                type="button" 
                                onClick={() => setProfile({...profile, subreddits: profile.subreddits.filter((_, idx) => idx !== i)})} 
                                className="tag-remove-btn"
                              >
                                <X size={12} />
                              </button>
                            </span>
                          ))}
                          <div style={{ position: "relative", flex: 1, minWidth: "140px" }}>
                            <input
                              type="text"
                              className="tag-input-field"
                              placeholder="Search subreddit..."
                              value={subredditInput}
                              onChange={(e) => setSubredditInput(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && subredditInput.trim()) {
                                  e.preventDefault();
                                  const val = subredditInput.trim();
                                  if (!profile.subreddits.includes(val)) {
                                    setProfile({...profile, subreddits: [...profile.subreddits, val]});
                                  }
                                  setSubredditInput("");
                                }
                              }}
                              style={{ width: "100%" }}
                            />
                            {subredditSuggestions.length > 0 && (
                              <div style={{ position: "absolute", top: "100%", left: 0, right: 0, marginTop: "4px", background: "var(--bg-card)", border: "1px solid var(--border-color)", borderRadius: "6px", overflow: "hidden", zIndex: 10, boxShadow: "0 4px 12px rgba(0,0,0,0.5)" }}>
                                {subredditSuggestions.map(sub => (
                                  <div 
                                    key={sub}
                                    style={{ padding: "8px 12px", fontSize: "0.85rem", cursor: "pointer", color: "var(--text-primary)" }}
                                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "var(--bg-card-hover)"}
                                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                                    onClick={() => {
                                      if (!profile.subreddits.includes(sub)) {
                                        setProfile({...profile, subreddits: [...profile.subreddits, sub]});
                                      }
                                      setSubredditInput("");
                                      setSubredditSuggestions([]);
                                    }}
                                  >
                                    r/{sub}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="profile-card">
                      <div>
                        <div className="profile-card-title">
                          Pain Keywords
                        </div>
                        <div className="profile-card-desc">
                          Specific phrases that indicate a user is frustrated or struggling.
                        </div>
                      </div>
                      
                      <div className="tag-input-container">
                        <div className="tags-wrapper">
                          {profile.keywords.map((tag, i) => (
                            <span key={i} className="tag-pill">
                              {tag}
                              <button 
                                type="button" 
                                onClick={() => setProfile({...profile, keywords: profile.keywords.filter((_, idx) => idx !== i)})} 
                                className="tag-remove-btn"
                              >
                                <X size={12} />
                              </button>
                            </span>
                          ))}
                          <input
                            type="text"
                            className="tag-input-field"
                            placeholder="Add keyword & press Enter..."
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && e.currentTarget.value.trim()) {
                                e.preventDefault();
                                const val = e.currentTarget.value.trim();
                                if (!profile.keywords.includes(val)) {
                                  setProfile({...profile, keywords: [...profile.keywords, val]});
                                }
                                e.currentTarget.value = "";
                              }
                            }}
                          />
                        </div>
                      </div>
                      
                      {keywordSuggestions.length > 0 && (
                        <div style={{ marginTop: "0.5rem" }}>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.5rem", fontWeight: "600", textTransform: "uppercase" }}>AI SUGGESTIONS:</div>
                          <div className="tags-wrapper">
                            {keywordSuggestions.map((sug, i) => (
                              <span 
                                key={i} 
                                className="tag-pill" 
                                style={{ cursor: "pointer", borderStyle: "dashed" }}
                                onClick={() => {
                                  if (!profile.keywords.includes(sug)) {
                                    setProfile({...profile, keywords: [...profile.keywords, sug]});
                                  }
                                  setKeywordSuggestions(keywordSuggestions.filter(k => k !== sug));
                                }}
                                title="Click to add"
                              >
                                + {sug}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <button 
                        className="btn btn-open" 
                        style={{ alignSelf: "flex-start", padding: "0.5rem 1rem", fontSize: "0.75rem", marginTop: "auto" }}
                        onClick={generateKeywords}
                        disabled={suggestingKeywords}
                      >
                        {suggestingKeywords ? "ANALYZING KNOWLEDGE..." : "AI SUGGEST KEYWORDS"}
                      </button>
                    </div>
                  </div>

                  <div className="profile-column" style={{ display: "flex", flexDirection: "column" }}>
                    <div className="profile-card" style={{ flex: 1 }}>
                      <div>
                        <div className="profile-card-title">
                          Knowledge Block (System Prompt)
                        </div>
                        <div className="profile-card-desc">
                          The core product context fed to the LLM. Define your product's features, tone of voice, and Reddit positioning strategy here.
                        </div>
                      </div>

                      <div className="code-editor-wrapper">
                        <div className="code-editor-header">
                          <span>soloa_knowledge.md</span>
                          <span style={{ color: "var(--text-muted)" }}>MARKDOWN</span>
                        </div>
                        <textarea 
                          className="code-editor-textarea"
                          value={profile.knowledge_block}
                          onChange={(e) => setProfile({ ...profile, knowledge_block: e.target.value })}
                          spellCheck="false"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className={`profile-action-bar visible`}>
                  <div className="profile-unsaved-text">
                    <span style={{ color: profileMessage ? (profileMessage.includes("Error") ? "var(--color-danger)" : "var(--color-success)") : "var(--text-muted)" }}>
                      {profileMessage || "Remember to save your changes to update the engine."}
                    </span>
                  </div>
                  <button 
                    className="btn btn-approve" 
                    onClick={saveProfile}
                    disabled={savingProfile}
                  >
                    {savingProfile ? "SAVING & RESTARTING..." : "SAVE CONFIGURATION"}
                  </button>
                </div>
              </div>
            )}

            {configTab === "playbooks" && (
              <div className="triage-layout" style={{ height: "calc(100vh - 120px)" }}>
                {/* Inbox List (Left Pane) */}
                <div className="inbox-list">
                  {playbooks.length === 0 ? (
                    <div style={{ padding: "2rem", color: "var(--text-muted)", textAlign: "center" }}>No playbooks found.</div>
                  ) : (
                    playbooks.map((pb) => (
                      <div 
                        key={pb.subreddit} 
                        className={`list-item ${selectedSubreddit === pb.subreddit ? "active" : ""}`}
                        onClick={() => setSelectedSubreddit(pb.subreddit)}
                      >
                        <div className="list-item-header">
                          <span className="list-item-meta" style={{ fontWeight: 600 }}>r/{pb.subreddit}</span>
                        </div>
                        <div className="list-item-title" style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
                          Updated: {new Date(pb.updated_at).toLocaleDateString()}
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Detail View (Right Pane) */}
                <div className="inbox-detail">
                  {!selectedSubreddit ? (
                    <div className="empty-state">
                      <div>Select a subreddit to view its rules and playbooks</div>
                    </div>
                  ) : (() => {
                    const activePb = playbooks.find(p => p.subreddit === selectedSubreddit);
                    if (!activePb) return null;
                    return (
                      <div className="detail-scroll-area">
                        <div className="detail-header-meta">
                          <span className="detail-subreddit">r/{activePb.subreddit}</span>
                          <span className="detail-score">Last updated: {new Date(activePb.updated_at).toLocaleString()}</span>
                          <a href={`https://reddit.com/r/${activePb.subreddit}`} target="_blank" rel="noopener noreferrer" className="detail-link">
                            Visit Subreddit <ArrowUpRight size={14} style={{ marginLeft: "4px" }}/>
                          </a>
                        </div>
                        
                        <h1 className="detail-title">Subreddit Rules & Notes</h1>

                        <div className="ai-insight-box">
                          <div className="insight-header">
                            <CheckSquare size={14} /> COMMUNITY RULES
                          </div>
                          <div className="insight-content" style={{ whiteSpace: "pre-wrap", lineHeight: "1.6" }}>
                            {activePb.rules_text || "No rules available."}
                          </div>
                        </div>

                        <div className="ai-insight-box" style={{ background: "transparent", marginTop: "1rem" }}>
                          <div className="insight-header">
                            <MessageSquareDiff size={14} /> PLAYBOOK NOTES
                          </div>
                          <div className="insight-content">
                            {activePb.notes ? activePb.notes : <span style={{ color: "var(--text-muted)" }}>No additional operator notes.</span>}
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}
          </>
        )}

        {currentView === "dashboard" && (
          <div className="scroll-container">
            <h2 style={{ marginBottom: "1.5rem", fontSize: "1.2rem", color: "var(--text-primary)" }}>Overview</h2>
            <div style={{ display: "flex", gap: "1.5rem" }}>
              <div style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border-color)", padding: "2rem", borderRadius: "8px", flex: 1, textAlign: "center" }}>
                <div style={{ fontSize: "2.5rem", fontWeight: "700", color: "#FCA5A5", marginBottom: "0.5rem" }}>{summary.pending}</div>
                <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", letterSpacing: "0.05em", fontWeight: "600" }}>PENDING MENTIONS</div>
              </div>
              <div style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border-color)", padding: "2rem", borderRadius: "8px", flex: 1, textAlign: "center" }}>
                <div style={{ fontSize: "2.5rem", fontWeight: "700", color: "#6EE7B7", marginBottom: "0.5rem" }}>{summary.approved}</div>
                <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", letterSpacing: "0.05em", fontWeight: "600" }}>APPROVED</div>
              </div>
              <div style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border-color)", padding: "2rem", borderRadius: "8px", flex: 1, textAlign: "center" }}>
                <div style={{ fontSize: "2.5rem", fontWeight: "700", color: "#CBD5E1", marginBottom: "0.5rem" }}>{summary.rejected}</div>
                <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", letterSpacing: "0.05em", fontWeight: "600" }}>DISCARDED</div>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
