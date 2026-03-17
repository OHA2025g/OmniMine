import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { getAnalyticsOverview, getSentimentTrends, getSourceDistribution, getFeedbacks, getCases, seedDemoData, getExecutiveDigest, getMonitoringLive } from '../services/api';
import { toast } from 'sonner';
import { 
  ChartLineUp, 
  ChatCircleDots, 
  CheckCircle, 
  Warning, 
  TrendUp, 
  TrendDown,
  Users,
  Gauge,
  ArrowRight,
  Database
} from '@phosphor-icons/react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from 'recharts';

const SENTIMENT_COLORS = {
  positive: '#10B981',
  neutral: '#64748B',
  negative: '#F43F5E'
};

const SOURCE_COLORS = ['#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#06B6D4', '#8B5CF6'];

export const DashboardPage = () => {
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState([]);
  const [sources, setSources] = useState([]);
  const [recentFeedbacks, setRecentFeedbacks] = useState([]);
  const [recentCases, setRecentCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [digestOpen, setDigestOpen] = useState(false);
  const [digestLoading, setDigestLoading] = useState(false);
  const [digest, setDigest] = useState(null);
  const [digestDays, setDigestDays] = useState(7);
  const [live, setLive] = useState(null);
  const [liveLoading, setLiveLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    let timer = null;
    const tick = async () => {
      setLiveLoading(true);
      try {
        const data = await getMonitoringLive();
        setLive(data);
      } catch (e) {
        // no-op; monitoring is optional on cold start
      } finally {
        setLiveLoading(false);
      }
    };

    tick();
    timer = window.setInterval(tick, 3000);
    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, []);

  const fetchData = async () => {
    try {
      const [overviewData, trendsData, sourcesData, feedbacksData, casesData] = await Promise.all([
        getAnalyticsOverview(),
        getSentimentTrends(14),
        getSourceDistribution(),
        getFeedbacks({ limit: 5 }),
        getCases({ limit: 5 })
      ]);
      setOverview(overviewData);
      setTrends(trendsData);
      setSources(sourcesData);
      setRecentFeedbacks(feedbacksData);
      setRecentCases(casesData);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSeedData = async () => {
    setSeeding(true);
    try {
      await seedDemoData();
      toast.success('Demo data seeded successfully!');
      fetchData();
    } catch (error) {
      toast.error('Failed to seed data');
    } finally {
      setSeeding(false);
    }
  };

  const handleGenerateDigest = async () => {
    setDigestLoading(true);
    try {
      const data = await getExecutiveDigest(digestDays);
      setDigest(data);
      toast.success('Executive digest generated');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate digest');
    } finally {
      setDigestLoading(false);
    }
  };

  const getSentimentBadge = (sentiment) => {
    const classes = {
      positive: 'sentiment-positive',
      neutral: 'sentiment-neutral',
      negative: 'sentiment-negative'
    };
    return <Badge variant="outline" className={classes[sentiment]}>{sentiment}</Badge>;
  };

  const getStatusBadge = (status) => {
    return <Badge variant="outline" className={`status-${status}`}>{status.replace('_', ' ')}</Badge>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse-slow text-muted-foreground">Loading dashboard...</div>
      </div>
    );
  }

  const hasData = overview?.feedback?.total > 0;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Monitor customer feedback and sentiment in real-time</p>
        </div>
        <div className="flex items-center gap-2">
          <Dialog open={digestOpen} onOpenChange={setDigestOpen}>
            <DialogTrigger asChild>
              <Button variant="outline">
                Executive Digest
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-2xl">
              <DialogHeader>
                <DialogTitle className="font-heading">Executive Digest</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Window:</span>
                  <div className="flex gap-2">
                    {[7, 14, 30].map((d) => (
                      <Button
                        key={d}
                        size="sm"
                        variant={digestDays === d ? 'default' : 'outline'}
                        className={digestDays === d ? 'bg-indigo-600' : ''}
                        onClick={() => setDigestDays(d)}
                      >
                        {d}d
                      </Button>
                    ))}
                  </div>
                  <div className="flex-1" />
                  <Button
                    className="bg-indigo-600 hover:bg-indigo-700"
                    onClick={handleGenerateDigest}
                    disabled={digestLoading}
                  >
                    {digestLoading ? 'Generating...' : 'Generate'}
                  </Button>
                </div>

                {digest ? (
                  <div className="space-y-4">
                    <div className="bg-slate-50 rounded-lg p-4">
                      <p className="text-xs text-muted-foreground mb-1">Summary</p>
                      <p className="text-sm">{digest.summary}</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="border rounded-lg p-4">
                        <p className="text-xs text-muted-foreground mb-2">Top themes</p>
                        <div className="space-y-2">
                          {(digest.top_themes || []).slice(0, 6).map((t) => (
                            <div key={t.theme} className="flex items-center justify-between text-sm">
                              <span className="truncate">{t.theme}</span>
                              <Badge variant="outline">{t.count}</Badge>
                            </div>
                          ))}
                          {(digest.top_themes || []).length === 0 && (
                            <p className="text-sm text-muted-foreground">No themes yet</p>
                          )}
                        </div>
                      </div>
                      <div className="border rounded-lg p-4">
                        <p className="text-xs text-muted-foreground mb-2">Risks</p>
                        <ul className="list-disc pl-5 text-sm space-y-1">
                          {(digest.risks || []).slice(0, 6).map((r, idx) => (
                            <li key={idx}>{r}</li>
                          ))}
                          {(digest.risks || []).length === 0 && (
                            <li className="text-muted-foreground">No risks detected</li>
                          )}
                        </ul>
                      </div>
                    </div>

                    <div className="border rounded-lg p-4">
                      <p className="text-xs text-muted-foreground mb-2">Recommended actions</p>
                      <ul className="list-disc pl-5 text-sm space-y-1">
                        {(digest.recommended_actions || []).slice(0, 6).map((a, idx) => (
                          <li key={idx}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    Generate a digest to get risks, themes, and recommended actions.
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>

          {!hasData && (
            <Button 
              onClick={handleSeedData} 
              disabled={seeding}
              className="bg-indigo-600 hover:bg-indigo-700"
              data-testid="seed-demo-btn"
            >
              <Database size={18} className="mr-2" />
              {seeding ? 'Seeding...' : 'Load Demo Data'}
            </Button>
          )}
        </div>
      </div>

      {/* Live monitoring */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="dashboard-card animate-fade-in">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Gauge size={20} className="text-indigo-600" />
                Live (last 60s)
              </span>
              <Badge variant="outline" className="text-xs">
                {liveLoading ? 'updating…' : 'live'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Total events</span>
              <Badge variant="outline">{live?.window_seconds?.s60 ?? 0}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Positive</p>
                <p className="text-lg font-semibold text-emerald-600">{live?.sentiment?.s60?.positive ?? 0}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Neutral</p>
                <p className="text-lg font-semibold text-slate-700">{live?.sentiment?.s60?.neutral ?? 0}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Negative</p>
                <p className="text-lg font-semibold text-rose-600">{live?.sentiment?.s60?.negative ?? 0}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Tip: use the floating Play button to generate live load.
            </p>
          </CardContent>
        </Card>

        <Card className="dashboard-card animate-fade-in lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <ChartLineUp size={20} className="text-indigo-600" />
              Top themes (last 5m)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {(live?.top_themes_s300 || []).slice(0, 8).map((t) => (
                <div key={t.theme} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                  <span className="truncate">{t.theme}</span>
                  <Badge variant="outline">{t.count}</Badge>
                </div>
              ))}
              {(live?.top_themes_s300 || []).length === 0 && (
                <div className="text-sm text-muted-foreground">No live themes yet (needs recent feedback).</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="dashboard-card animate-fade-in">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Feedback</p>
                <p className="text-3xl font-heading font-bold mt-1">{overview?.feedback?.total || 0}</p>
              </div>
              <div className="p-3 bg-indigo-50 rounded-lg">
                <ChatCircleDots size={24} weight="duotone" className="text-indigo-600" />
              </div>
            </div>
            <div className="flex items-center mt-4 text-sm">
              <span className="text-emerald-600 flex items-center">
                <TrendUp size={16} className="mr-1" />
                {overview?.feedback?.positive_rate?.toFixed(1) || 0}%
              </span>
              <span className="text-muted-foreground ml-2">positive rate</span>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card animate-fade-in stagger-1">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Open Cases</p>
                <p className="text-3xl font-heading font-bold mt-1">{overview?.cases?.open || 0}</p>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <Warning size={24} weight="duotone" className="text-amber-600" />
              </div>
            </div>
            <div className="flex items-center mt-4 text-sm">
              <span className="text-muted-foreground">{overview?.cases?.total || 0} total cases</span>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card animate-fade-in stagger-2">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Closure Rate</p>
                <p className="text-3xl font-heading font-bold mt-1">{overview?.kpis?.closure_rate?.toFixed(1) || 0}%</p>
              </div>
              <div className="p-3 bg-emerald-50 rounded-lg">
                <CheckCircle size={24} weight="duotone" className="text-emerald-600" />
              </div>
            </div>
            <Progress value={overview?.kpis?.closure_rate || 0} className="mt-4 h-2" />
          </CardContent>
        </Card>

        <Card className="dashboard-card animate-fade-in stagger-3">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">CSAT Score</p>
                <p className="text-3xl font-heading font-bold mt-1">{overview?.kpis?.csat?.toFixed(1) || 0}/5</p>
              </div>
              <div className="p-3 bg-violet-50 rounded-lg">
                <Gauge size={24} weight="duotone" className="text-violet-600" />
              </div>
            </div>
            <Progress value={(overview?.kpis?.csat || 0) * 20} className="mt-4 h-2" />
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sentiment Trends */}
        <Card className="dashboard-card lg:col-span-2 animate-fade-in stagger-4">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <ChartLineUp size={20} weight="duotone" className="text-indigo-600" />
              Sentiment Trends (14 days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trends.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="positive" stroke={SENTIMENT_COLORS.positive} strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="neutral" stroke={SENTIMENT_COLORS.neutral} strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="negative" stroke={SENTIMENT_COLORS.negative} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[280px] flex items-center justify-center text-muted-foreground">
                No trend data available yet
              </div>
            )}
            <div className="flex justify-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-sm text-muted-foreground">Positive</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-slate-500" />
                <span className="text-sm text-muted-foreground">Neutral</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-rose-500" />
                <span className="text-sm text-muted-foreground">Negative</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Source Distribution */}
        <Card className="dashboard-card animate-fade-in stagger-5">
          <CardHeader>
            <CardTitle className="font-heading">Feedback Sources</CardTitle>
          </CardHeader>
          <CardContent>
            {sources.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={sources}
                      dataKey="count"
                      nameKey="source"
                      cx="50%"
                      cy="50%"
                      outerRadius={70}
                      innerRadius={40}
                    >
                      {sources.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={SOURCE_COLORS[index % SOURCE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2 mt-2">
                  {sources.slice(0, 4).map((source, index) => (
                    <div key={source.source} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: SOURCE_COLORS[index % SOURCE_COLORS.length] }}
                        />
                        <span className="capitalize">{source.source?.replace('_', ' ')}</span>
                      </div>
                      <span className="text-muted-foreground">{source.count}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="h-[200px] flex items-center justify-center text-muted-foreground">
                No source data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Feedback */}
        <Card className="dashboard-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="font-heading">Recent Feedback</CardTitle>
            <Link to="/feedback">
              <Button variant="ghost" size="sm" className="text-indigo-600" data-testid="view-all-feedback-btn">
                View all <ArrowRight size={16} className="ml-1" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentFeedbacks.length > 0 ? (
              <div className="space-y-4">
                {recentFeedbacks.map((feedback) => (
                  <div key={feedback.id} className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700 line-clamp-2">{feedback.content}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-xs text-muted-foreground capitalize">{feedback.source?.replace('_', ' ')}</span>
                        {feedback.analysis && getSentimentBadge(feedback.analysis.sentiment)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-8">No feedback yet</p>
            )}
          </CardContent>
        </Card>

        {/* Recent Cases */}
        <Card className="dashboard-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="font-heading">Recent Cases</CardTitle>
            <Link to="/cases">
              <Button variant="ghost" size="sm" className="text-indigo-600" data-testid="view-all-cases-btn">
                View all <ArrowRight size={16} className="ml-1" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentCases.length > 0 ? (
              <div className="space-y-4">
                {recentCases.map((caseItem) => (
                  <div key={caseItem.id} className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-700 line-clamp-1">{caseItem.title}</p>
                      <div className="flex items-center gap-2 mt-2">
                        {getStatusBadge(caseItem.status)}
                        <Badge variant="outline" className={`priority-${caseItem.priority}`}>
                          {caseItem.priority}
                        </Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-8">No cases yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Sentiment Distribution Bar */}
      {hasData && (
        <Card className="dashboard-card">
          <CardHeader>
            <CardTitle className="font-heading">Sentiment Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex h-4 rounded-full overflow-hidden">
                  <div 
                    className="bg-emerald-500 transition-all duration-500" 
                    style={{ width: `${(overview?.feedback?.positive / overview?.feedback?.total * 100) || 0}%` }}
                  />
                  <div 
                    className="bg-slate-400 transition-all duration-500" 
                    style={{ width: `${(overview?.feedback?.neutral / overview?.feedback?.total * 100) || 0}%` }}
                  />
                  <div 
                    className="bg-rose-500 transition-all duration-500" 
                    style={{ width: `${(overview?.feedback?.negative / overview?.feedback?.total * 100) || 0}%` }}
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-between mt-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span>Positive: {overview?.feedback?.positive || 0}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-slate-400" />
                <span>Neutral: {overview?.feedback?.neutral || 0}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-rose-500" />
                <span>Negative: {overview?.feedback?.negative || 0}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
