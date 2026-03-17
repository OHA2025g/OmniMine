import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { getAnalyticsOverview, getSentimentTrends, getSourceDistribution, getThemeDistribution, getEmotionDistribution } from '../services/api';
import { toast } from 'sonner';
import { 
  ChartLineUp, 
  ChartPie, 
  ChartBar,
  TrendUp,
  TrendDown,
  Sparkle,
  Smiley
} from '@phosphor-icons/react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, BarChart, Bar, Legend, AreaChart, Area 
} from 'recharts';

const SENTIMENT_COLORS = {
  positive: '#10B981',
  neutral: '#64748B',
  negative: '#F43F5E'
};

const CHART_COLORS = ['#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#06B6D4', '#8B5CF6', '#EF4444', '#14B8A6', '#8B5CF6'];

export const AnalyticsPage = () => {
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState([]);
  const [sources, setSources] = useState([]);
  const [themes, setThemes] = useState([]);
  const [emotions, setEmotions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trendDays, setTrendDays] = useState('30');

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    fetchTrends();
  }, [trendDays]);

  const fetchData = async () => {
    try {
      const [overviewData, sourcesData, themesData, emotionsData] = await Promise.all([
        getAnalyticsOverview(),
        getSourceDistribution(),
        getThemeDistribution(),
        getEmotionDistribution()
      ]);
      setOverview(overviewData);
      setSources(sourcesData);
      setThemes(themesData);
      setEmotions(emotionsData);
    } catch (error) {
      toast.error('Failed to fetch analytics data');
    } finally {
      setLoading(false);
    }
  };

  const fetchTrends = async () => {
    try {
      const trendsData = await getSentimentTrends(parseInt(trendDays));
      setTrends(trendsData);
    } catch (error) {
      console.error('Failed to fetch trends');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse-slow text-muted-foreground">Loading analytics...</div>
      </div>
    );
  }

  const sentimentData = overview ? [
    { name: 'Positive', value: overview.feedback.positive, color: SENTIMENT_COLORS.positive },
    { name: 'Neutral', value: overview.feedback.neutral, color: SENTIMENT_COLORS.neutral },
    { name: 'Negative', value: overview.feedback.negative, color: SENTIMENT_COLORS.negative },
  ] : [];

  return (
    <div className="space-y-6" data-testid="analytics-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Analytics</h1>
          <p className="text-muted-foreground mt-1">Insights and trends from customer feedback</p>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-50 rounded-lg">
                <TrendUp size={24} weight="duotone" className="text-emerald-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Positive Rate</p>
                <p className="text-2xl font-heading font-bold">
                  {overview?.feedback?.positive_rate?.toFixed(1) || 0}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-amber-50 rounded-lg">
                <ChartBar size={24} weight="duotone" className="text-amber-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Closure Rate</p>
                <p className="text-2xl font-heading font-bold">
                  {overview?.kpis?.closure_rate?.toFixed(1) || 0}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-indigo-50 rounded-lg">
                <Sparkle size={24} weight="duotone" className="text-indigo-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">SLA Compliance</p>
                <p className="text-2xl font-heading font-bold">
                  {overview?.kpis?.sla_compliance?.toFixed(1) || 100}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Sentiment Trends */}
      <Card className="dashboard-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="font-heading flex items-center gap-2">
            <ChartLineUp size={20} weight="duotone" className="text-indigo-600" />
            Sentiment Trends
          </CardTitle>
          <Select value={trendDays} onValueChange={setTrendDays}>
            <SelectTrigger className="w-[120px]" data-testid="trend-days-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7 days</SelectItem>
              <SelectItem value="14">14 days</SelectItem>
              <SelectItem value="30">30 days</SelectItem>
              <SelectItem value="90">90 days</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          {trends.length > 0 ? (
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={trends}>
                <defs>
                  <linearGradient id="colorPositive" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={SENTIMENT_COLORS.positive} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={SENTIMENT_COLORS.positive} stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorNeutral" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={SENTIMENT_COLORS.neutral} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={SENTIMENT_COLORS.neutral} stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorNegative" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={SENTIMENT_COLORS.negative} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={SENTIMENT_COLORS.negative} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="positive" stroke={SENTIMENT_COLORS.positive} fillOpacity={1} fill="url(#colorPositive)" />
                <Area type="monotone" dataKey="neutral" stroke={SENTIMENT_COLORS.neutral} fillOpacity={1} fill="url(#colorNeutral)" />
                <Area type="monotone" dataKey="negative" stroke={SENTIMENT_COLORS.negative} fillOpacity={1} fill="url(#colorNegative)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[350px] flex items-center justify-center text-muted-foreground">
              No trend data available. Add feedback to see trends.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sentiment Distribution */}
        <Card className="dashboard-card">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <ChartPie size={20} weight="duotone" className="text-indigo-600" />
              Sentiment Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sentimentData.some(d => d.value > 0) ? (
              <>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={sentimentData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      innerRadius={50}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                    >
                      {sentimentData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex justify-center gap-4 mt-4">
                  {sentimentData.map((d) => (
                    <div key={d.name} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: d.color }} />
                      <span className="text-sm">{d.name}: {d.value}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                No sentiment data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* Source Distribution */}
        <Card className="dashboard-card">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <ChartBar size={20} weight="duotone" className="text-indigo-600" />
              Feedback by Source
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sources.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={sources} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" tick={{ fontSize: 12 }} />
                  <YAxis dataKey="source" type="category" tick={{ fontSize: 12 }} width={100} tickFormatter={(v) => v?.replace('_', ' ')} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#4F46E5" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                No source data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Theme & Emotion Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Theme Distribution */}
        <Card className="dashboard-card">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <Sparkle size={20} weight="duotone" className="text-indigo-600" />
              Top Themes
            </CardTitle>
          </CardHeader>
          <CardContent>
            {themes.length > 0 ? (
              <div className="space-y-3">
                {themes.slice(0, 10).map((theme, i) => (
                  <div key={theme.theme} className="flex items-center gap-3">
                    <div className="w-8 text-sm text-muted-foreground">{i + 1}</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium capitalize">{theme.theme}</span>
                        <span className="text-sm text-muted-foreground">{theme.count}</span>
                      </div>
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div 
                          className="h-full rounded-full transition-all duration-500"
                          style={{ 
                            width: `${(theme.count / themes[0].count) * 100}%`,
                            backgroundColor: CHART_COLORS[i % CHART_COLORS.length]
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-[200px] flex items-center justify-center text-muted-foreground">
                No theme data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* Emotion Distribution */}
        <Card className="dashboard-card">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <Smiley size={20} weight="duotone" className="text-indigo-600" />
              Emotion Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {emotions.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={emotions.slice(0, 8)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="emotion" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {emotions.slice(0, 8).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                No emotion data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
