"use client";

import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  BarChart3,
  Book,
  Building2,
  Check,
  CheckSquare,
  ChevronDown,
  Clipboard,
  Clock,
  ExternalLink,
  Eye,
  EyeOff,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  MessageSquareDiff,
  MoreVertical,
  Plus,
  Play,
  Settings,
  Sparkles,
  Square,
  Target,
  TrendingUp,
  User,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Funnel,
  FunnelChart,
  LabelList,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Opportunity {
  id: string;
  platform?: string;
  subreddit: string;
  title: string;
  body: string;
  url: string;
  score: number;
  status: string;
  reasons: string[];
  drafts: string[];
  created_at: string;
  posted_reply_url?: string;
  selected_draft_index?: number | null;
  replied_at?: string | null;
  followup_sentiment?: string;
  clicks?: number;
  signups?: number;
  conversion_value?: number;
  next_follow_up_at?: string | null;
  operator_notes?: string;
  feedback_label?: string;
  feedback_note?: string;
}

interface Summary {
  pending: number;
  approved: number;
  rejected: number;
  posted?: number;
  converted?: number;
}

interface Playbook {
  subreddit: string;
  rules_text: string;
  notes: string;
  updated_at: string;
}

interface AuditLog {
  id: number;
  platform?: string;
  opportunity_id: string;
  action: string;
  actor: string;
  note: string;
  created_at: string;
}

interface BotProfile {
  campaign_name: string;
  target_audience: string;
  product_area: string;
  subreddits: string[];
  reddit_keywords: string[];
  twitter_keywords: string[];
  competitors: string[];
  buying_signals: string[];
  forbidden_phrases: string[];
  max_replies_per_community_per_day: number;
  disclosure_policy: string;
  reddit_knowledge_block: string;
  twitter_knowledge_block: string;
  youtube_knowledge_block: string;
  reddit_prompt_template: string;
  twitter_prompt_template: string;
  youtube_prompt_template: string;
  twitter_target_handles: string[];
  twitter_queries: string[];
  youtube_target_channels: string[];
  youtube_queries: string[];
  youtube_keywords: string[];
}

interface EngineRuntimeStatus {
  running: boolean;
  pid: number | null;
  last_returncode: number | null;
  account_id?: string | null;
}

interface RuntimeStatusPayload {
  running: boolean;
  engines?: {
    reddit?: EngineRuntimeStatus;
    twitter?: EngineRuntimeStatus;
    youtube?: EngineRuntimeStatus;
  };
}

interface Account {
  id: string;
  name: string;
  role: string;
}

interface AuthUser {
  id: string;
  email: string;
  display_name?: string;
  current_account_id: string;
}

interface AuthContext {
  user: AuthUser;
  accounts: Account[];
}

interface Analytics {
  total: number;
  stage_counts: Record<string, number>;
  approval_rate: number;
  posted_rate: number;
  reply_rate: number;
  conversion_rate: number;
  clicks: number;
  signups: number;
  pipeline_value: number;
  estimated_time_saved_minutes: number;
  best_channels: [string, number][];
  best_product_areas: [string, number][];
  feedback: Record<string, number>;
  opportunities_by_day: Record<string, number>;
}

type AuditActionFilter = "all" | "approved" | "rejected" | "posted" | "converted";
type ConfigTab = "profile" | "playbooks";
type Platform = "reddit" | "twitter" | "youtube";
type View = "dashboard" | "triage" | "approvals" | "config";

const STAGES = ["new", "qualified", "drafted", "approved", "posted", "replied_back", "converted", "lost", "rejected"];
const FEEDBACK_LABELS = ["good lead", "bad fit", "too promotional", "wrong audience", "competitor mention", "high intent"];

const emptyAnalytics: Analytics = {
  total: 0,
  stage_counts: {},
  approval_rate: 0,
  posted_rate: 0,
  reply_rate: 0,
  conversion_rate: 0,
  clicks: 0,
  signups: 0,
  pipeline_value: 0,
  estimated_time_saved_minutes: 0,
  best_channels: [],
  best_product_areas: [],
  feedback: {},
  opportunities_by_day: {},
};

function displayStage(stage: string) {
  if (stage === "replied_back") return "replied";
  if (stage === "new" || stage === "pending") return "triage";
  return stage.replaceAll("_", " ");
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value || 0);
}

