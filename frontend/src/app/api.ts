const getApiBase = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const cleanUrl = envUrl.endsWith("/") ? envUrl.slice(0, -1) : envUrl;
  return cleanUrl.endsWith("/api") ? cleanUrl : `${cleanUrl}/api`;
};

const API_BASE = getApiBase();

export interface Transaction {
  id: string;
  date: string;
  description: string;
  merchant: string;
  amount: number;
  currency: string;
  category: string;
  confidence: string;
  is_recurring: boolean;
  flags: string[];
}

export interface Profile {
  id: string;
  email: string;
  currency: string;
  savings_goal: number;
}

export interface SubscriptionItem {
  merchant: string;
  amount: number;
  flagged: boolean;
  flags: string[];
}

export interface OpportunityItem {
  action: string;
  saving: number;
  effort: string;
  evidence: string;
}

export interface CategoryBreakdown {
  [categoryName: string]: {
    total: number;
    pct_of_income: number;
    mom_change_pct: number;
    three_month_avg: number;
    flagged_high: boolean;
  };
}

export interface AnalysisResults {
  month: string;
  income: number;
  spent: number;
  saved: number;
  savings_rate: number;
  savings_goal: number;
  mom_spent_change_pct: number;
  categories: CategoryBreakdown;
  subscriptions: {
    items: SubscriptionItem[];
    total_monthly_burn: number;
  };
  patterns: string[];
  opportunities: OpportunityItem[];
}

export interface IngestionResponse {
  status: "ok" | "needs_review" | "alert";
  summary: string;
  transactions: Transaction[];
  flags: string[];
  analysis: AnalysisResults;
  briefing: string;
}

export interface Briefing {
  id: string;
  profile_id: string;
  month: string;
  briefing_text: string;
  analysis: AnalysisResults;
  created_at: string;
}

export async function fetchProfile(profileId?: string): Promise<Profile> {
  const url = profileId ? `${API_BASE}/profile?profile_id=${profileId}` : `${API_BASE}/profile`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json();
}

export async function updateProfile(currency: string, savingsGoal: number, profileId?: string): Promise<Profile> {
  const url = profileId ? `${API_BASE}/profile?profile_id=${profileId}` : `${API_BASE}/profile`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ currency, savings_goal: savingsGoal }),
  });
  if (!res.ok) throw new Error("Failed to update profile");
  return res.json();
}

export async function fetchTransactions(profileId?: string): Promise<Transaction[]> {
  const url = profileId ? `${API_BASE}/transactions?profile_id=${profileId}` : `${API_BASE}/transactions`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch transactions");
  return res.json();
}

export async function fetchBriefings(profileId?: string): Promise<Briefing[]> {
  const url = profileId ? `${API_BASE}/briefings?profile_id=${profileId}` : `${API_BASE}/briefings`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch briefings");
  return res.json();
}

export async function uploadStatementFile(file: File, profileId?: string): Promise<IngestionResponse> {
  const url = `${API_BASE}/upload`;
  const formData = new FormData();
  formData.append("file", file);
  if (profileId) {
    formData.append("profile_id", profileId);
  }
  
  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to upload statement file");
  }
  return res.json();
}
