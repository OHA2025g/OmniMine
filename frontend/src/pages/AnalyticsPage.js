import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  getAnalyticsOverview,
  getSentimentTrends,
  getSourceDistribution,
  getThemeDistribution,
  getEmotionDistribution,
  getRiskGovernanceKpis,
} from '../services/api';
import { toast } from 'sonner';
import {
  ChartLineUp,
  ChartPie,
  ChartBar,
  TrendUp,
  Sparkle,
  Smiley,
  ShieldCheck,
  WarningCircle,
  CurrencyCircleDollar,
} from '@phosphor-icons/react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, Legend, AreaChart, Area,
} from 'recharts';

const SENTIMENT_COLORS = {
  positive: '#10B981',
  neutral: '#64748B',
  negative: '#F43F5E',
};

const CHART_COLORS = ['#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#06B6D4', '#8B5CF6', '#EF4444', '#14B8A6', '#8B5CF6'];

const num = (v) => Number(v || 0).toLocaleString();

export const AnalyticsPage = () => {
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState([]);
  const [sources, setSources] = useState([]);
  const [themes, setThemes] = useState([]);
  const [emotions, setEmotions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trendDays, setTrendDays] = useState('30');

  const [riskData, setRiskData] = useState(null);
  const [riskLoading, setRiskLoading] = useState(true);

  useEffect(() => {
    fetchData();
    fetchRiskGovernance();
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
        getEmotionDistribution(),
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
      const trendsData = await getSentimentTrends(parseInt(trendDays, 10));
      setTrends(trendsData);
    } catch (error) {
      console.error('Failed to fetch trends');
    }
  };

  const fetchRiskGovernance = async () => {
    setRiskLoading(true);
    try {
      const data = await getRiskGovernanceKpis(90, 365);
      setRiskData(data);
    } catch (error) {
      toast.error('Failed to fetch Risk & Governance KPIs');
    } finally {
      setRiskLoading(false);
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

  const riskKpis = riskData?.kpis || {};
  const regionZoneSurge = riskData?.region_zone_surge || [];
  const productGrowth = riskData?.product_growth || [];
  const promoTrend = riskData?.promoted_vs_non_promoted_trend || [];
  const priceOutliers = riskData?.price_variance_outliers || [];
  const divisionZoneOutliers = riskData?.division_zone_sales_outliers || [];

  return (
    <div className="space-y-6" data-testid="analytics-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Analytics</h1>
          <p className="text-muted-foreground mt-1">Insights, trends, and risk governance KPIs</p>
        </div>
      </div>

      <Tabs defaultValue="insights" className="space-y-6">
        <TabsList>
          <TabsTrigger value="insights">Insights</TabsTrigger>
          <TabsTrigger value="risk-governance">Risk & Governance</TabsTrigger>
        </TabsList>

        <TabsContent value="insights" className="space-y-6">
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
                        <stop offset="5%" stopColor={SENTIMENT_COLORS.positive} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={SENTIMENT_COLORS.positive} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorNeutral" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={SENTIMENT_COLORS.neutral} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={SENTIMENT_COLORS.neutral} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorNegative" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={SENTIMENT_COLORS.negative} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={SENTIMENT_COLORS.negative} stopOpacity={0} />
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="dashboard-card">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <ChartPie size={20} weight="duotone" className="text-indigo-600" />
                  Sentiment Distribution
                </CardTitle>
              </CardHeader>
              <CardContent>
                {sentimentData.some((d) => d.value > 0) ? (
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                                backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
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
        </TabsContent>

        <TabsContent value="risk-governance" className="space-y-6">
          {riskLoading ? (
            <div className="h-48 flex items-center justify-center text-muted-foreground">Loading risk KPIs...</div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <Card className="dashboard-card">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 text-amber-700">
                      <WarningCircle size={18} />
                      <span className="text-xs">High-growth Region/Zone</span>
                    </div>
                    <p className="text-2xl font-bold mt-2">{num(riskKpis.high_growth_region_zone_count)}</p>
                  </CardContent>
                </Card>
                <Card className="dashboard-card">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 text-indigo-700">
                      <ChartLineUp size={18} />
                      <span className="text-xs">High-growth Products</span>
                    </div>
                    <p className="text-2xl font-bold mt-2">{num(riskKpis.high_growth_product_count)}</p>
                  </CardContent>
                </Card>
                <Card className="dashboard-card">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 text-rose-700">
                      <CurrencyCircleDollar size={18} />
                      <span className="text-xs">Price Outliers</span>
                    </div>
                    <p className="text-2xl font-bold mt-2">{num(riskKpis.price_variance_outlier_count)}</p>
                  </CardContent>
                </Card>
                <Card className="dashboard-card">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 text-blue-700">
                      <ShieldCheck size={18} />
                      <span className="text-xs">Division-Zone Outliers</span>
                    </div>
                    <p className="text-2xl font-bold mt-2">{num(riskKpis.division_zone_outlier_count)}</p>
                  </CardContent>
                </Card>
                <Card className="dashboard-card">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 text-slate-700">
                      <ChartBar size={18} />
                      <span className="text-xs">Recent Sales Records</span>
                    </div>
                    <p className="text-2xl font-bold mt-2">{num(riskKpis.recent_records_used)}</p>
                  </CardContent>
                </Card>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="dashboard-card">
                  <CardHeader>
                    <CardTitle>1) Region/Zone sudden sales increase</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {regionZoneSurge.length > 0 ? (
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={regionZoneSurge.slice(0, 8)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="region_zone" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                          <YAxis tick={{ fontSize: 12 }} />
                          <Tooltip />
                          <Bar dataKey="growth_pct" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <div className="text-muted-foreground">No sales metadata for region/zone surge.</div>}
                  </CardContent>
                </Card>

                <Card className="dashboard-card">
                  <CardHeader>
                    <CardTitle>2) Products with recent sales surge vs history</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {productGrowth.length > 0 ? (
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={productGrowth.slice(0, 8)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="product" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                          <YAxis tick={{ fontSize: 12 }} />
                          <Tooltip />
                          <Bar dataKey="growth_pct" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <div className="text-muted-foreground">No product sales trend data available.</div>}
                  </CardContent>
                </Card>
              </div>

              <Card className="dashboard-card">
                <CardHeader>
                  <CardTitle>3) Non-promoted vs promoted product sales trend</CardTitle>
                </CardHeader>
                <CardContent>
                  {promoTrend.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={promoTrend}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="promoted" stroke="#10B981" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="non_promoted" stroke="#F43F5E" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : <div className="text-muted-foreground">No promoted vs non-promoted trend data available.</div>}
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="dashboard-card">
                  <CardHeader>
                    <CardTitle>4) Same product + same zone price variance outliers</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 max-h-[320px] overflow-y-auto">
                    {priceOutliers.length > 0 ? priceOutliers.slice(0, 12).map((x, idx) => (
                      <div key={`${x.product}-${x.zone}-${idx}`} className="border rounded-md p-2 flex items-center justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium capitalize">{x.product} · {x.zone}</p>
                          <p className="text-xs text-muted-foreground">Price {x.price} vs mean {x.mean_price}</p>
                        </div>
                        <Badge variant="outline">z={x.zscore}</Badge>
                      </div>
                    )) : <div className="text-muted-foreground">No price variance outliers detected.</div>}
                  </CardContent>
                </Card>

                <Card className="dashboard-card">
                  <CardHeader>
                    <CardTitle>5) Division code + zone sales outliers</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {divisionZoneOutliers.length > 0 ? (
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={divisionZoneOutliers.slice(0, 10)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="zone" tick={{ fontSize: 12 }} />
                          <YAxis tick={{ fontSize: 12 }} />
                          <Tooltip />
                          <Bar dataKey="sales_total" fill="#0EA5E9" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <div className="text-muted-foreground">No division-zone outliers detected.</div>}
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};
