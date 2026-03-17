import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { getAlerts, markAlertRead, markAllAlertsRead } from '../services/api';
import { toast } from 'sonner';
import { 
  Bell, 
  BellRinging,
  Check,
  CheckCircle,
  Warning,
  Info
} from '@phosphor-icons/react';

export const AlertsPage = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const navigate = useNavigate();

  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const data = await getAlerts();
      setAlerts(data);
    } catch (error) {
      toast.error('Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkRead = async (id) => {
    try {
      await markAlertRead(id);
      setAlerts(alerts.map(a => a.id === id ? { ...a, is_read: true } : a));
    } catch (error) {
      toast.error('Failed to mark as read');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllAlertsRead();
      setAlerts(alerts.map(a => ({ ...a, is_read: true })));
      toast.success('All alerts marked as read');
    } catch (error) {
      toast.error('Failed to mark all as read');
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical':
      case 'high':
        return <Warning size={20} weight="fill" className="text-rose-500" />;
      case 'medium':
        return <BellRinging size={20} weight="fill" className="text-amber-500" />;
      default:
        return <Info size={20} weight="fill" className="text-blue-500" />;
    }
  };

  const getSeverityBadge = (severity) => {
    const classes = {
      critical: 'bg-red-100 text-red-700',
      high: 'bg-orange-100 text-orange-700',
      medium: 'bg-amber-100 text-amber-700',
      low: 'bg-blue-100 text-blue-700'
    };
    return <Badge className={classes[severity]}>{severity}</Badge>;
  };

  const filteredAlerts = alerts.filter(a => {
    if (filter === 'unread') return !a.is_read;
    return true;
  });

  const unreadCount = alerts.filter(a => !a.is_read).length;

  const getCaseIdFromAlert = (alert) => {
    if (!alert?.related_ids || alert.related_ids.length === 0) return null;
    // convention: case id is first for case_* alerts
    return alert.related_ids[0];
  };

  return (
    <div className="space-y-6" data-testid="alerts-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Alerts</h1>
          <p className="text-muted-foreground mt-1">
            {unreadCount > 0 ? `${unreadCount} unread alerts` : 'No unread alerts'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant={filter === 'all' ? 'default' : 'outline'} 
            onClick={() => setFilter('all')}
            className={filter === 'all' ? 'bg-indigo-600' : ''}
          >
            All
          </Button>
          <Button 
            variant={filter === 'unread' ? 'default' : 'outline'} 
            onClick={() => setFilter('unread')}
            className={filter === 'unread' ? 'bg-indigo-600' : ''}
          >
            Unread
          </Button>
          {unreadCount > 0 && (
            <Button variant="outline" onClick={handleMarkAllRead} data-testid="mark-all-read-btn">
              <CheckCircle size={16} className="mr-2" />
              Mark All Read
            </Button>
          )}
        </div>
      </div>

      {/* Alerts List */}
      <Card className="dashboard-card">
        <CardContent className="p-0">
          {loading ? (
            <div className="text-center py-12 text-muted-foreground">Loading...</div>
          ) : filteredAlerts.length === 0 ? (
            <div className="text-center py-12">
              <Bell size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground">No alerts to show</p>
            </div>
          ) : (
            <div className="divide-y">
              {filteredAlerts.map((alert) => (
                <div 
                  key={alert.id} 
                  className={`flex items-start gap-4 p-4 hover:bg-slate-50 transition-colors ${!alert.is_read ? 'bg-indigo-50/50' : ''}`}
                >
                  <div className="mt-1">
                    {getSeverityIcon(alert.severity)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className={`font-medium ${!alert.is_read ? 'text-slate-900' : 'text-slate-600'}`}>
                        {alert.title}
                      </h3>
                      {getSeverityBadge(alert.severity)}
                      {!alert.is_read && (
                        <Badge className="bg-indigo-100 text-indigo-700">New</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{alert.message}</p>
                    <p className="text-xs text-muted-foreground mt-2">
                      {new Date(alert.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    {(alert.type === 'case_escalated' || alert.type === 'sla_breach' || alert.type === 'case_created' || alert.type === 'case_auto_assigned') && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const caseId = getCaseIdFromAlert(alert);
                          if (caseId) navigate(`/cases?case_id=${caseId}`);
                        }}
                        title="View Case"
                      >
                        View
                      </Button>
                    )}
                    {!alert.is_read && (
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => handleMarkRead(alert.id)}
                        data-testid={`mark-read-${alert.id}`}
                      >
                        <Check size={16} />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
