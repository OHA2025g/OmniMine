import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { getUsers, updateUserRole, getTeams, createTeam, addTeamMember } from '../services/api';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { 
  Users, 
  UserCircle,
  Plus,
  UsersThree,
  ShieldCheck,
  Gear,
  Globe,
  TwitterLogo,
  FacebookLogo,
  YoutubeLogo,
  LinkedinLogo,
  Bell,
  EnvelopeSimple,
  Clock,
  FloppyDisk,
  FileArrowDown,
  FilePdf,
  FileCsv
} from '@phosphor-icons/react';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const SettingsPage = () => {
  const [users, setUsers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddTeamDialog, setShowAddTeamDialog] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newTeamDesc, setNewTeamDesc] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { user: currentUser } = useAuth();
  
  // System Settings
  const [systemSettings, setSystemSettings] = useState({
    organization_name: 'OmniMine',
    notification_email: '',
    email_alerts_enabled: false,
    sla_critical_hours: 4,
    sla_high_hours: 8,
    sla_medium_hours: 24,
    sla_low_hours: 72
  });
  
  // Social Media Configs
  const [socialConfigs, setSocialConfigs] = useState({
    twitter: { profile_url: '', api_key: '', enabled: false },
    facebook: { profile_url: '', api_key: '', enabled: false },
    youtube: { profile_url: '', api_key: '', enabled: false },
    linkedin: { profile_url: '', api_key: '', enabled: false }
  });

  const [savingSettings, setSavingSettings] = useState(false);
  const [savingSocial, setSavingSocial] = useState(null);

  useEffect(() => {
    fetchData();
    fetchSystemSettings();
    fetchSocialConfigs();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [usersData, teamsData] = await Promise.all([
        getUsers(),
        getTeams()
      ]);
      setUsers(usersData);
      setTeams(teamsData);
    } catch (error) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  const fetchSystemSettings = async () => {
    try {
      const response = await axios.get(`${API_URL}/settings/system`);
      setSystemSettings(prev => ({ ...prev, ...response.data }));
    } catch (error) {
      console.error('Failed to fetch system settings');
    }
  };

  const fetchSocialConfigs = async () => {
    try {
      const response = await axios.get(`${API_URL}/settings/social`);
      if (response.data.social_configs) {
        setSocialConfigs(prev => ({
          ...prev,
          ...response.data.social_configs
        }));
      }
    } catch (error) {
      console.error('Failed to fetch social configs');
    }
  };

  const handleSaveSystemSettings = async () => {
    setSavingSettings(true);
    try {
      await axios.put(`${API_URL}/settings/system`, systemSettings);
      toast.success('System settings saved');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleSaveSocialConfig = async (platform) => {
    setSavingSocial(platform);
    try {
      await axios.put(`${API_URL}/settings/social/${platform}`, {
        platform,
        ...socialConfigs[platform]
      });
      toast.success(`${platform} configuration saved`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save configuration');
    } finally {
      setSavingSocial(null);
    }
  };

  const handleExport = async (type, format) => {
    try {
      const response = await axios.post(
        `${API_URL}/export/${type}/${format}`,
        {},
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `omnimine_${type}_${new Date().toISOString().split('T')[0]}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success(`${type} exported successfully`);
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const handleTriggerSLACheck = async () => {
    try {
      const response = await axios.post(`${API_URL}/sla/check`);
      toast.success(response.data.message);
    } catch (error) {
      toast.error('SLA check failed');
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      await updateUserRole(userId, newRole);
      setUsers(users.map(u => u.id === userId ? { ...u, role: newRole } : u));
      toast.success('Role updated');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update role');
    }
  };

  const handleCreateTeam = async () => {
    if (!newTeamName.trim()) {
      toast.error('Please enter a team name');
      return;
    }
    setSubmitting(true);
    try {
      await createTeam(newTeamName, newTeamDesc);
      toast.success('Team created');
      setShowAddTeamDialog(false);
      setNewTeamName('');
      setNewTeamDesc('');
      fetchData();
    } catch (error) {
      toast.error('Failed to create team');
    } finally {
      setSubmitting(false);
    }
  };

  const getRoleBadge = (role) => {
    const classes = {
      admin: 'bg-purple-100 text-purple-700',
      manager: 'bg-blue-100 text-blue-700',
      agent: 'bg-emerald-100 text-emerald-700',
      analyst: 'bg-slate-100 text-slate-700'
    };
    return <Badge className={classes[role]}>{role}</Badge>;
  };

  const socialPlatforms = [
    { key: 'twitter', name: 'Twitter/X', icon: TwitterLogo, color: 'text-sky-500' },
    { key: 'facebook', name: 'Facebook', icon: FacebookLogo, color: 'text-blue-600' },
    { key: 'youtube', name: 'YouTube', icon: YoutubeLogo, color: 'text-red-500' },
    { key: 'linkedin', name: 'LinkedIn', icon: LinkedinLogo, color: 'text-blue-700' }
  ];

  return (
    <div className="space-y-6" data-testid="settings-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-heading font-bold text-slate-900">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage users, teams, integrations, and system configuration</p>
      </div>

      <Tabs defaultValue="general" className="space-y-6">
        <TabsList>
          <TabsTrigger value="general" className="flex items-center gap-2">
            <Gear size={16} /> General
          </TabsTrigger>
          <TabsTrigger value="social" className="flex items-center gap-2">
            <Globe size={16} /> Social Media
          </TabsTrigger>
          <TabsTrigger value="users" className="flex items-center gap-2">
            <Users size={16} /> Users
          </TabsTrigger>
          <TabsTrigger value="teams" className="flex items-center gap-2">
            <UsersThree size={16} /> Teams
          </TabsTrigger>
          <TabsTrigger value="export" className="flex items-center gap-2">
            <FileArrowDown size={16} /> Export
          </TabsTrigger>
        </TabsList>

        {/* General Settings Tab */}
        <TabsContent value="general">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Organization Settings */}
            <Card className="dashboard-card">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Gear size={20} weight="duotone" className="text-indigo-600" />
                  Organization Settings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Organization Name</Label>
                  <Input
                    value={systemSettings.organization_name}
                    onChange={(e) => setSystemSettings({ ...systemSettings, organization_name: e.target.value })}
                    data-testid="org-name-input"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Email Notifications */}
            <Card className="dashboard-card">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <EnvelopeSimple size={20} weight="duotone" className="text-indigo-600" />
                  Email Notifications
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Enable Email Alerts</Label>
                    <p className="text-sm text-muted-foreground">Receive emails for negative feedback and SLA breaches</p>
                  </div>
                  <Switch
                    checked={systemSettings.email_alerts_enabled}
                    onCheckedChange={(v) => setSystemSettings({ ...systemSettings, email_alerts_enabled: v })}
                    data-testid="email-alerts-switch"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Notification Email</Label>
                  <Input
                    type="email"
                    placeholder="alerts@company.com"
                    value={systemSettings.notification_email || ''}
                    onChange={(e) => setSystemSettings({ ...systemSettings, notification_email: e.target.value })}
                    data-testid="notification-email-input"
                  />
                </div>
              </CardContent>
            </Card>

            {/* SLA Configuration */}
            <Card className="dashboard-card lg:col-span-2">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="font-heading flex items-center gap-2">
                    <Clock size={20} weight="duotone" className="text-indigo-600" />
                    SLA Configuration
                  </CardTitle>
                  <CardDescription>Set response time targets for different priority levels</CardDescription>
                </div>
                <Button variant="outline" onClick={handleTriggerSLACheck} data-testid="check-sla-btn">
                  Check SLA Breaches
                </Button>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Badge className="bg-red-100 text-red-700">Critical</Badge>
                    </Label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        value={systemSettings.sla_critical_hours}
                        onChange={(e) => setSystemSettings({ ...systemSettings, sla_critical_hours: parseInt(e.target.value) })}
                        className="w-20"
                      />
                      <span className="text-sm text-muted-foreground">hours</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Badge className="bg-orange-100 text-orange-700">High</Badge>
                    </Label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        value={systemSettings.sla_high_hours}
                        onChange={(e) => setSystemSettings({ ...systemSettings, sla_high_hours: parseInt(e.target.value) })}
                        className="w-20"
                      />
                      <span className="text-sm text-muted-foreground">hours</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Badge className="bg-amber-100 text-amber-700">Medium</Badge>
                    </Label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        value={systemSettings.sla_medium_hours}
                        onChange={(e) => setSystemSettings({ ...systemSettings, sla_medium_hours: parseInt(e.target.value) })}
                        className="w-20"
                      />
                      <span className="text-sm text-muted-foreground">hours</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Badge className="bg-blue-100 text-blue-700">Low</Badge>
                    </Label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        value={systemSettings.sla_low_hours}
                        onChange={(e) => setSystemSettings({ ...systemSettings, sla_low_hours: parseInt(e.target.value) })}
                        className="w-20"
                      />
                      <span className="text-sm text-muted-foreground">hours</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="flex justify-end mt-6">
            <Button 
              className="bg-indigo-600 hover:bg-indigo-700"
              onClick={handleSaveSystemSettings}
              disabled={savingSettings}
              data-testid="save-settings-btn"
            >
              <FloppyDisk size={18} className="mr-2" />
              {savingSettings ? 'Saving...' : 'Save Settings'}
            </Button>
          </div>
        </TabsContent>

        {/* Social Media Tab */}
        <TabsContent value="social">
          <Card className="dashboard-card">
            <CardHeader>
              <CardTitle className="font-heading flex items-center gap-2">
                <Globe size={20} weight="duotone" className="text-indigo-600" />
                Social Media Integrations
              </CardTitle>
              <CardDescription>
                Configure your social media profiles and API credentials for feedback ingestion
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {socialPlatforms.map((platform) => {
                const Icon = platform.icon;
                const config = socialConfigs[platform.key] || {};
                
                return (
                  <div key={platform.key} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <Icon size={28} weight="fill" className={platform.color} />
                        <div>
                          <h3 className="font-semibold">{platform.name}</h3>
                          <p className="text-sm text-muted-foreground">
                            {config.enabled ? 'Connected' : 'Not connected'}
                          </p>
                        </div>
                      </div>
                      <Switch
                        checked={config.enabled || false}
                        onCheckedChange={(v) => setSocialConfigs({
                          ...socialConfigs,
                          [platform.key]: { ...config, enabled: v }
                        })}
                        data-testid={`${platform.key}-enabled-switch`}
                      />
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Profile/Page URL</Label>
                        <Input
                          placeholder={`https://${platform.key}.com/yourprofile`}
                          value={config.profile_url || ''}
                          onChange={(e) => setSocialConfigs({
                            ...socialConfigs,
                            [platform.key]: { ...config, profile_url: e.target.value }
                          })}
                          data-testid={`${platform.key}-url-input`}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>API Key (Optional)</Label>
                        <Input
                          type="password"
                          placeholder="Enter API key for live ingestion"
                          value={config.api_key || ''}
                          onChange={(e) => setSocialConfigs({
                            ...socialConfigs,
                            [platform.key]: { ...config, api_key: e.target.value }
                          })}
                          data-testid={`${platform.key}-api-input`}
                        />
                      </div>
                    </div>
                    
                    <div className="flex justify-end mt-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleSaveSocialConfig(platform.key)}
                        disabled={savingSocial === platform.key}
                        data-testid={`save-${platform.key}-btn`}
                      >
                        {savingSocial === platform.key ? 'Saving...' : 'Save'}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Users Tab */}
        <TabsContent value="users">
          <Card className="dashboard-card">
            <CardHeader>
              <CardTitle className="font-heading flex items-center gap-2">
                <ShieldCheck size={20} weight="duotone" className="text-indigo-600" />
                User Management
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Joined</TableHead>
                    {currentUser?.role === 'admin' && <TableHead>Actions</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        Loading...
                      </TableCell>
                    </TableRow>
                  ) : users.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        No users found
                      </TableCell>
                    </TableRow>
                  ) : (
                    users.map((user) => (
                      <TableRow key={user.id} className="hover:bg-slate-50">
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                              <UserCircle size={20} className="text-indigo-600" />
                            </div>
                            <span className="font-medium">{user.name}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{user.email}</TableCell>
                        <TableCell>{getRoleBadge(user.role)}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className={user.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-50 text-slate-700'}>
                            {user.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(user.created_at).toLocaleDateString()}
                        </TableCell>
                        {currentUser?.role === 'admin' && (
                          <TableCell>
                            {user.id !== currentUser.id && (
                              <Select 
                                value={user.role} 
                                onValueChange={(v) => handleRoleChange(user.id, v)}
                              >
                                <SelectTrigger className="w-[120px]" data-testid={`role-select-${user.id}`}>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="analyst">Analyst</SelectItem>
                                  <SelectItem value="agent">Agent</SelectItem>
                                  <SelectItem value="manager">Manager</SelectItem>
                                  <SelectItem value="admin">Admin</SelectItem>
                                </SelectContent>
                              </Select>
                            )}
                          </TableCell>
                        )}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Teams Tab */}
        <TabsContent value="teams">
          <div className="flex justify-end mb-4">
            <Dialog open={showAddTeamDialog} onOpenChange={setShowAddTeamDialog}>
              <DialogTrigger asChild>
                <Button className="bg-indigo-600 hover:bg-indigo-700" data-testid="add-team-btn">
                  <Plus size={18} className="mr-2" />
                  Create Team
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="font-heading">Create New Team</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label>Team Name</Label>
                    <Input
                      placeholder="e.g., Customer Support"
                      value={newTeamName}
                      onChange={(e) => setNewTeamName(e.target.value)}
                      data-testid="team-name-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Description (optional)</Label>
                    <Input
                      placeholder="Team description..."
                      value={newTeamDesc}
                      onChange={(e) => setNewTeamDesc(e.target.value)}
                      data-testid="team-desc-input"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowAddTeamDialog(false)}>Cancel</Button>
                    <Button 
                      className="bg-indigo-600 hover:bg-indigo-700"
                      onClick={handleCreateTeam}
                      disabled={submitting}
                      data-testid="create-team-btn"
                    >
                      {submitting ? 'Creating...' : 'Create'}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {teams.length === 0 ? (
              <Card className="dashboard-card col-span-full">
                <CardContent className="p-8 text-center">
                  <UsersThree size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground">No teams created yet</p>
                </CardContent>
              </Card>
            ) : (
              teams.map((team) => (
                <Card key={team.id} className="dashboard-card">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-semibold text-lg">{team.name}</h3>
                        {team.description && (
                          <p className="text-sm text-muted-foreground mt-1">{team.description}</p>
                        )}
                      </div>
                      <div className="p-2 bg-indigo-50 rounded-lg">
                        <UsersThree size={20} className="text-indigo-600" />
                      </div>
                    </div>
                    <div className="mt-4 pt-4 border-t">
                      <p className="text-sm text-muted-foreground">
                        {team.members?.length || 0} members
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        {/* Export Tab */}
        <TabsContent value="export">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Card className="dashboard-card">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <FileCsv size={20} weight="duotone" className="text-emerald-600" />
                  Export Feedback
                </CardTitle>
                <CardDescription>Download all feedback data as CSV</CardDescription>
              </CardHeader>
              <CardContent>
                <Button 
                  className="w-full bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => handleExport('feedback', 'csv')}
                  data-testid="export-feedback-csv-btn"
                >
                  <FileArrowDown size={18} className="mr-2" />
                  Download CSV
                </Button>
              </CardContent>
            </Card>

            <Card className="dashboard-card">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <FileCsv size={20} weight="duotone" className="text-blue-600" />
                  Export Cases
                </CardTitle>
                <CardDescription>Download all cases data as CSV</CardDescription>
              </CardHeader>
              <CardContent>
                <Button 
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  onClick={() => handleExport('cases', 'csv')}
                  data-testid="export-cases-csv-btn"
                >
                  <FileArrowDown size={18} className="mr-2" />
                  Download CSV
                </Button>
              </CardContent>
            </Card>

            <Card className="dashboard-card">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <FilePdf size={20} weight="duotone" className="text-rose-600" />
                  Analytics Report
                </CardTitle>
                <CardDescription>Download analytics summary as PDF</CardDescription>
              </CardHeader>
              <CardContent>
                <Button 
                  className="w-full bg-rose-600 hover:bg-rose-700"
                  onClick={() => handleExport('analytics', 'pdf')}
                  data-testid="export-analytics-pdf-btn"
                >
                  <FileArrowDown size={18} className="mr-2" />
                  Download PDF
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};
