import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { getAdminSummary, getUsers, listOrgs, updateUserRole, moveUserToOrg, createOrg, queryAuditEvents, exportAuditCsv, bulkUserAction, getSystemSettings, updateSystemSettings } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

export const AdminPage = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [users, setUsers] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [audit, setAudit] = useState([]);
  const [newOrgName, setNewOrgName] = useState('');
  const [auditAction, setAuditAction] = useState('');
  const [bulkUserIds, setBulkUserIds] = useState('');
  const [bulkPassword, setBulkPassword] = useState('');
  const [settings, setSettings] = useState({
    password_min_length: 8,
    mfa_required_for_admins: false,
    audit_retention_days: 90,
  });

  const canAdmin = user?.role === 'admin';

  const load = async () => {
    setLoading(true);
    try {
      const [s, u, o, a, sys] = await Promise.all([
        getAdminSummary(),
        getUsers(),
        listOrgs(),
        queryAuditEvents({ limit: 100 }),
        getSystemSettings(),
      ]);
      setSummary(s);
      setUsers(Array.isArray(u) ? u : []);
      setOrgs(Array.isArray(o) ? o : []);
      setAudit(Array.isArray(a) ? a : []);
      setSettings((prev) => ({
        ...prev,
        password_min_length: sys?.password_min_length ?? prev.password_min_length,
        mfa_required_for_admins: Boolean(sys?.mfa_required_for_admins),
        audit_retention_days: sys?.audit_retention_days ?? prev.audit_retention_days,
      }));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load admin console');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (canAdmin) load();
  }, [canAdmin]);

  const roleOptions = useMemo(() => ['admin', 'manager', 'agent', 'analyst'], []);

  const onChangeRole = async (userId, role) => {
    try {
      await updateUserRole(userId, role);
      toast.success('Role updated');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to update role');
    }
  };

  const onMoveOrg = async (userId, orgId) => {
    try {
      await moveUserToOrg(orgId, userId);
      toast.success('User moved to organization');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to move user');
    }
  };

  const onCreateOrg = async () => {
    const name = newOrgName.trim();
    if (!name) return;
    try {
      await createOrg(name);
      setNewOrgName('');
      toast.success('Organization created');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to create org');
    }
  };

  const onAuditFilter = async () => {
    try {
      const data = await queryAuditEvents({ action: auditAction || undefined, limit: 200 });
      setAudit(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to query audit');
    }
  };

  const parseBulkIds = () => (bulkUserIds || '').split(',').map((x) => x.trim()).filter(Boolean);

  const onBulkAction = async (action) => {
    try {
      const user_ids = parseBulkIds();
      const payload = { user_ids, action };
      if (action === 'reset_password') payload.new_password = bulkPassword;
      const res = await bulkUserAction(payload);
      toast.success(`Bulk action complete (${res.modified} modified)`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bulk action failed');
    }
  };

  const onExportAudit = async () => {
    try {
      const blob = await exportAuditCsv({ action: auditAction || undefined, limit: 2000 });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_export_${Date.now()}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Audit CSV exported');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to export audit CSV');
    }
  };

  const onSavePolicy = async () => {
    try {
      await updateSystemSettings({
        password_min_length: Number(settings.password_min_length || 8),
        mfa_required_for_admins: Boolean(settings.mfa_required_for_admins),
        audit_retention_days: Number(settings.audit_retention_days || 90),
      });
      toast.success('Policy settings saved');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save policy');
    }
  };

  if (!canAdmin) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-heading font-bold">Admin Console</h1>
        <p className="text-muted-foreground">Admin access is required.</p>
      </div>
    );
  }

  if (loading) {
    return <div className="text-muted-foreground">Loading admin console...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Admin Console</h1>
          <p className="text-muted-foreground mt-1">End-to-end administration, governance, and compliance</p>
        </div>
        <Button variant="outline" onClick={load}>Refresh</Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Users</p><p className="text-2xl font-bold">{summary?.users?.total ?? 0}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Feedback</p><p className="text-2xl font-bold">{summary?.feedback?.total ?? 0}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Cases</p><p className="text-2xl font-bold">{summary?.cases?.total ?? 0}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Open Cases</p><p className="text-2xl font-bold">{summary?.cases?.open_like ?? 0}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Audit (24h)</p><p className="text-2xl font-bold">{summary?.audit?.events_last_24h ?? 0}</p></CardContent></Card>
      </div>

      <Tabs defaultValue="users" className="w-full">
        <TabsList>
          <TabsTrigger value="users">Users & Roles</TabsTrigger>
          <TabsTrigger value="orgs">Organizations</TabsTrigger>
          <TabsTrigger value="audit">Audit & Compliance</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-3">
          <Card>
            <CardHeader><CardTitle>Bulk user actions</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              <Label>User IDs (comma separated)</Label>
              <Input value={bulkUserIds} onChange={(e) => setBulkUserIds(e.target.value)} placeholder="id1,id2,id3" />
              <Label>New password (for reset only)</Label>
              <Input value={bulkPassword} onChange={(e) => setBulkPassword(e.target.value)} placeholder="NewPassword@123" />
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => onBulkAction('activate')}>Activate</Button>
                <Button variant="outline" onClick={() => onBulkAction('deactivate')}>Deactivate</Button>
                <Button onClick={() => onBulkAction('reset_password')}>Reset Password</Button>
              </div>
            </CardContent>
          </Card>
          {users.map((u) => (
            <Card key={u.id}>
              <CardContent className="p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                  <p className="font-medium">{u.name}</p>
                  <p className="text-sm text-muted-foreground">{u.email}</p>
                  <p className="text-xs text-muted-foreground break-all">id: {u.id}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <Badge variant="outline">{u.role}</Badge>
                    <Badge variant="outline">org: {u.org_id || 'default'}</Badge>
                    <Badge variant="outline">{u.is_active === false ? 'inactive' : 'active'}</Badge>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Select value={u.role} onValueChange={(v) => onChangeRole(u.id, v)}>
                    <SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {roleOptions.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Select value={u.org_id || 'default'} onValueChange={(orgId) => onMoveOrg(u.id, orgId)}>
                    <SelectTrigger className="w-[190px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {orgs.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="orgs" className="space-y-3">
          <Card>
            <CardHeader><CardTitle>Create Organization</CardTitle></CardHeader>
            <CardContent className="flex gap-2">
              <Input value={newOrgName} onChange={(e) => setNewOrgName(e.target.value)} placeholder="Organization name" />
              <Button onClick={onCreateOrg}>Create</Button>
            </CardContent>
          </Card>
          {orgs.map((o) => (
            <Card key={o.id}>
              <CardContent className="p-4">
                <p className="font-medium">{o.name}</p>
                <p className="text-sm text-muted-foreground">id: {o.id}</p>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="audit" className="space-y-3">
          <Card>
            <CardContent className="p-4 flex flex-col md:flex-row gap-3">
              <div className="space-y-1">
                <Label>Action filter</Label>
                <Input value={auditAction} onChange={(e) => setAuditAction(e.target.value)} placeholder="e.g. user_role_change" />
              </div>
              <div className="flex items-end">
                <Button variant="outline" onClick={onAuditFilter}>Filter</Button>
              </div>
              <div className="flex items-end">
                <Button onClick={onExportAudit}>Export CSV</Button>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Policy controls</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label>Password min length</Label>
                <Input
                  type="number"
                  value={String(settings.password_min_length)}
                  onChange={(e) => setSettings((s) => ({ ...s, password_min_length: Number(e.target.value || 8) }))}
                />
              </div>
              <div className="space-y-1">
                <Label>Audit retention days</Label>
                <Input
                  type="number"
                  value={String(settings.audit_retention_days)}
                  onChange={(e) => setSettings((s) => ({ ...s, audit_retention_days: Number(e.target.value || 90) }))}
                />
              </div>
              <div className="space-y-1">
                <Label>MFA required for admins</Label>
                <Select
                  value={settings.mfa_required_for_admins ? 'true' : 'false'}
                  onValueChange={(v) => setSettings((s) => ({ ...s, mfa_required_for_admins: v === 'true' }))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="false">false</SelectItem>
                    <SelectItem value="true">true</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-3">
                <Button onClick={onSavePolicy}>Save policy settings</Button>
              </div>
            </CardContent>
          </Card>
          {audit.map((ev) => (
            <Card key={ev.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{ev.action}</p>
                  <Badge variant="outline">{ev.resource_type}</Badge>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {ev.actor_email || ev.actor_id || 'system'} • {new Date(ev.ts).toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {ev.method || '-'} {ev.path || '-'} • status {ev.status ?? '-'}
                </p>
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
};