function formatCompact(value: number) {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

function platformLabel(platform: Platform) {
  if (platform === "reddit") return "Reddit";
  if (platform === "twitter") return "Twitter";
  return "YouTube";
}

function platformTargetLabel(platform: Platform) {
  if (platform === "reddit") return "Target Subreddits";
  if (platform === "twitter") return "Target Twitter Handles";
  return "Target YouTube Channels";
}

function platformTargetDescription(platform: Platform) {
  if (platform === "reddit") return "Communities monitored for buying signals.";
  if (platform === "twitter") return "Accounts monitored for relevant posts.";
  return "Channels used to constrain YouTube discovery when configured.";
}

function platformTargetPrefix(platform: Platform) {
  if (platform === "reddit") return "r/";
  if (platform === "twitter") return "@";
  return "@";
}

function platformMention(platform: Platform, value: string) {
  if (platform === "reddit") return `r/${value}`;
  if (platform === "twitter") return `@${value}`;
  return value.startsWith("@") ? value : `@${value}`;
}

export default function Gatekeeper() {
  const [currentView, setCurrentView] = useState<View>("triage");
  const [platform, setPlatform] = useState<Platform>("reddit");
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selectedOppId, setSelectedOppId] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary>({ pending: 0, approved: 0, rejected: 0 });
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [selectedSubreddit, setSelectedSubreddit] = useState<string | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditActionFilter, setAuditActionFilter] = useState<AuditActionFilter>("all");
  const [analytics, setAnalytics] = useState<Analytics>(emptyAnalytics);
  const [configTab, setConfigTab] = useState<ConfigTab>("profile");
  const [profile, setProfile] = useState<BotProfile | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");
  const [configEditing, setConfigEditing] = useState(false);
  const [note, setNote] = useState("");
  const [selectedDraftIndex, setSelectedDraftIndex] = useState(0);
  const [postedReplyUrl, setPostedReplyUrl] = useState("");
  const [nextFollowUpAt, setNextFollowUpAt] = useState("");
  const [outcomeNotes, setOutcomeNotes] = useState("");
  const [feedbackNote, setFeedbackNote] = useState("");
  const [botRunning, setBotRunning] = useState(false);
  const [triageMenuOpen, setTriageMenuOpen] = useState(false);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [engineLoading, setEngineLoading] = useState<string | null>(null);
  const [runtimeMessage, setRuntimeMessage] = useState("");
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusPayload>({
    running: false,
    engines: {
      reddit: { running: false, pid: null, last_returncode: null },
      twitter: { running: false, pid: null, last_returncode: null },
      youtube: { running: false, pid: null, last_returncode: null },
    },
  });
  const [subredditInput, setSubredditInput] = useState("");
  const [twitterHandleInput, setTwitterHandleInput] = useState("");
  const [twitterQueryInput, setTwitterQueryInput] = useState("");
  const [youtubeChannelInput, setYoutubeChannelInput] = useState("");
  const [youtubeQueryInput, setYoutubeQueryInput] = useState("");
  const [subredditSuggestions, setSubredditSuggestions] = useState<string[]>([]);
  const [suggestingKeywords, setSuggestingKeywords] = useState(false);
  const [keywordSuggestions, setKeywordSuggestions] = useState<string[]>([]);
  const [authChecked, setAuthChecked] = useState(false);
  const [auth, setAuth] = useState<AuthContext | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [authEmail, setAuthEmail] = useState("admin@soloa.local");
  const [authPassword, setAuthPassword] = useState("soloa-admin");
  const [authPasswordVisible, setAuthPasswordVisible] = useState(false);
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authAccountName, setAuthAccountName] = useState("New campaign");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [newAccountName, setNewAccountName] = useState("");
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [enginePanelOpen, setEnginePanelOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const activeAccount = useMemo(
    () => auth?.accounts.find((account) => account.id === auth.user.current_account_id) || auth?.accounts[0] || null,
    [auth],
  );

  const activeOpp = useMemo(
    () => opportunities.find((opp) => opp.id === selectedOppId) || null,
    [opportunities, selectedOppId],
  );

  const activeDraft = activeOpp?.drafts?.[selectedDraftIndex] || activeOpp?.drafts?.[0] || "";

  const refreshAuth = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/me");
      if (!res.ok) {
        setAuth(null);
        return;
      }
      const data = await res.json();
      setAuth({ user: data.user, accounts: data.accounts || [] });
    } catch (err) {
      console.error(err);
      setAuth(null);
    } finally {
      setAuthChecked(true);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshAuth();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshAuth]);

  const submitAuth = async (event: React.FormEvent) => {
    event.preventDefault();
    setAuthLoading(true);
    setAuthError("");
    try {
      const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/signup";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: authEmail,
          password: authPassword,
          display_name: authDisplayName,
          account_name: authAccountName,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Authentication failed");
      setAuth({ user: data.user, accounts: data.accounts || [] });
      setCurrentView("triage");
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setAuthLoading(false);
      setAuthChecked(true);
    }
  };

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    setAuth(null);
    setOpportunities([]);
    setProfile(null);
  };

  const switchAccount = async (accountId: string) => {
    if (!accountId || accountId === auth?.user.current_account_id) return;
    const res = await fetch("/api/accounts/current", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_id: accountId }),
    });
    const data = await res.json();
    if (!res.ok) return;
    setAuth({ user: data.user, accounts: data.accounts || [] });
    setSelectedOppId(null);
    setProfile(null);
  };

  const createBusinessAccount = async () => {
    if (!newAccountName.trim()) return;
    setCreatingAccount(true);
    try {
      const res = await fetch("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newAccountName.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setAuth({ user: data.user, accounts: data.accounts || [] });
        setNewAccountName("");
        setSelectedOppId(null);
      }
    } finally {
      setCreatingAccount(false);
    }
  };

  const fetchOpportunities = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ platform });
      if (filter !== "all") params.set("status", filter);
      const res = await fetch(`/api/opportunities?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch opportunities");
      const data = await res.json();
      const rows: Opportunity[] = data.opportunities || [];
      setOpportunities(rows);
      setSummary(data.summary || { pending: 0, approved: 0, rejected: 0 });
      setSelectedOppId((previous) => {
        if (!rows.length) return null;
        if (previous && rows.some((opp) => opp.id === previous)) return previous;
        return rows[0].id;
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filter, platform]);

  const fetchPlaybooks = useCallback(async () => {
    try {
      const res = await fetch(`/api/playbooks?platform=${platform}`);
      if (!res.ok) throw new Error("Failed to fetch playbooks");
      const data = await res.json();
      const rows: Playbook[] = data.playbooks || [];
      setPlaybooks(rows);
      setSelectedSubreddit((previous) => previous || rows[0]?.subreddit || null);
    } catch (err) {
      console.error(err);
    }
  }, [platform]);

  const fetchAuditLogs = useCallback(async () => {
    try {
      const res = await fetch(`/api/audit?platform=${platform}`);
      if (!res.ok) throw new Error("Failed to fetch audit logs");
      const data = await res.json();
      setAuditLogs(data.logs || []);
    } catch (err) {
      console.error(err);
    }
  }, [platform]);

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await fetch(`/api/analytics?platform=${platform}`);
      if (!res.ok) throw new Error("Failed to fetch analytics");
      const data = await res.json();
      setAnalytics(data.analytics || emptyAnalytics);
    } catch (err) {
      console.error(err);
    }
  }, [platform]);

  const fetchRuntimeStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/runtime");
      if (!res.ok) throw new Error("Failed to fetch runtime status");
      const data: RuntimeStatusPayload = await res.json();
      setRuntimeStatus(data);
      setBotRunning(Boolean(data.running));
      setRuntimeMessage("");
    } catch (err) {
      console.error(err);
      setRuntimeMessage("Runtime API unavailable. Ensure backend is running on 127.0.0.1:5050.");
    }
  }, []);

  const fetchProfile = useCallback(async () => {
    try {
      const res = await fetch("/api/profile");
      if (!res.ok) throw new Error("Failed to fetch profile");
      const data = await res.json();
      setProfile(data);
      setConfigEditing(false);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    if (!auth) return;
    const timer = window.setTimeout(() => {
      if (currentView === "triage") {
        void fetchOpportunities();
        void fetchRuntimeStatus();
      }
      if (currentView === "dashboard") void fetchAnalytics();
      if (currentView === "config") {
        void fetchPlaybooks();
        void fetchProfile();
      }
      if (currentView === "approvals") void fetchAuditLogs();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [auth, currentView, fetchAnalytics, fetchAuditLogs, fetchOpportunities, fetchPlaybooks, fetchProfile, fetchRuntimeStatus]);

  useEffect(() => {
    if (!auth || currentView !== "triage") return;
    const runtimeTimer = window.setInterval(fetchRuntimeStatus, 5000);
    const dataTimer = botRunning ? window.setInterval(fetchOpportunities, 10000) : null;
    return () => {
      window.clearInterval(runtimeTimer);
      if (dataTimer) window.clearInterval(dataTimer);
    };
  }, [auth, botRunning, currentView, fetchOpportunities, fetchRuntimeStatus]);

  // Close dropdown panels on outside click
  useEffect(() => {
    const handler = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (enginePanelOpen && !target.closest(".engine-trigger-wrapper")) {
        setEnginePanelOpen(false);
      }
      if (userMenuOpen && !target.closest(".user-trigger-wrapper")) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [enginePanelOpen, userMenuOpen]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSelectedDraftIndex(activeOpp?.selected_draft_index ?? 0);
      setPostedReplyUrl(activeOpp?.posted_reply_url || "");
      setNextFollowUpAt(activeOpp?.next_follow_up_at || "");
      setOutcomeNotes(activeOpp?.operator_notes || "");
      setFeedbackNote(activeOpp?.feedback_note || "");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeOpp]);

  useEffect(() => {
    if (platform !== "reddit" || subredditInput.length < 2) {
      window.setTimeout(() => setSubredditSuggestions([]), 0);
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const res = await fetch(`/api/search_subreddits?q=${encodeURIComponent(subredditInput)}`);
        const data = await res.json();
        setSubredditSuggestions(data.results || []);
      } catch {
        setSubredditSuggestions([]);
      }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [platform, subredditInput]);

  const saveProfile = async () => {
    if (!profile) return;
    setSavingProfile(true);
    setProfileMessage("");
    try {
      const res = await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      setProfileMessage(res.ok ? "Profile saved. Running engines are restarting." : "Error saving profile.");
      if (res.ok) setConfigEditing(false);
    } catch (err) {
      console.error(err);
      setProfileMessage("Error saving profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const generateKeywords = async () => {
    if (!configEditing) return;
    setSuggestingKeywords(true);
    try {
      const res = await fetch(`/api/suggest_keywords?platform=${platform}`, { method: "POST" });
      const data = await res.json();
      setKeywordSuggestions(data.suggestions || []);
    } catch (err) {
      console.error(err);
    } finally {
      setSuggestingKeywords(false);
    }
  };

  const toggleRuntime = async () => {
    setRuntimeLoading(true);
    setRuntimeMessage("");
    try {
      const endpoint = botRunning ? "/api/runtime/stop" : "/api/runtime/start";
      const res = await fetch(endpoint, { method: "POST" });
      if (!res.ok) {
        let reason = "Failed to change runtime state";
        try {
          const payload = await res.json();
          if (payload?.error) reason = String(payload.error);
        } catch {
          // Keep default reason when response body is not JSON.
        }
        throw new Error(reason);
      }
      await fetchRuntimeStatus();
      void fetchOpportunities();
    } catch (err) {
      console.error(err);
      setRuntimeMessage(err instanceof Error ? err.message : "Failed to change runtime state");
    } finally {
      setRuntimeLoading(false);
    }
  };

  const toggleEngine = async (engine: Platform) => {
    setEngineLoading(engine);
    setRuntimeMessage("");
    try {
      const isRunning = Boolean(runtimeStatus.engines?.[engine]?.running);
      const endpoint = isRunning ? `/api/runtime/stop?engine=${engine}` : `/api/runtime/start?engine=${engine}`;
      const res = await fetch(endpoint, { method: "POST" });
      if (!res.ok) {
        let reason = `Failed to change ${engine} runtime state`;
        try {
          const payload = await res.json();
          if (payload?.error) reason = String(payload.error);
        } catch {
          // Keep default reason when response body is not JSON.
        }
        throw new Error(reason);
      }
      await fetchRuntimeStatus();
      void fetchOpportunities();
    } catch (err) {
      console.error(err);
      setRuntimeMessage(err instanceof Error ? err.message : `Failed to change ${engine} runtime state`);
    } finally {
      setEngineLoading(null);
    }
  };

  const setOpportunityStatus = async (id: string, status: string, statusNote = note) => {
    const endpoint = status === "approved" || status === "rejected"
      ? `/api/opportunity/${id}/${status === "approved" ? "approve" : "reject"}`
      : `/api/opportunity/${id}/status`;
    const body = status === "approved" || status === "rejected" ? { note: statusNote } : { status, note: statusNote };
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed to update status");
      setNote("");
      await fetchOpportunities();
      void fetchAnalytics();
    } catch (err) {
      console.error(err);
    }
  };

  const saveOutcome = async (status?: string) => {
    if (!activeOpp) return;
    try {
      const res = await fetch(`/api/opportunity/${activeOpp.id}/outcome`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          posted_reply_url: postedReplyUrl,
          selected_draft_index: selectedDraftIndex,
          next_follow_up_at: nextFollowUpAt,
          operator_notes: outcomeNotes,
          status,
        }),
      });
      if (!res.ok) throw new Error("Failed to save outcome");
      await fetchOpportunities();
      void fetchAnalytics();
    } catch (err) {
      console.error(err);
    }
  };

  const saveFeedback = async (label: string) => {
    if (!activeOpp) return;
    try {
      const res = await fetch(`/api/opportunity/${activeOpp.id}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label, note: feedbackNote }),
      });
      if (!res.ok) throw new Error("Failed to save feedback");
      await fetchOpportunities();
    } catch (err) {
      console.error(err);
    }
  };

  const copyDraft = async () => {
    if (!activeDraft) return;
    await navigator.clipboard.writeText(activeDraft);
    if (activeOpp && activeOpp.status === "new") {
      await setOpportunityStatus(activeOpp.id, "drafted", "Draft copied for posting");
    }
  };

  const handleDiscardAll = async () => {
    try {
      const res = await fetch(`/api/opportunities/reject_all?platform=${platform}`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to discard all");
      setTriageMenuOpen(false);
      await fetchOpportunities();
    } catch (err) {
      console.error(err);
    }
  };

  const filteredAuditLogs = auditLogs.filter((log) => {
    if (auditActionFilter === "all") return true;
    if (auditActionFilter === "posted") return log.action === "posted" || log.action === "outcome_updated";
    return log.action === auditActionFilter;
  });

  const currentStageCount = analytics.stage_counts[filter] || (filter === "pending" ? summary.pending : 0);
  const stageEntries = Object.entries(analytics.stage_counts || {}).filter(([, value]) => value > 0);
  const stageChartData = STAGES.map((stage) => ({
    stage: displayStage(stage),
    value: analytics.stage_counts?.[stage] || 0,
  })).filter((item) => item.value > 0);
  const trendChartData = Object.entries(analytics.opportunities_by_day || {})
    .sort(([first], [second]) => first.localeCompare(second))
    .map(([date, value]) => ({
      date: new Date(`${date}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      value,
    }));
  const channelChartData = analytics.best_channels.map(([name, value]) => ({ name, value })).slice(0, 6);
  const productAreaData = analytics.best_product_areas.map(([name, value]) => ({ name, value })).slice(0, 5);
  const feedbackData = Object.entries(analytics.feedback || {}).map(([name, value]) => ({ name, value }));
  const approvedCount = analytics.stage_counts.approved || 0;
  const postedCount = analytics.stage_counts.posted || 0;
  const repliedCount = analytics.stage_counts.replied_back || 0;
  const convertedCount = analytics.stage_counts.converted || 0;
  const funnelData = [
    { name: "Captured", value: analytics.total || 0, fill: "#38BDF8" },
    { name: "Approved", value: approvedCount, fill: "#60A5FA" },
    { name: "Posted", value: postedCount, fill: "#A78BFA" },
    { name: "Replied", value: repliedCount, fill: "#F59E0B" },
    { name: "Converted", value: convertedCount, fill: "#10B981" },
  ].filter((item) => item.value > 0);
  const topChannel = analytics.best_channels[0]?.[0] || "No channel yet";
  const nextBestAction = analytics.total === 0
    ? "Start the engine to collect opportunities."
    : analytics.stage_counts.new || analytics.stage_counts.pending
      ? "Review triage and qualify the strongest leads."
      : approvedCount > postedCount
        ? "Post approved replies to unlock response data."
        : postedCount > repliedCount
          ? "Track replies and schedule follow-ups."
          : "Keep feeding the pipeline with qualified mentions.";

  if (!authChecked) {
    return <div className="auth-shell"><div className="auth-card"><div className="auth-title">Loading workspace</div></div></div>;
  }

  if (!auth) {
    return (
      <AuthScreen
        mode={authMode}
        email={authEmail}
        password={authPassword}
        displayName={authDisplayName}
        accountName={authAccountName}
        error={authError}
        loading={authLoading}
        passwordVisible={authPasswordVisible}
        onModeChange={(mode) => {
          setAuthMode(mode);
          setAuthError("");
          if (mode === "login") {
            setAuthEmail("admin@soloa.local");
            setAuthPassword("soloa-admin");
            setAuthAccountName("Default workspace");
          } else {
            setAuthEmail("");
            setAuthPassword("");
            setAuthAccountName("");
          }
        }}
        onEmailChange={setAuthEmail}
        onPasswordChange={setAuthPassword}
        onPasswordVisibleChange={setAuthPasswordVisible}
        onDisplayNameChange={setAuthDisplayName}
        onAccountNameChange={setAuthAccountName}
        onSubmit={submitAuth}
      />
    );
  }

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">{activeAccount?.name || "Workspace"}</div>
          <div className="sidebar-subtitle">{platformLabel(platform).toUpperCase()} ENGINE</div>
        </div>

        <nav className="sidebar-nav">
          <button className={`nav-item ${currentView === "dashboard" ? "active" : ""}`} onClick={() => setCurrentView("dashboard")}>
            <LayoutDashboard className="nav-icon" /> DASHBOARD
          </button>
          <button className={`nav-item ${currentView === "triage" ? "active" : ""}`} onClick={() => setCurrentView("triage")}>
            <MessageSquareDiff className="nav-icon" /> MENTIONS & PIPELINE
          </button>
          <button className={`nav-item ${currentView === "approvals" ? "active" : ""}`} onClick={() => setCurrentView("approvals")}>
            <CheckSquare className="nav-icon" /> AUDIT
          </button>
          <button className={`nav-item ${currentView === "config" ? "active" : ""}`} onClick={() => setCurrentView("config")}>
            <Settings className="nav-icon" /> CONFIGURATION
          </button>
        </nav>

        <div className="sidebar-footer">
          <button className="nav-item" onClick={() => window.open("/api/audit/export?platform=" + platform, "_blank")}>
            <Book className="nav-icon" /> EXPORT AUDIT
          </button>
          <button className="nav-item" onClick={logout}>
            <LogOut className="nav-icon" /> LOG OUT
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          {/* ── Left: contextual page title ── */}
          <div className="topbar-left">
            <h1 className="topbar-title">
              {currentView === "dashboard" && "Dashboard"}
              {currentView === "triage" && "Mentions & Pipeline"}
              {currentView === "approvals" && "Audit Trail"}
              {currentView === "config" && "Configuration"}
            </h1>
            <span className="topbar-breadcrumb">{platformLabel(platform)}</span>
          </div>

          {/* ── Center: platform segmented control ── */}
          <div className="platform-switcher">
            {(["reddit", "twitter", "youtube"] as const).map((p) => (
              <button
                key={p}
                className={`platform-seg ${platform === p ? "active" : ""}`}
                onClick={() => setPlatform(p)}
              >
                <span className={`platform-dot ${p === platform && runtimeStatus.engines?.[p]?.running ? "live" : ""}`} />
                {platformLabel(p)}
              </button>
            ))}
          </div>

          {/* ── Right: engine status + user ── */}
          <div className="topbar-right">
            {/* Engine control */}
            <div className="engine-trigger-wrapper">
              <button
                className={`engine-trigger ${botRunning ? "live" : ""}`}
                onClick={() => setEnginePanelOpen((prev) => !prev)}
              >
                <Zap size={14} />
                <span>{botRunning ? "Engines running" : "Engines off"}</span>
                <ChevronDown size={14} className={`engine-chevron ${enginePanelOpen ? "open" : ""}`} />
              </button>

              {enginePanelOpen && (
                <div className="engine-panel">
                  <div className="engine-panel-header">
                    <span className="engine-panel-title">Engine Control</span>
                    <button
                      className={`engine-master-btn ${botRunning ? "stop" : "start"}`}
                      onClick={() => { void toggleRuntime(); }}
                      disabled={runtimeLoading}
                    >
                      {runtimeLoading ? "..." : botRunning ? "Stop all" : "Start all"}
                    </button>
                  </div>
                  <div className="engine-panel-list">
                    {(["reddit", "twitter", "youtube"] as const).map((engine) => {
                      const isOn = Boolean(runtimeStatus.engines?.[engine]?.running);
                      return (
                        <div key={engine} className="engine-row">
                          <div className="engine-row-info">
                            <span className={`engine-row-dot ${isOn ? "on" : ""}`} />
                            <span className="engine-row-name">{platformLabel(engine)}</span>
                          </div>
                          <button
                            className={`engine-row-btn ${isOn ? "stop" : "start"}`}
                            onClick={() => void toggleEngine(engine)}
                            disabled={runtimeLoading || engineLoading !== null}
                          >
                            {engineLoading === engine
                              ? "..."
                              : isOn
                                ? <><Square size={10} fill="currentColor" /> Stop</>
                                : <><Play size={10} fill="currentColor" /> Start</>
                            }
                          </button>
                        </div>
                      );
                    })}
                  </div>
                  {runtimeMessage && <div className="engine-panel-msg">{runtimeMessage}</div>}
                </div>
              )}
            </div>

            <div className="topbar-divider" />

            {/* User / account area */}
            <div className="user-trigger-wrapper">
              <button className="user-trigger" onClick={() => setUserMenuOpen((prev) => !prev)}>
                <div className="user-avatar-ring">
                  <User size={14} />
                </div>
                <div className="user-trigger-text">
                  <span className="user-trigger-name">{auth.user.display_name || auth.user.email.split("@")[0]}</span>
                  <span className="user-trigger-account">{activeAccount?.name || "—"}</span>
                </div>
                <ChevronDown size={14} className={`user-chevron ${userMenuOpen ? "open" : ""}`} />
              </button>

              {userMenuOpen && (
                <div className="user-panel">
                  <div className="user-panel-section">
                    <span className="user-panel-label">Workspace</span>
                    {auth.accounts.map((account) => (
                      <button
                        key={account.id}
                        className={`user-panel-item ${account.id === auth.user.current_account_id ? "active" : ""}`}
                        onClick={() => { void switchAccount(account.id); setUserMenuOpen(false); }}
                      >
                        <Building2 size={14} />
                        {account.name}
                        {account.id === auth.user.current_account_id && <Check size={14} className="user-panel-check" />}
                      </button>
                    ))}
                    <div className="user-panel-create">
                      <input
                        className="user-panel-create-input"
                        placeholder="New workspace name..."
                        value={newAccountName}
                        onChange={(event) => setNewAccountName(event.target.value)}
                        onKeyDown={(event) => { if (event.key === "Enter") { void createBusinessAccount(); setUserMenuOpen(false); } }}
                      />
                      <button
                        className="user-panel-create-btn"
                        onClick={() => { void createBusinessAccount(); setUserMenuOpen(false); }}
                        disabled={creatingAccount || !newAccountName.trim()}
                      >
                        <Plus size={14} />
                      </button>
                    </div>
                  </div>
                  <div className="user-panel-divider" />
                  <button className="user-panel-item danger" onClick={() => { void logout(); setUserMenuOpen(false); }}>
                    <LogOut size={14} /> Log out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {currentView === "dashboard" && (
          <div className="scroll-container dashboard-surface">
            <section className="growth-hero">
              <div>
                <div className="dashboard-eyebrow">Growth Overview</div>
                <h2 className="growth-title">{platformLabel(platform)} performance</h2>
                <p className="growth-subtitle">Pipeline health, replies, conversions, and the channels producing results.</p>
              </div>
              <div className="growth-hero-actions">
                <div className="growth-chip">
                  <Target size={14} />
                  Best: {topChannel}
                </div>
                <div className="growth-chip">
                  <Sparkles size={14} />
                  {nextBestAction}
                </div>
              </div>
            </section>

            <div className="metric-grid growth-metrics">
              <Metric icon={<TrendingUp size={18} />} label="Opportunities" value={formatCompact(analytics.total)} helper="Total found" tone="blue" />
              <Metric icon={<CheckSquare size={18} />} label="Approval Rate" value={`${analytics.approval_rate}%`} helper="Qualified leads" tone="green" />
              <Metric icon={<MessageCircle size={18} />} label="Reply Rate" value={`${analytics.reply_rate}%`} helper="Replies received" tone="amber" />
              <Metric icon={<Target size={18} />} label="Conversion Rate" value={`${analytics.conversion_rate}%`} helper={`${analytics.signups} signups`} tone="purple" />
              <Metric icon={<ExternalLink size={18} />} label="Clicks" value={formatCompact(analytics.clicks)} helper="Tracked clicks" tone="cyan" />
              <Metric icon={<BarChart3 size={18} />} label="Pipeline Value" value={formatMoney(analytics.pipeline_value)} helper="Estimated value" tone="orange" />
              <Metric icon={<Clock size={18} />} label="Time Saved" value={`${analytics.estimated_time_saved_minutes}m`} helper="Estimated" tone="slate" />
            </div>

            <div className="dashboard-grid dashboard-grid-primary">
              <ChartPanel title="Opportunity Momentum" description="Daily captured buying signals">
                {trendChartData.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={trendChartData} margin={{ top: 8, right: 18, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="opportunityTrend" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.45} />
                          <stop offset="95%" stopColor="#38BDF8" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" vertical={false} />
                      <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} />
                      <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} width={28} allowDecimals={false} />
                      <Tooltip content={<DashboardTooltip />} />
                      <Area type="monotone" dataKey="value" stroke="#38BDF8" strokeWidth={3} fill="url(#opportunityTrend)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : <ChartEmpty label="No daily trend yet." />}
              </ChartPanel>

              <ChartPanel title="Conversion Funnel" description="From signal capture to signup">
                {funnelData.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <FunnelChart>
                      <Tooltip content={<DashboardTooltip />} />
                      <Funnel dataKey="value" data={funnelData} isAnimationActive>
                        <LabelList position="right" fill="#E2E8F0" stroke="none" dataKey="name" fontSize={12} />
                      </Funnel>
                    </FunnelChart>
                  </ResponsiveContainer>
                ) : <ChartEmpty label="No funnel movement yet." />}
              </ChartPanel>
            </div>

            <div className="dashboard-grid dashboard-grid-secondary">
              <ChartPanel title="Pipeline Mix" description="Where leads sit right now">
                {stageChartData.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie data={stageChartData} dataKey="value" nameKey="stage" innerRadius={58} outerRadius={90} paddingAngle={3}>
                        {stageChartData.map((entry, index) => (
                          <Cell key={entry.stage} fill={["#38BDF8", "#60A5FA", "#A78BFA", "#F59E0B", "#10B981", "#EF4444", "#64748B"][index % 7]} />
                        ))}
                      </Pie>
                      <Tooltip content={<DashboardTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <ChartEmpty label="No stage data yet." />}
              </ChartPanel>

              <ChartPanel title="Best Channels" description="Communities and accounts producing leads">
                {channelChartData.length ? <HorizontalBars data={channelChartData} color="#60A5FA" /> : <ChartEmpty label="No channel data yet." />}
              </ChartPanel>

              <ChartPanel title="Product Areas" description="Demand clusters worth pursuing">
                {productAreaData.length ? <HorizontalBars data={productAreaData} color="#10B981" /> : <ChartEmpty label="No product area data yet." />}
              </ChartPanel>
            </div>

            <div className="dashboard-grid dashboard-grid-secondary">
              <InsightList title="Stage Detail" rows={stageEntries} />
              <InsightList title="Lead Feedback" rows={feedbackData.map(({ name, value }) => [name, value])} />
            </div>
          </div>
        )}

        {currentView === "triage" && (
          <>
            <div className="content-header">
              <div className="filters">
                <button className={`filter-btn ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>
                  <LayoutDashboard size={14} /> ALL
                </button>
                <button className={`filter-btn ${filter === "pending" ? "active" : ""}`} onClick={() => setFilter("pending")}>
                  <div className="filter-dot" /> TRIAGE ({summary.pending})
                </button>
                {STAGES.filter((stage) => stage !== "new").map((stage) => (
                  <button key={stage} className={`filter-btn ${filter === stage ? "active" : ""}`} onClick={() => setFilter(stage)}>
                    {displayStage(stage).toUpperCase()} {filter === stage ? `(${currentStageCount})` : ""}
                  </button>
                ))}
              </div>
              <div style={{ position: "relative" }}>
                <button onClick={() => setTriageMenuOpen(!triageMenuOpen)} style={{ color: "var(--text-muted)", padding: "4px" }}>
                  <MoreVertical size={16} />
                </button>
                {triageMenuOpen && (
                  <div className="popover-menu">
                    <button onClick={handleDiscardAll} className="popover-danger"><X size={14} /> Discard Triage</button>
                  </div>
                )}
              </div>
            </div>

            <div className="triage-layout">
              <div className="inbox-list">
                {loading ? (
                  <div className="empty-list">Loading...</div>
                ) : opportunities.length === 0 ? (
                  <div className="empty-list">No mentions found.</div>
                ) : (
                  opportunities.map((opp) => (
                    <button key={opp.id} className={`list-item ${selectedOppId === opp.id ? "active" : ""}`} onClick={() => setSelectedOppId(opp.id)}>
                      <div className="list-item-header">
                        <span className="list-item-meta">{platformMention(platform, opp.subreddit)}</span>
                        <span className={`card-pill ${opp.status === "rejected" ? "rejected" : opp.status === "approved" || opp.status === "posted" || opp.status === "converted" ? "approved" : "triage"}`}>
                          {displayStage(opp.status)}
                        </span>
                      </div>
                      <div className="list-item-title">{opp.title}</div>
                      <div className="list-item-preview">{opp.body}</div>
                    </button>
                  ))
                )}
              </div>

              <div className="inbox-detail">
                {!activeOpp ? (
                  <div className="empty-state">Select a mention from the list to review</div>
                ) : (
                  <>
                    <div className="detail-scroll-area">
                      <div className="detail-header-meta">
                        <span className="detail-subreddit">{platformMention(platform, activeOpp.subreddit)}</span>
                        <span className="detail-score">Score: {activeOpp.score}</span>
                        <span className="detail-score">Stage: {displayStage(activeOpp.status)}</span>
                        <a href={activeOpp.url} target="_blank" rel="noopener noreferrer" className="detail-link">
                          Open source <ArrowUpRight size={14} style={{ marginLeft: "4px" }} />
                        </a>
                      </div>

                      <h1 className="detail-title">{activeOpp.title}</h1>
                      <div className="detail-body">{activeOpp.body || "No body text."}</div>

                      <section className="ai-insight-box">
                        <div className="insight-header"><Sparkles size={14} /> MODEL REASONING</div>
                        <div className="insight-content">
                          {activeOpp.reasons?.length ? activeOpp.reasons.map((reason, index) => <div key={index} className="reason-row">- {reason}</div>) : "No reasoning available."}
                        </div>
                      </section>

                      <section className="ai-insight-box" style={{ background: "transparent" }}>
                        <div className="insight-header"><MessageCircle size={14} /> POSTING ASSISTANT</div>
                        <div className="insight-content">
                          <div className="draft-grid">
                            {activeOpp.drafts.map((draft, index) => (
                              <button key={index} className={`draft-item selectable ${selectedDraftIndex === index ? "selected" : ""}`} onClick={() => setSelectedDraftIndex(index)}>
                                <strong>Draft {index + 1}</strong>
                                <span>{draft}</span>
                              </button>
                            ))}
                          </div>
                          <div className="posting-actions">
                            <button className="btn btn-open" onClick={copyDraft}><Clipboard size={16} /> COPY DRAFT</button>
                            <a className="btn btn-open" href={activeOpp.url} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} /> OPEN THREAD</a>
                            <button className="btn btn-approve" onClick={() => saveOutcome("posted")}><Check size={16} /> MARK POSTED</button>
                          </div>
                        </div>
                      </section>

                      <section className="ai-insight-box">
                        <div className="insight-header"><BarChart3 size={14} /> OUTCOME TRACKING</div>
                        <div className="outcome-grid">
                          <input className="action-input" placeholder="Posted reply URL" value={postedReplyUrl} onChange={(e) => setPostedReplyUrl(e.target.value)} />
                          <input className="action-input" placeholder="Next follow-up date/time" value={nextFollowUpAt} onChange={(e) => setNextFollowUpAt(e.target.value)} />
                          <input className="action-input" placeholder="Operator notes" value={outcomeNotes} onChange={(e) => setOutcomeNotes(e.target.value)} />
                          <button className="btn btn-open" onClick={() => saveOutcome()}>SAVE OUTCOME</button>
                        </div>
                      </section>

                      <section className="ai-insight-box">
                        <div className="insight-header"><CheckSquare size={14} /> LEAD FEEDBACK</div>
                        <div className="tags-wrapper" style={{ marginBottom: "0.75rem" }}>
                          {FEEDBACK_LABELS.map((label) => (
                            <button key={label} className={`tag-pill feedback-pill ${activeOpp.feedback_label === label ? "selected" : ""}`} onClick={() => saveFeedback(label)}>
                              {label}
                            </button>
                          ))}
                        </div>
                        <input className="action-input" placeholder="Feedback note" value={feedbackNote} onChange={(e) => setFeedbackNote(e.target.value)} />
                      </section>
                    </div>

                    <div className="detail-action-bar">
                      <input
                        type="text"
                        className="action-input"
                        placeholder="Decision note"
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") void setOpportunityStatus(activeOpp.id, "approved");
                        }}
                      />
                      <button className="btn btn-discard" onClick={() => setOpportunityStatus(activeOpp.id, "rejected")}><X size={16} /> DISCARD</button>
                      <button className="btn btn-open" onClick={() => setOpportunityStatus(activeOpp.id, "qualified")}>QUALIFY</button>
                      <button className="btn btn-approve" onClick={() => setOpportunityStatus(activeOpp.id, "approved")}><Check size={16} /> APPROVE</button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </>
        )}

        {currentView === "approvals" && (
          <div className="scroll-container">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
              <h2 style={{ fontSize: "1.2rem" }}>Audit Log</h2>
              <div className="filters">
                {(["all", "approved", "rejected", "posted", "converted"] as AuditActionFilter[]).map((action) => (
                  <button key={action} className={`filter-btn ${auditActionFilter === action ? "active" : ""}`} onClick={() => setAuditActionFilter(action)}>
                    {action.toUpperCase()}
                  </button>
                ))}
                <a className="btn btn-open" href={`/api/audit/export?platform=${platform}`} target="_blank" rel="noopener noreferrer">EXPORT CSV</a>
              </div>
            </div>
            <table className="data-table">
              <thead>
                <tr><th>ID</th><th>OPPORTUNITY</th><th>ACTION</th><th>ACTOR</th><th>NOTE</th><th>DATE</th></tr>
              </thead>
              <tbody>
                {filteredAuditLogs.length === 0 ? (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-muted)", padding: "3rem" }}>No logs found.</td></tr>
                ) : filteredAuditLogs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.id}</td>
                    <td>{log.opportunity_id}</td>
                    <td><span className={`card-pill ${log.action === "rejected" ? "rejected" : "approved"}`}>{log.action}</span></td>
                    <td>{log.actor}</td>
                    <td>{log.note || "-"}</td>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {currentView === "config" && (
          <>
            <div className="content-header">
              <div className="filters">
                <button className={`filter-btn ${configTab === "profile" ? "active" : ""}`} onClick={() => setConfigTab("profile")}>BOT PROFILE</button>
                <button className={`filter-btn ${configTab === "playbooks" ? "active" : ""}`} onClick={() => setConfigTab("playbooks")}>PLAYBOOKS</button>
              </div>
              {configTab === "profile" && profile && (
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {!configEditing ? (
                    <button className="btn btn-open" onClick={() => setConfigEditing(true)}>EDIT CONFIGURATION</button>
                  ) : (
                    <button className="btn btn-discard" onClick={() => void fetchProfile()} disabled={savingProfile}>CANCEL</button>
                  )}
                </div>
              )}
            </div>

            {configTab === "profile" && profile && (
              <div className="scroll-container" style={{ paddingBottom: "100px" }}>
                <h2 style={{ fontSize: "1.2rem", marginBottom: "2rem" }}>Campaign Profile</h2>
                <div className="profile-grid">
                  <div className="profile-column" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                    <div className="profile-card">
                      <div>
                        <div className="profile-card-title">Campaign Strategy</div>
                        <div className="profile-card-desc">Defines the customer segment, product angle, and compliance posture for this monitoring run.</div>
                      </div>
                      <input className="action-input" placeholder="Campaign name" value={profile.campaign_name} disabled={!configEditing} onChange={(event) => setProfile({ ...profile, campaign_name: event.target.value })} />
                      <input className="action-input" placeholder="Target audience" value={profile.target_audience} disabled={!configEditing} onChange={(event) => setProfile({ ...profile, target_audience: event.target.value })} />
                      <input className="action-input" placeholder="Product area" value={profile.product_area} disabled={!configEditing} onChange={(event) => setProfile({ ...profile, product_area: event.target.value })} />
                      <input
                        className="action-input"
                        placeholder="Max replies per community per day"
                        type="number"
                        min={1}
                        value={profile.max_replies_per_community_per_day}
                        disabled={!configEditing}
                        onChange={(event) => setProfile({ ...profile, max_replies_per_community_per_day: Number(event.target.value || 1) })}
                      />
                      <textarea
                        className="action-input"
                        placeholder="Disclosure policy"
                        value={profile.disclosure_policy}
                        disabled={!configEditing}
                        onChange={(event) => setProfile({ ...profile, disclosure_policy: event.target.value })}
                        style={{ minHeight: "80px", resize: "vertical" }}
                      />
                    </div>

                    <TagEditor
                      title={platformTargetLabel(platform)}
                      description={platformTargetDescription(platform)}
                      tags={platform === "reddit" ? profile.subreddits : platform === "twitter" ? profile.twitter_target_handles : profile.youtube_target_channels}
                      disabled={!configEditing}
                      prefix={platformTargetPrefix(platform)}
                      inputValue={platform === "reddit" ? subredditInput : platform === "twitter" ? twitterHandleInput : youtubeChannelInput}
                      placeholder={platform === "reddit" ? "Search subreddit..." : platform === "twitter" ? "Add handle and press Enter..." : "Add channel name or ID and press Enter..."}
                      onInputChange={platform === "reddit" ? setSubredditInput : platform === "twitter" ? setTwitterHandleInput : setYoutubeChannelInput}
                      suggestions={platform === "reddit" ? subredditSuggestions : []}
                      onAdd={(value) => {
                        const normalized = platform === "reddit" ? value.trim() : value.trim().replace(/^@+/, "").toLowerCase();
                        if (!normalized) return;
                        if (platform === "reddit" && !profile.subreddits.includes(normalized)) setProfile({ ...profile, subreddits: [...profile.subreddits, normalized] });
                        if (platform === "twitter" && !profile.twitter_target_handles.includes(normalized)) setProfile({ ...profile, twitter_target_handles: [...profile.twitter_target_handles, normalized] });
                        if (platform === "youtube" && !profile.youtube_target_channels.includes(normalized)) setProfile({ ...profile, youtube_target_channels: [...profile.youtube_target_channels, normalized] });
                        setSubredditInput("");
                        setTwitterHandleInput("");
                        setYoutubeChannelInput("");
                        setSubredditSuggestions([]);
                      }}
                      onRemove={(index) => {
                        if (platform === "reddit") setProfile({ ...profile, subreddits: profile.subreddits.filter((_, idx) => idx !== index) });
                        else if (platform === "twitter") setProfile({ ...profile, twitter_target_handles: profile.twitter_target_handles.filter((_, idx) => idx !== index) });
                        else setProfile({ ...profile, youtube_target_channels: profile.youtube_target_channels.filter((_, idx) => idx !== index) });
                      }}
                    />

                    <TagEditor
                      title="Competitors And Alternatives"
                      description="Names that indicate switcher intent or comparison conversations."
                      tags={profile.competitors}
                      disabled={!configEditing}
                      inputValue=""
                      placeholder="Add competitor and press Enter..."
                      onInputChange={() => undefined}
                      onAdd={(value) => {
                        const normalized = value.trim();
                        if (normalized && !profile.competitors.includes(normalized)) setProfile({ ...profile, competitors: [...profile.competitors, normalized] });
                      }}
                      onRemove={(index) => setProfile({ ...profile, competitors: profile.competitors.filter((_, idx) => idx !== index) })}
                    />

                    <TagEditor
                      title="Buying Signals"
                      description="Patterns such as looking for, switching from, or too expensive."
                      tags={profile.buying_signals}
                      disabled={!configEditing}
                      inputValue=""
                      placeholder="Add signal and press Enter..."
                      onInputChange={() => undefined}
                      onAdd={(value) => {
                        const normalized = value.trim().toLowerCase();
                        if (normalized && !profile.buying_signals.includes(normalized)) setProfile({ ...profile, buying_signals: [...profile.buying_signals, normalized] });
                      }}
                      onRemove={(index) => setProfile({ ...profile, buying_signals: profile.buying_signals.filter((_, idx) => idx !== index) })}
                    />

                    {platform !== "reddit" && (
                      <TagEditor
                        title={platform === "twitter" ? "Twitter Buying-Signal Queries" : "YouTube Search Queries"}
                        description="Configured queries now feed the active collector."
                        tags={platform === "twitter" ? profile.twitter_queries : profile.youtube_queries}
                        disabled={!configEditing}
                        inputValue={platform === "twitter" ? twitterQueryInput : youtubeQueryInput}
                        placeholder="Add query and press Enter..."
                        onInputChange={platform === "twitter" ? setTwitterQueryInput : setYoutubeQueryInput}
                        onAdd={(value) => {
                          const normalized = value.trim().toLowerCase();
                          if (platform === "twitter" && normalized && !profile.twitter_queries.includes(normalized)) setProfile({ ...profile, twitter_queries: [...profile.twitter_queries, normalized] });
                          if (platform === "youtube" && normalized && !profile.youtube_queries.includes(normalized)) setProfile({ ...profile, youtube_queries: [...profile.youtube_queries, normalized] });
                          if (platform === "twitter") setTwitterQueryInput("");
                          else setYoutubeQueryInput("");
                        }}
                        onRemove={(index) => {
                          if (platform === "twitter") setProfile({ ...profile, twitter_queries: profile.twitter_queries.filter((_, idx) => idx !== index) });
                          else setProfile({ ...profile, youtube_queries: profile.youtube_queries.filter((_, idx) => idx !== index) });
                        }}
                      />
                    )}

                    <TagEditor
                      title="Forbidden Phrases"
                      description="Compliance guardrails for words or CTAs operators should avoid."
                      tags={profile.forbidden_phrases}
                      disabled={!configEditing}
                      inputValue=""
                      placeholder="Add phrase and press Enter..."
                      onInputChange={() => undefined}
                      onAdd={(value) => {
                        const normalized = value.trim().toLowerCase();
                        if (normalized && !profile.forbidden_phrases.includes(normalized)) setProfile({ ...profile, forbidden_phrases: [...profile.forbidden_phrases, normalized] });
                      }}
                      onRemove={(index) => setProfile({ ...profile, forbidden_phrases: profile.forbidden_phrases.filter((_, idx) => idx !== index) })}
                    />

                    <TagEditor
                      title={platform === "reddit" ? "Reddit Discovery Signals" : "Pain Keywords"}
                      description={platform === "reddit" ? "Used only to prefilter posts before AI relevance review." : "Phrases that signal frustration, search intent, or readiness to switch."}
                      tags={platform === "reddit" ? profile.reddit_keywords : platform === "twitter" ? profile.twitter_keywords : profile.youtube_keywords}
                      disabled={!configEditing}
                      inputValue=""
                      placeholder={platform === "reddit" ? "Add discovery signal and press Enter..." : "Add keyword and press Enter..."}
                      suggestions={keywordSuggestions}
                      onInputChange={() => undefined}
                      onAdd={(value) => {
                        const normalized = value.trim();
                        if (!normalized) return;
                        if (platform === "reddit" && !profile.reddit_keywords.includes(normalized)) setProfile({ ...profile, reddit_keywords: [...profile.reddit_keywords, normalized] });
                        if (platform === "twitter" && !profile.twitter_keywords.includes(normalized)) setProfile({ ...profile, twitter_keywords: [...profile.twitter_keywords, normalized] });
                        if (platform === "youtube" && !profile.youtube_keywords.includes(normalized)) setProfile({ ...profile, youtube_keywords: [...profile.youtube_keywords, normalized] });
                        setKeywordSuggestions(keywordSuggestions.filter((item) => item !== normalized));
                      }}
                      onRemove={(index) => {
                        if (platform === "reddit") setProfile({ ...profile, reddit_keywords: profile.reddit_keywords.filter((_, idx) => idx !== index) });
                        else if (platform === "twitter") setProfile({ ...profile, twitter_keywords: profile.twitter_keywords.filter((_, idx) => idx !== index) });
                        else setProfile({ ...profile, youtube_keywords: profile.youtube_keywords.filter((_, idx) => idx !== index) });
                      }}
                    />
                    <button className="btn btn-open" style={{ alignSelf: "flex-start" }} onClick={generateKeywords} disabled={!configEditing || suggestingKeywords}>
                      {suggestingKeywords ? "ANALYZING..." : platform === "reddit" ? "AI SUGGEST SIGNALS" : "AI SUGGEST KEYWORDS"}
                    </button>
                  </div>

                  <div className="profile-column" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <TextEditor
                      title={platform === "reddit" ? "Reddit Knowledge Block" : platform === "twitter" ? "Twitter Knowledge Block" : "YouTube Knowledge Block"}
                      filename="campaign_knowledge.md"
                      value={platform === "reddit" ? profile.reddit_knowledge_block : platform === "twitter" ? profile.twitter_knowledge_block : profile.youtube_knowledge_block}
                      disabled={!configEditing}
                      onChange={(value) => {
                        if (platform === "reddit") setProfile({ ...profile, reddit_knowledge_block: value });
                        else if (platform === "twitter") setProfile({ ...profile, twitter_knowledge_block: value });
                        else setProfile({ ...profile, youtube_knowledge_block: value });
                      }}
                    />
                    <TextEditor
                      title={platform === "reddit" ? "Reddit Prompt Template" : platform === "twitter" ? "Twitter Prompt Template" : "YouTube Prompt Template"}
                      filename={platform === "reddit" ? "reddit_prompt.txt" : platform === "twitter" ? "twitter_prompt.txt" : "youtube_prompt.txt"}
                      value={platform === "reddit" ? profile.reddit_prompt_template : platform === "twitter" ? profile.twitter_prompt_template : profile.youtube_prompt_template}
                      disabled={!configEditing}
                      onChange={(value) => {
                        if (platform === "reddit") setProfile({ ...profile, reddit_prompt_template: value });
                        else if (platform === "twitter") setProfile({ ...profile, twitter_prompt_template: value });
                        else setProfile({ ...profile, youtube_prompt_template: value });
                      }}
                    />
                  </div>
                </div>
                <div className="profile-action-bar visible">
                  <div className="profile-unsaved-text">
                    <span style={{ color: profileMessage.includes("Error") ? "var(--color-danger)" : "var(--text-muted)" }}>
                      {profileMessage || (configEditing ? "Edit mode is active. Save to restart running engines." : "Configuration is locked.")}
                    </span>
                  </div>
                  <button className="btn btn-approve" onClick={saveProfile} disabled={!configEditing || savingProfile}>
                    {savingProfile ? "SAVING..." : "SAVE CONFIGURATION"}
                  </button>
                </div>
              </div>
            )}

            {configTab === "playbooks" && platform === "twitter" && <div className="empty-state">Twitter compliance playbooks are not configured yet.</div>}
            {configTab === "playbooks" && platform === "youtube" && <div className="empty-state">YouTube compliance playbooks are not configured yet.</div>}
            {configTab === "playbooks" && platform === "reddit" && (
              <div className="triage-layout" style={{ height: "calc(100vh - 120px)" }}>
                <div className="inbox-list">
                  {playbooks.map((playbook) => (
                    <button key={playbook.subreddit} className={`list-item ${selectedSubreddit === playbook.subreddit ? "active" : ""}`} onClick={() => setSelectedSubreddit(playbook.subreddit)}>
                      <div className="list-item-header"><span className="list-item-meta">r/{playbook.subreddit}</span></div>
                      <div className="list-item-preview">Updated: {new Date(playbook.updated_at).toLocaleDateString()}</div>
                    </button>
                  ))}
                </div>
                <div className="inbox-detail">
                  {(() => {
                    const activePlaybook = playbooks.find((item) => item.subreddit === selectedSubreddit);
                    if (!activePlaybook) return <div className="empty-state">Select a subreddit playbook</div>;
                    return (
                      <div className="detail-scroll-area">
                        <div className="detail-header-meta">
                          <span className="detail-subreddit">r/{activePlaybook.subreddit}</span>
                          <a href={`https://reddit.com/r/${activePlaybook.subreddit}`} target="_blank" rel="noopener noreferrer" className="detail-link">Visit <ArrowUpRight size={14} /></a>
                        </div>
                        <h1 className="detail-title">Community Rules</h1>
                        <div className="ai-insight-box"><div className="insight-content" style={{ whiteSpace: "pre-wrap" }}>{activePlaybook.rules_text || "No rules available."}</div></div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function AuthScreen({
  mode,
  email,
  password,
  displayName,
  accountName,
  error,
  loading,
  passwordVisible,
  onModeChange,
  onEmailChange,
  onPasswordChange,
  onPasswordVisibleChange,
  onDisplayNameChange,
  onAccountNameChange,
  onSubmit,
}: {
  mode: "login" | "signup";
  email: string;
  password: string;
  displayName: string;
  accountName: string;
  error: string;
  loading: boolean;
  passwordVisible: boolean;
  onModeChange: (mode: "login" | "signup") => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onPasswordVisibleChange: (value: boolean) => void;
  onDisplayNameChange: (value: string) => void;
  onAccountNameChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
}) {
  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={onSubmit}>
        <div>
          <div className="auth-kicker">THE GATEKEEPER</div>
          <h1 className="auth-title">{mode === "login" ? "Sign in to your workspace" : "Create a workspace"}</h1>
          <p className="auth-copy">
            {mode === "login"
              ? "The existing default workspace is available after login."
              : "New workspaces start clean so each business or individual can keep separate settings and leads."}
          </p>
        </div>
        <div className="auth-mode-tabs">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => onModeChange("login")}>Login</button>
          <button type="button" className={mode === "signup" ? "active" : ""} onClick={() => onModeChange("signup")}>Sign up</button>
        </div>
        <div className="auth-fields">
          {mode === "signup" && (
            <input className="action-input" placeholder="Your name" value={displayName} onChange={(event) => onDisplayNameChange(event.target.value)} />
          )}
          <input className="action-input" placeholder="Email" type="email" value={email} onChange={(event) => onEmailChange(event.target.value)} required />
          <div className="password-field">
            <input
              className="action-input"
              placeholder="Password"
              type={passwordVisible ? "text" : "password"}
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              required
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => onPasswordVisibleChange(!passwordVisible)}
              aria-label={passwordVisible ? "Hide password" : "Show password"}
              title={passwordVisible ? "Hide password" : "Show password"}
            >
              {passwordVisible ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {mode === "signup" && (
            <input className="action-input" placeholder="Business or individual name" value={accountName} onChange={(event) => onAccountNameChange(event.target.value)} required />
          )}
        </div>
        {error && <div className="auth-error">{error}</div>}
        <button className="btn btn-approve auth-submit" type="submit" disabled={loading}>
          {loading ? "WORKING..." : mode === "login" ? "SIGN IN" : "CREATE ACCOUNT"}
        </button>
        {mode === "login" && <div className="auth-hint">Default local login: admin@soloa.local / soloa-admin</div>}
      </form>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  helper,
  tone = "blue",
}: {
  icon?: React.ReactNode;
  label: string;
  value: string | number;
  helper?: string;
  tone?: "blue" | "green" | "amber" | "purple" | "cyan" | "orange" | "slate";
}) {
  return (
    <div className={`metric-card metric-card-${tone}`}>
      <div className="metric-topline">
        <div className="metric-icon">{icon}</div>
        <div className="metric-label">{label}</div>
      </div>
      <div className="metric-value">{value}</div>
      {helper && <div className="metric-helper">{helper}</div>}
    </div>
  );
}

function InsightList({ title, rows }: { title: string; rows: [string, number][] }) {
  return (
    <div className="profile-card">
      <div className="profile-card-title">{title}</div>
      {rows.length === 0 ? (
        <div className="insight-content">No data yet.</div>
      ) : rows.map(([label, value]) => (
        <div key={label} className="insight-row">
          <span>{displayStage(label)}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

function ChartPanel({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="chart-panel">
      <div className="chart-panel-header">
        <div>
          <div className="profile-card-title">{title}</div>
          <div className="profile-card-desc">{description}</div>
        </div>
      </div>
      <div className="chart-panel-body">{children}</div>
    </section>
  );
}

function ChartEmpty({ label }: { label: string }) {
  return <div className="chart-empty">{label}</div>;
}

function DashboardTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name?: string; value?: number; payload?: { name?: string; stage?: string } }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const row = payload[0];
  const name = row.payload?.name || row.payload?.stage || label || row.name || "Value";
  return (
    <div className="dashboard-tooltip">
      <div className="dashboard-tooltip-label">{name}</div>
      <div className="dashboard-tooltip-value">{row.value}</div>
    </div>
  );
}

function HorizontalBars({ data, color }: { data: { name: string; value: number }[]; color: string }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 22, left: 8, bottom: 4 }}>
        <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" horizontal={false} />
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="name"
          axisLine={false}
          tickLine={false}
          width={110}
          tick={{ fill: "#CBD5E1", fontSize: 12 }}
        />
        <Tooltip content={<DashboardTooltip />} />
        <Bar dataKey="value" fill={color} radius={[0, 6, 6, 0]} barSize={16}>
          <LabelList dataKey="value" position="right" fill="#E2E8F0" fontSize={12} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function TagEditor({
  title,
  description,
  tags,
  disabled,
  inputValue,
  placeholder,
  prefix = "",
  suggestions = [],
  onInputChange,
  onAdd,
  onRemove,
}: {
  title: string;
  description: string;
  tags: string[];
  disabled: boolean;
  inputValue: string;
  placeholder: string;
  prefix?: string;
  suggestions?: string[];
  onInputChange: (value: string) => void;
  onAdd: (value: string) => void;
  onRemove: (index: number) => void;
}) {
  const [localValue, setLocalValue] = useState("");
  const controlledValue = inputValue || localValue;
  const setValue = (value: string) => {
    if (inputValue) onInputChange(value);
    else setLocalValue(value);
  };

  return (
    <div className="profile-card">
      <div>
        <div className="profile-card-title">{title}</div>
        <div className="profile-card-desc">{description}</div>
      </div>
      <div className="tag-input-container">
        <div className="tags-wrapper">
          {tags.map((tag, index) => (
            <span key={`${tag}-${index}`} className="tag-pill">
              {prefix}{String(tag).replace(/^@+|^r\//, "")}
              <button type="button" onClick={() => onRemove(index)} className="tag-remove-btn" disabled={disabled}><X size={12} /></button>
            </span>
          ))}
          <input
            type="text"
            className="tag-input-field"
            placeholder={placeholder}
            value={controlledValue}
            disabled={disabled}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && controlledValue.trim()) {
                event.preventDefault();
                onAdd(controlledValue);
                setValue("");
              }
            }}
          />
        </div>
        {!disabled && suggestions.length > 0 && (
          <div className="suggestion-list">
            {suggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => onAdd(suggestion)}>+ {suggestion}</button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TextEditor({
  title,
  filename,
  value,
  disabled,
  onChange,
}: {
  title: string;
  filename: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className="profile-card" style={{ flex: 1 }}>
      <div>
        <div className="profile-card-title">{title}</div>
        <div className="profile-card-desc">Campaign-specific context used for qualification and draft generation.</div>
      </div>
      <div className="code-editor-wrapper">
        <div className="code-editor-header"><span>{filename}</span><span>TEXT</span></div>
        <textarea className="code-editor-textarea" value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} spellCheck="false" />
      </div>
    </div>
  );
}
