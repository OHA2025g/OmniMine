import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { getAlerts, listOrgs, markAlertRead } from '../services/api';
import { toast } from 'sonner';
import { FeedbackGeneratorFloater } from './FeedbackGeneratorFloater';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuSeparator,
  DropdownMenuTrigger 
} from '../components/ui/dropdown-menu';
import { 
  House,
  ChatCircleDots,
  FolderOpen,
  Lightning,
  ChartLineUp,
  Bell,
  ClipboardText,
  Gear,
  SignOut,
  List,
  X,
  UserCircle,
  CaretDown
} from '@phosphor-icons/react';

const navItems = [
  { path: '/', icon: House, label: 'Dashboard' },
  { path: '/feedback', icon: ChatCircleDots, label: 'Feedback' },
  { path: '/cases', icon: FolderOpen, label: 'Cases' },
  { path: '/agents', icon: Lightning, label: 'Smart Routing' },
  { path: '/analytics', icon: ChartLineUp, label: 'Analytics' },
  { path: '/alerts', icon: Bell, label: 'Alerts' },
  { path: '/surveys', icon: ClipboardText, label: 'Surveys' },
  { path: '/settings', icon: Gear, label: 'Settings' },
];

export const Layout = () => {
  const { user, token, activeOrgId, switchOrg: switchOrgAuth, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const seenEscalationsRef = useRef(new Set());
  const [unreadAlerts, setUnreadAlerts] = useState(0);
  const [orgs, setOrgs] = useState([]);
  const [orgsLoading, setOrgsLoading] = useState(false);

  useEffect(() => {
    // Real-time alerts via SSE.
    // EventSource can't send Authorization header, so we pass JWT as query param.
    if (!token) return;

    let es;
    const connect = () => {
      const base = process.env.REACT_APP_BACKEND_URL || '';
      es = new EventSource(`${base}/api/stream/alerts?token=${encodeURIComponent(token)}`);

      es.addEventListener('alert', async (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          const a = payload?.alert;
          if (!a?.id) return;

          setUnreadAlerts((n) => n + 1);

          const isEscalation = a.type === 'case_escalated' || a.type === 'sla_breach';
          if (isEscalation) {
            if (seenEscalationsRef.current.has(a.id)) return;
            seenEscalationsRef.current.add(a.id);
            toast.warning(a.title || 'Case escalated', { description: a.message });
          } else {
            toast.message(a.title || 'New alert', { description: a.message });
          }

          // Mark read for escalation toasts to prevent repeat across refresh
          if (isEscalation) {
            try { await markAlertRead(a.id); } catch {}
          }
        } catch {
          // ignore
        }
      });

      es.addEventListener('ping', () => {});

      es.onerror = () => {
        try { es.close(); } catch {}
        // simple reconnect
        window.setTimeout(connect, 2000);
      };
    };

    // initial unread count
    (async () => {
      try {
        const data = await getAlerts(true);
        setUnreadAlerts((data || []).length);
      } catch {}
    })();

    connect();
    return () => {
      if (es) {
        try { es.close(); } catch {}
      }
    };
  }, [token]);

  useEffect(() => {
    const canSwitch = user?.role === 'admin';
    if (!canSwitch) return;
    let cancelled = false;
    (async () => {
      try {
        setOrgsLoading(true);
        const data = await listOrgs();
        if (!cancelled) setOrgs(Array.isArray(data) ? data : []);
      } catch {
        if (!cancelled) setOrgs([]);
      } finally {
        if (!cancelled) setOrgsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user?.role]);

  const getRoleBadge = (role) => {
    const classes = {
      admin: 'bg-purple-100 text-purple-700',
      manager: 'bg-blue-100 text-blue-700',
      agent: 'bg-emerald-100 text-emerald-700',
      analyst: 'bg-slate-100 text-slate-700'
    };
    return <Badge className={classes[role] || classes.analyst}>{role}</Badge>;
  };

  const currentOrgLabel = () => {
    const match = (orgs || []).find(o => o?.id === (activeOrgId || user?.org_id));
    return match?.name || (activeOrgId || user?.org_id || 'default');
  };

  const handleSwitchOrg = async (orgId) => {
    if (!orgId || orgId === (activeOrgId || user?.org_id)) return;
    try {
      await switchOrgAuth(orgId);
      toast.message('Organization switched', { description: `Now viewing: ${orgId}` });
      // refresh org list label if needed
    } catch (e) {
      toast.warning('Failed to switch org', { description: 'Please try again.' });
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="app-layout">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 z-50 h-full w-64 bg-white border-r border-slate-200 
        transform transition-transform duration-200 ease-in-out
        lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-slate-100">
            <Link to="/" className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl flex items-center justify-center">
                <ChartLineUp size={24} weight="bold" className="text-white" />
              </div>
              <div>
                <h1 className="font-heading font-bold text-xl text-slate-900">OmniMine</h1>
                <p className="text-xs text-muted-foreground">Opinion Mining</p>
              </div>
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  data-testid={`nav-${item.label.toLowerCase()}`}
                  className={`
                    flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200
                    ${isActive 
                      ? 'bg-indigo-50 text-indigo-700 font-medium' 
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }
                  `}
                >
                  <Icon 
                    size={20} 
                    weight={isActive ? 'duotone' : 'regular'} 
                    className={isActive ? 'text-indigo-600' : ''}
                  />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* User section */}
          <div className="p-4 border-t border-slate-100">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button 
                  variant="ghost" 
                  className="w-full justify-start h-auto p-3 hover:bg-slate-50"
                  data-testid="user-menu-trigger"
                >
                  <div className="flex items-center gap-3 w-full">
                    <div className="w-9 h-9 rounded-full bg-indigo-100 flex items-center justify-center">
                      <UserCircle size={24} className="text-indigo-600" />
                    </div>
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium text-slate-900 truncate">{user?.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                    </div>
                    <CaretDown size={16} className="text-muted-foreground" />
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <div className="px-2 py-2">
                  <p className="text-sm font-medium">{user?.name}</p>
                  <div className="mt-1">{getRoleBadge(user?.role)}</div>
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout} className="text-red-600" data-testid="logout-btn">
                  <SignOut size={16} className="mr-2" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:ml-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200">
          <div className="flex items-center justify-between px-4 lg:px-6 h-16">
            {/* Mobile menu button */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-2 rounded-lg hover:bg-slate-100"
              data-testid="mobile-menu-btn"
            >
              {sidebarOpen ? <X size={24} /> : <List size={24} />}
            </button>

            {/* Breadcrumb or page title */}
            <div className="hidden lg:block">
              <p className="text-sm text-muted-foreground">
                {navItems.find(n => n.path === location.pathname)?.label || 'Dashboard'}
              </p>
            </div>

            {/* Right side actions */}
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2">
                {user?.role === 'admin' ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="gap-2">
                        <span className="text-xs text-muted-foreground">Org</span>
                        <span className="text-sm font-medium">{currentOrgLabel()}</span>
                        <CaretDown size={14} className="text-muted-foreground" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-64">
                      <div className="px-2 py-2">
                        <p className="text-xs text-muted-foreground">Current</p>
                        <p className="text-sm font-medium truncate">{currentOrgLabel()}</p>
                      </div>
                      <DropdownMenuSeparator />
                      {orgsLoading && (
                        <div className="px-2 py-2 text-sm text-muted-foreground">Loading orgs…</div>
                      )}
                      {!orgsLoading && (orgs || []).length === 0 && (
                        <div className="px-2 py-2 text-sm text-muted-foreground">No organizations</div>
                      )}
                      {!orgsLoading && (orgs || []).map((o) => (
                        <DropdownMenuItem
                          key={o.id}
                          onClick={() => handleSwitchOrg(o.id)}
                          className="flex items-center justify-between"
                        >
                          <span className="truncate">{o.name}</span>
                          {(o.id === (activeOrgId || user?.org_id)) && (
                            <Badge className="bg-indigo-100 text-indigo-700">Active</Badge>
                          )}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : (
                  <Badge className="bg-slate-100 text-slate-700">
                    Org: {currentOrgLabel()}
                  </Badge>
                )}
              </div>
              <Link to="/alerts">
                <Button variant="ghost" size="icon" className="relative" data-testid="header-alerts-btn">
                  <Bell size={20} />
                  {unreadAlerts > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-rose-500 text-white text-[11px] leading-[18px] text-center">
                      {unreadAlerts > 99 ? '99+' : unreadAlerts}
                    </span>
                  )}
                </Button>
              </Link>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6 max-w-[1600px] mx-auto">
          <Outlet />
        </main>
      </div>

      {/* Dev utility floater (admin/manager can use) */}
      <FeedbackGeneratorFloater />
    </div>
  );
};
