import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Progress } from '../components/ui/progress';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { 
  UserCircle,
  Lightning,
  Briefcase,
  ChartBar,
  Star,
  Clock,
  CheckCircle,
  Gear,
  Plus,
  X
} from '@phosphor-icons/react';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SKILL_LABELS = {
  technical_support: 'Technical Support',
  billing: 'Billing & Payments',
  product_issues: 'Product Issues',
  general_inquiry: 'General Inquiry',
  complaints: 'Complaints',
  feature_requests: 'Feature Requests',
  security: 'Security',
  shipping: 'Shipping & Delivery',
  returns: 'Returns & Refunds',
  account_management: 'Account Management'
};

export const AgentsPage = () => {
  const [agents, setAgents] = useState([]);
  const [availableSkills, setAvailableSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [editingProfile, setEditingProfile] = useState(null);
  const [saving, setSaving] = useState(false);
  const { user: currentUser } = useAuth();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [agentsRes, skillsRes] = await Promise.all([
        axios.get(`${API_URL}/agents/profiles`),
        axios.get(`${API_URL}/agents/skills`)
      ]);
      setAgents(agentsRes.data);
      setAvailableSkills(skillsRes.data.skills);
    } catch (error) {
      toast.error('Failed to fetch agents data');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateProfile = async () => {
    if (!editingProfile) return;
    setSaving(true);
    try {
      await axios.put(`${API_URL}/agents/profiles/${editingProfile.user_id}`, {
        skills: editingProfile.skills,
        max_workload: editingProfile.max_workload,
        is_available: editingProfile.is_available,
        shift_start: editingProfile.shift_start,
        shift_end: editingProfile.shift_end
      });
      toast.success('Agent profile updated');
      setSelectedAgent(null);
      setEditingProfile(null);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const toggleSkill = (skill) => {
    if (!editingProfile) return;
    const skills = editingProfile.skills || [];
    if (skills.includes(skill)) {
      setEditingProfile({
        ...editingProfile,
        skills: skills.filter(s => s !== skill)
      });
    } else {
      setEditingProfile({
        ...editingProfile,
        skills: [...skills, skill]
      });
    }
  };

  const getWorkloadColor = (current, max) => {
    const ratio = current / max;
    if (ratio < 0.5) return 'bg-emerald-500';
    if (ratio < 0.8) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  const openEditDialog = (agent) => {
    setSelectedAgent(agent);
    setEditingProfile({
      user_id: agent.id,
      skills: agent.profile?.skills || [],
      max_workload: agent.profile?.max_workload || 10,
      is_available: agent.profile?.is_available ?? true,
      shift_start: agent.profile?.shift_start || '09:00',
      shift_end: agent.profile?.shift_end || '17:00'
    });
  };

  return (
    <div className="space-y-6" data-testid="agents-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Smart Routing</h1>
          <p className="text-muted-foreground mt-1">Manage agent skills, workload, and AI-powered case assignment</p>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Agents</p>
                <p className="text-3xl font-heading font-bold mt-1">{agents.length}</p>
              </div>
              <div className="p-3 bg-indigo-50 rounded-lg">
                <UserCircle size={24} weight="duotone" className="text-indigo-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Available</p>
                <p className="text-3xl font-heading font-bold mt-1">
                  {agents.filter(a => a.profile?.is_available).length}
                </p>
              </div>
              <div className="p-3 bg-emerald-50 rounded-lg">
                <CheckCircle size={24} weight="duotone" className="text-emerald-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Workload</p>
                <p className="text-3xl font-heading font-bold mt-1">
                  {agents.reduce((sum, a) => sum + (a.profile?.current_workload || 0), 0)}
                </p>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <Briefcase size={24} weight="duotone" className="text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Avg Satisfaction</p>
                <p className="text-3xl font-heading font-bold mt-1">
                  {agents.length > 0 
                    ? (agents.reduce((sum, a) => sum + (a.profile?.satisfaction_score || 0), 0) / agents.length).toFixed(1)
                    : '0'}
                </p>
              </div>
              <div className="p-3 bg-violet-50 rounded-lg">
                <Star size={24} weight="duotone" className="text-violet-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agents Table */}
      <Card className="dashboard-card">
        <CardHeader>
          <CardTitle className="font-heading flex items-center gap-2">
            <Lightning size={20} weight="duotone" className="text-indigo-600" />
            Agent Profiles & Skills
          </CardTitle>
          <CardDescription>
            Configure agent skills for AI-powered smart routing
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead>Skills</TableHead>
                <TableHead>Workload</TableHead>
                <TableHead>Performance</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Loading...
                  </TableCell>
                </TableRow>
              ) : agents.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    <UserCircle size={48} className="mx-auto mb-2 opacity-50" />
                    No agents found. Create users with 'agent' or 'manager' role.
                  </TableCell>
                </TableRow>
              ) : (
                agents.map((agent) => {
                  const profile = agent.profile || {};
                  const workloadPercent = (profile.current_workload || 0) / (profile.max_workload || 10) * 100;
                  
                  return (
                    <TableRow key={agent.id} className="hover:bg-slate-50">
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                            <UserCircle size={24} className="text-indigo-600" />
                          </div>
                          <div>
                            <p className="font-medium">{agent.name}</p>
                            <p className="text-sm text-muted-foreground">{agent.email}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                          {(profile.skills || []).slice(0, 3).map((skill) => (
                            <Badge key={skill} variant="secondary" className="text-xs">
                              {SKILL_LABELS[skill] || skill}
                            </Badge>
                          ))}
                          {(profile.skills || []).length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{profile.skills.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="w-32">
                          <div className="flex items-center justify-between text-sm mb-1">
                            <span>{profile.current_workload || 0}/{profile.max_workload || 10}</span>
                          </div>
                          <Progress 
                            value={workloadPercent} 
                            className={`h-2 ${getWorkloadColor(profile.current_workload || 0, profile.max_workload || 10)}`}
                          />
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-1 text-sm">
                            <Star size={14} weight="fill" className="text-amber-400" />
                            <span>{(profile.satisfaction_score || 0).toFixed(1)}/5</span>
                          </div>
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Clock size={14} />
                            <span>{(profile.avg_resolution_time || 0).toFixed(0)}h avg</span>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge 
                          variant="outline" 
                          className={profile.is_available ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-50 text-slate-500'}
                        >
                          {profile.is_available ? 'Available' : 'Unavailable'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(agent)}
                            data-testid={`edit-agent-${agent.id}`}
                          >
                            <Gear size={16} />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Edit Agent Profile Dialog */}
      <Dialog open={!!selectedAgent} onOpenChange={() => { setSelectedAgent(null); setEditingProfile(null); }}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">
              Edit Agent Profile: {selectedAgent?.name}
            </DialogTitle>
          </DialogHeader>
          {editingProfile && (
            <div className="space-y-6 mt-4">
              {/* Availability */}
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <Label>Availability Status</Label>
                  <p className="text-sm text-muted-foreground">Agent can receive new case assignments</p>
                </div>
                <Switch
                  checked={editingProfile.is_available}
                  onCheckedChange={(v) => setEditingProfile({ ...editingProfile, is_available: v })}
                  data-testid="agent-availability-switch"
                />
              </div>

              {/* Workload Capacity */}
              <div className="space-y-2">
                <Label>Maximum Workload Capacity</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={editingProfile.max_workload}
                  onChange={(e) => setEditingProfile({ ...editingProfile, max_workload: parseInt(e.target.value) || 10 })}
                  data-testid="agent-max-workload-input"
                />
                <p className="text-sm text-muted-foreground">Maximum number of cases this agent can handle simultaneously</p>
              </div>

              {/* Shift Hours */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Shift Start</Label>
                  <Input
                    type="time"
                    value={editingProfile.shift_start || '09:00'}
                    onChange={(e) => setEditingProfile({ ...editingProfile, shift_start: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Shift End</Label>
                  <Input
                    type="time"
                    value={editingProfile.shift_end || '17:00'}
                    onChange={(e) => setEditingProfile({ ...editingProfile, shift_end: e.target.value })}
                  />
                </div>
              </div>

              {/* Skills */}
              <div className="space-y-3">
                <Label>Skills & Expertise</Label>
                <p className="text-sm text-muted-foreground">Select all skills this agent can handle. Smart routing will match cases based on these skills.</p>
                <div className="grid grid-cols-2 gap-2">
                  {availableSkills.map((skill) => {
                    const isSelected = (editingProfile.skills || []).includes(skill.value);
                    return (
                      <button
                        key={skill.value}
                        type="button"
                        onClick={() => toggleSkill(skill.value)}
                        className={`p-3 rounded-lg border text-left transition-all ${
                          isSelected 
                            ? 'border-indigo-500 bg-indigo-50 text-indigo-700' 
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                        data-testid={`skill-${skill.value}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{skill.label}</span>
                          {isSelected && <CheckCircle size={18} weight="fill" className="text-indigo-600" />}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button variant="outline" onClick={() => { setSelectedAgent(null); setEditingProfile(null); }}>
                  Cancel
                </Button>
                <Button 
                  className="bg-indigo-600 hover:bg-indigo-700"
                  onClick={handleUpdateProfile}
                  disabled={saving}
                  data-testid="save-agent-profile-btn"
                >
                  {saving ? 'Saving...' : 'Save Profile'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
