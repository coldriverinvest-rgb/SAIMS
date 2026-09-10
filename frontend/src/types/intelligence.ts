export type BriefingLevel = "CRITICAL" | "WARN" | "INFO";
export type NewsSentiment = "POSITIVE" | "NEUTRAL" | "RISK";

export interface ExecutiveBriefing {
  id: string;
  level: BriefingLevel;
  title: string;
  fact: string;
  impact: string;
}

export interface DisclosureItem {
  id: string;
  date: string;
  company: string;
  title: string;
  isKeyExecutiveIssue: boolean;
  keyMetrics?: string;
  url: string;
}

export interface NewsArticle {
  title: string;
  press: string;
  time: string;
  url: string;
}

export interface NewsCluster {
  id: string;
  topicTitle: string;
  mainArticle: NewsArticle;
  clusterCount: number;
  sentiment: NewsSentiment;
  relatedArticles: NewsArticle[];
}
