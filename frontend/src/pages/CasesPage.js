import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { getCases, getCase, assignCase, startCaseWork, resolveCase, verifyCase, uploadCaseEvidence, getCaseLogs, getUsers, getFeedback, agenticTriageFeedback, agenticResponseDraft, startCaseOrchestration, decideOrchestrationGate } from '../services/api';
import { toast } from 'sonner';
import axios from 'axios';
import { 
  MagnifyingGlass, 
  FunnelSimple, 
  Eye,
  UserCircle,
  CheckCircle,
  Clock,
  Warning,
  FolderOpen,
  Lightning,
  Robot,
  Sparkle
} from '@phosphor-icons/react';
import { useAuth } from '../context/AuthContext';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const CasesPage = () => {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [selectedCase, setSelectedCase] = useState(null);
  const [caseLogs, setCaseLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [relatedFeedback, setRelatedFeedback] = useState(null);
  const [showAssignDialog, setShowAssignDialog] = useState(false);
  const [showResolveDialog, setShowResolveDialog] = useState(false);
  const [showSmartRoutingDialog, setShowSmartRoutingDialog] = useState(false);
  const [routingResult, setRoutingResult] = useState(null);
  const [routingLoading, setRoutingLoading] = useState(false);
  const [assigneeId, setAssigneeId] = useState('');
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [showStartDialog, setShowStartDialog] = useState(false);
  const [showVerifyDialog, setShowVerifyDialog] = useState(false);
  const [verificationRating, setVerificationRating] = useState(5);
  const [verificationComments, setVerificationComments] = useState('');
  const [evidenceFile, setEvidenceFile] = useState(null);
  const [evidenceNote, setEvidenceNote] = useState('');
  const [aiTriage, setAiTriage] = useState(null);
  const [aiDraft, setAiDraft] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [orchestrationRun, setOrchestrationRun] = useState(null);
  const [orchestrationLoading, setOrchestrationLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { user } = useAuth();
  const location = useLocation();

  useEffect(() => {
    fetchCases();
    fetchUsers();
  }, [statusFilter, priorityFilter]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const caseId = params.get('case_id');
    if (!caseId) return;
    (async () => {
      try {
        const caseItem = await getCase(caseId);
        handleViewCase(caseItem);
      } catch (e) {
        // ignore
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  const fetchCases = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (priorityFilter !== 'all') params.priority = priorityFilter;
      const data = await getCases(params);
      setCases(data);
    } catch (error) {
      toast.error('Failed to fetch cases');
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const data = await getUsers();
      setUsers(data);
    } catch (error) {
      console.error('Failed to fetch users');
    }
  };

  const handleSmartRouting = async (caseItem) => {
    setSelectedCase(caseItem);
    setShowSmartRoutingDialog(true);
    setRoutingLoading(true);
    setRoutingResult(null);
    
    try {
      const response = await axios.post(`${API_URL}/routing/analyze/${caseItem.id}`);
      setRoutingResult(response.data);
    } catch (error) {
      toast.error('Failed to analyze case for routing');
    } finally {
      setRoutingLoading(false);
    }
  };

  const handleAutoAssign = async () => {
    if (!selectedCase) return;
    setSubmitting(true);
    try {
      const response = await axios.post(`${API_URL}/routing/auto-assign/${selectedCase.id}`);
      toast.success(`Case assigned to ${response.data.agent_name}`);
      setShowSmartRoutingDialog(false);
      setRoutingResult(null);
      fetchCases();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Auto-assignment failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleViewCase = async (caseItem) => {
    setSelectedCase(caseItem);
    setAiTriage(null);
    setAiDraft(null);
    try {
      const [logs, feedback] = await Promise.all([
        getCaseLogs(caseItem.id),
        getFeedback(caseItem.feedback_id)
      ]);
      setCaseLogs(logs);
      setRelatedFeedback(feedback);
    } catch (error) {
      console.error('Failed to fetch case details');
    }
  };

  const handleAiTriage = async () => {
    if (!relatedFeedback?.id) return;
    setAiLoading(true);
    try {
      const res = await agenticTriageFeedback(relatedFeedback.id);
      setAiTriage(res);
      toast.success('AI triage generated');
      fetchCases();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to run AI triage');
    } finally {
      setAiLoading(false);
    }
  };

  const handleAiDraft = async () => {
    if (!selectedCase?.id) return;
    setAiLoading(true);
    try {
      const res = await agenticResponseDraft(selectedCase.id);
      setAiDraft(res);
      toast.success('AI draft generated');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate draft');
    } finally {
      setAiLoading(false);
    }
  };

  const refreshSelectedCase = async () => {
    if (!selectedCase?.id) return;
    try {
      const fresh = await getCase(selectedCase.id);
      await handleViewCase(fresh);
      fetchCases();
    } catch (e) {
      // ignore
    }
  };

  const handleStartOrchestration = async () => {
    if (!selectedCase?.id) return;
    setOrchestrationLoading(true);
    try {
      const run = await startCaseOrchestration(selectedCase.id);
      setOrchestrationRun(run);
      toast.message('Workflow started', { description: 'Running until the next HITL gate.' });
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to start workflow');
    } finally {
      setOrchestrationLoading(false);
    }
  };

  const handleGateDecision = async (stepKey, decision) => {
    if (!orchestrationRun?.id) return;
    setOrchestrationLoading(true);
    try {
      const run = await decideOrchestrationGate(orchestrationRun.id, stepKey, decision);
      setOrchestrationRun(run);
      toast.success(decision === 'approve' ? 'Approved' : 'Rejected');
      await refreshSelectedCase();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to submit decision');
    } finally {
      setOrchestrationLoading(false);
    }
  };

  const handleAssign = async () => {
    if (!assigneeId) {
      toast.error('Please select an assignee');
      return;
    }
    setSubmitting(true);
    try {
      await assignCase(selectedCase.id, assigneeId);
      toast.success('Case assigned successfully');
      setShowAssignDialog(false);
      setAssigneeId('');
      fetchCases();
      handleViewCase({ ...selectedCase, assigned_to: assigneeId, status: 'assigned' });
    } catch (error) {
      toast.error('Failed to assign case');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolve = async () => {
    if (!resolutionNotes.trim()) {
      toast.error('Please enter resolution notes');
      return;
    }
    setSubmitting(true);
    try {
      await resolveCase(selectedCase.id, resolutionNotes);
      toast.success('Case resolved successfully');
      setShowResolveDialog(false);
      setResolutionNotes('');
      fetchCases();
      setSelectedCase(null);
    } catch (error) {
      toast.error('Failed to resolve case');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartWork = async () => {
    if (!selectedCase) return;
    setSubmitting(true);
    try {
      await startCaseWork(selectedCase.id);
      toast.success('Case marked as in progress');
      setShowStartDialog(false);
      fetchCases();
      handleViewCase({ ...selectedCase, status: 'in_progress' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to start work');
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerify = async () => {
    if (!selectedCase) return;
    setSubmitting(true);
    try {
      await verifyCase(selectedCase.id, {
        case_id: selectedCase.id,
        feedback_id: selectedCase.feedback_id,
        rating: verificationRating,
        comments: verificationComments,
      });
      toast.success('Verification recorded');
      setShowVerifyDialog(false);
      setVerificationComments('');
      setVerificationRating(5);
      fetchCases();
      setSelectedCase(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to record verification');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUploadEvidence = async () => {
    if (!selectedCase?.id) return;
    if (!evidenceFile) {
      toast.error('Please choose a file');
      return;
    }
    setSubmitting(true);
    try {
      await uploadCaseEvidence(selectedCase.id, evidenceFile, evidenceNote);
      toast.success('Evidence uploaded');
      setEvidenceFile(null);
      setEvidenceNote('');
      // refresh case + logs
      await handleViewCase(selectedCase);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to upload evidence');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    const config = {
      open: { className: 'status-open', icon: <FolderOpen size={14} /> },
      assigned: { className: 'status-in_progress', icon: <UserCircle size={14} /> },
      in_progress: { className: 'status-in_progress', icon: <Clock size={14} /> },
      resolved: { className: 'status-resolved', icon: <CheckCircle size={14} /> },
      verified: { className: 'status-resolved', icon: <CheckCircle size={14} /> },
      closed: { className: 'status-closed', icon: <CheckCircle size={14} /> },
      escalated: { className: 'status-escalated', icon: <Warning size={14} /> },
    };
    const c = config[status] || config.open;
    return (
      <Badge variant="outline" className={`${c.className} flex items-center gap-1`}>
        {c.icon} {status.replace('_', ' ')}
      </Badge>
    );
  };

  const getPriorityBadge = (priority) => {
    return <Badge variant="outline" className={`priority-${priority}`}>{priority}</Badge>;
  };

  const getSlaBadge = (caseItem) => {
    if (!caseItem?.due_date || caseItem.status === 'closed') return null;
    const due = new Date(caseItem.due_date).getTime();
    const now = Date.now();
    if (Number.isNaN(due)) return null;
    if (now > due) {
      return <Badge className="bg-red-100 text-red-700">Overdue</Badge>;
    }
    const hoursLeft = (due - now) / (1000 * 60 * 60);
    if (hoursLeft <= 4) {
      return <Badge className="bg-amber-100 text-amber-700">Due soon</Badge>;
    }
    return null;
  };

  const filteredCases = cases.filter(c => 
    c.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6" data-testid="cases-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Cases</h1>
          <p className="text-muted-foreground mt-1">Manage and resolve customer issues</p>
        </div>
      </div>

      {/* Filters */}
      <Card className="dashboard-card">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search cases..."
                  className="pl-10"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  data-testid="cases-search-input"
                />
              </div>
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]" data-testid="status-filter">
                <FunnelSimple size={16} className="mr-2" />
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="assigned">Assigned</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="verified">Verified</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
                <SelectItem value="escalated">Escalated</SelectItem>
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-[150px]" data-testid="priority-filter">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Cases Table */}
      <Card className="dashboard-card">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[35%]">Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Assigned To</TableHead>
                <TableHead>Due Date</TableHead>
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
              ) : filteredCases.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    <FolderOpen size={48} className="mx-auto mb-2 opacity-50" />
                    No cases found
                  </TableCell>
                </TableRow>
              ) : (
                filteredCases.map((caseItem) => (
                  <TableRow key={caseItem.id} className="hover:bg-slate-50">
                    <TableCell>
                      <p className="text-sm font-medium line-clamp-1">{caseItem.title}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Created {new Date(caseItem.created_at).toLocaleDateString()}
                      </p>
                    </TableCell>
                    <TableCell>{getStatusBadge(caseItem.status)}</TableCell>
                    <TableCell>{getPriorityBadge(caseItem.priority)}</TableCell>
                    <TableCell>
                      {caseItem.assigned_to ? (
                        <div className="flex items-center gap-2">
                          <UserCircle size={20} className="text-muted-foreground" />
                          <span className="text-sm">
                            {users.find(u => u.id === caseItem.assigned_to)?.name || 'Unknown'}
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">Unassigned</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <span>{caseItem.due_date ? new Date(caseItem.due_date).toLocaleDateString() : '-'}</span>
                        {getSlaBadge(caseItem)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        {!caseItem.assigned_to && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSmartRouting(caseItem)}
                            title="Smart Routing"
                            className="text-indigo-600"
                            data-testid={`smart-route-${caseItem.id}`}
                          >
                            <Lightning size={16} weight="fill" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewCase(caseItem)}
                          data-testid={`view-case-${caseItem.id}`}
                        >
                          <Eye size={16} />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Case Detail Dialog */}
      <Dialog open={!!selectedCase} onOpenChange={() => setSelectedCase(null)}>
        <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">Case Details</DialogTitle>
          </DialogHeader>
          {selectedCase && (
            <div className="space-y-6 mt-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-lg">{selectedCase.title}</h3>
                  <div className="flex items-center gap-2 mt-2">
                    {getStatusBadge(selectedCase.status)}
                    {getPriorityBadge(selectedCase.priority)}
                  </div>
                </div>
                <div className="text-right text-sm text-muted-foreground">
                  <p>Created: {new Date(selectedCase.created_at).toLocaleString()}</p>
                  {selectedCase.due_date && (
                    <p>Due: {new Date(selectedCase.due_date).toLocaleString()}</p>
                  )}
                </div>
              </div>

              {/* Related Feedback */}
              {relatedFeedback && (
                <div className="bg-slate-50 rounded-lg p-4">
                  <Label className="text-muted-foreground text-xs">Original Feedback</Label>
                  <p className="mt-1 text-sm">{relatedFeedback.content}</p>
                  {relatedFeedback.analysis && (
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="outline" className={`sentiment-${relatedFeedback.analysis.sentiment}`}>
                        {relatedFeedback.analysis.sentiment}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {(relatedFeedback.analysis.confidence * 100).toFixed(0)}% confidence
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Assignment */}
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <Label className="text-muted-foreground text-xs">Assigned To</Label>
                  <p className="mt-1">
                    {selectedCase.assigned_to 
                      ? users.find(u => u.id === selectedCase.assigned_to)?.name || 'Unknown'
                      : 'Unassigned'}
                  </p>
                </div>
                {selectedCase.status !== 'closed' && selectedCase.status !== 'resolved' && (
                  <Button 
                    variant="outline" 
                    onClick={() => setShowAssignDialog(true)}
                    data-testid="assign-case-btn"
                  >
                    <UserCircle size={16} className="mr-2" />
                    {selectedCase.assigned_to ? 'Reassign' : 'Assign'}
                  </Button>
                )}
              </div>

              {/* Resolution Notes */}
              {selectedCase.resolution_notes && (
                <div className="bg-emerald-50 rounded-lg p-4">
                  <Label className="text-emerald-700 text-xs">Resolution Notes</Label>
                  <p className="mt-1 text-sm text-emerald-800">{selectedCase.resolution_notes}</p>
                </div>
              )}

              {/* AI Copilot */}
              <div className="border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-muted-foreground text-xs">AI Copilot</Label>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={handleAiTriage} disabled={aiLoading || !relatedFeedback?.id}>
                      {aiLoading ? 'Working...' : 'Run Triage'}
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleAiDraft} disabled={aiLoading || !selectedCase?.id}>
                      {aiLoading ? 'Working...' : 'Draft Reply'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleStartOrchestration}
                      disabled={orchestrationLoading || !selectedCase?.id}
                      title="Runs a multi-step workflow and pauses on HITL approvals"
                    >
                      {orchestrationLoading ? 'Working...' : 'Run Workflow'}
                    </Button>
                  </div>
                </div>

                {orchestrationRun && (
                  <div className="bg-slate-50 rounded-md p-3 text-sm space-y-2">
                    <div className="flex items-center justify-between">
                      <p>
                        <span className="text-muted-foreground">Workflow:</span>{' '}
                        <span className="capitalize">{String(orchestrationRun.status || '').replaceAll('_', ' ')}</span>
                      </p>
                      <Badge variant="outline" className="text-xs">HITL</Badge>
                    </div>

                    <div className="space-y-2">
                      {(orchestrationRun.steps || []).map((s) => (
                        <div key={s.id} className="border rounded-md p-2 bg-white">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="font-medium">{s.title}</p>
                              <p className="text-xs text-muted-foreground capitalize">
                                {String(s.status || '').replaceAll('_', ' ')}
                              </p>
                            </div>

                            {s.requires_approval && s.status === 'needs_approval' && (
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  className="bg-emerald-600 hover:bg-emerald-700"
                                  onClick={() => handleGateDecision(s.key, 'approve')}
                                  disabled={orchestrationLoading}
                                >
                                  Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleGateDecision(s.key, 'reject')}
                                  disabled={orchestrationLoading}
                                >
                                  Reject
                                </Button>
                              </div>
                            )}
                          </div>

                          {s.output?.triage?.suggested_priority && (
                            <div className="mt-2 text-xs text-muted-foreground">
                              Suggested priority: <span className="font-medium capitalize">{s.output.triage.suggested_priority}</span>
                            </div>
                          )}
                          {s.output?.proposed_priority && (
                            <div className="mt-2 text-xs text-muted-foreground">
                              Proposed priority: <span className="font-medium capitalize">{s.output.proposed_priority}</span>
                            </div>
                          )}
                          {s.output?.draft?.customer_reply && (
                            <div className="mt-2">
                              <p className="text-xs text-muted-foreground mb-1">Draft reply</p>
                              <p className="text-xs whitespace-pre-wrap">{s.output.draft.customer_reply}</p>
                            </div>
                          )}
                          {s.output?.proposed_assignee_name && (
                            <div className="mt-2 text-xs text-muted-foreground">
                              Proposed assignee: <span className="font-medium">{s.output.proposed_assignee_name}</span>
                            </div>
                          )}
                          {s.error && (
                            <div className="mt-2 text-xs text-rose-600">{s.error}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {aiTriage && (
                  <div className="bg-slate-50 rounded-md p-3 text-sm space-y-1">
                    <p><span className="text-muted-foreground">Category:</span> <span className="capitalize">{aiTriage.category}</span></p>
                    <p><span className="text-muted-foreground">Suggested priority:</span> <span className="capitalize">{aiTriage.suggested_priority}</span></p>
                    <p className="text-muted-foreground text-xs mt-2">Recommended actions:</p>
                    <ul className="list-disc pl-5">
                      {(aiTriage.recommended_actions || []).slice(0, 5).map((a, idx) => (
                        <li key={idx}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {aiDraft && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="bg-slate-50 rounded-md p-3">
                      <p className="text-xs text-muted-foreground mb-2">Customer reply</p>
                      <p className="text-sm whitespace-pre-wrap">{aiDraft.customer_reply}</p>
                    </div>
                    <div className="bg-slate-50 rounded-md p-3">
                      <p className="text-xs text-muted-foreground mb-2">Internal note</p>
                      <p className="text-sm whitespace-pre-wrap">{aiDraft.internal_note}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Evidence */}
              <div className="border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-muted-foreground text-xs">Evidence</Label>
                </div>

                {selectedCase.evidence?.length > 0 ? (
                  <div className="space-y-2">
                    {selectedCase.evidence.map((ev) => (
                      <div key={ev.id} className="flex items-center justify-between gap-3 text-sm border rounded-md p-2">
                        <div className="min-w-0">
                          <p className="font-medium truncate">{ev.original_filename || ev.filename}</p>
                          <p className="text-xs text-muted-foreground">
                            {ev.note ? ev.note : '—'} • {ev.uploaded_at ? new Date(ev.uploaded_at).toLocaleString() : ''}
                          </p>
                        </div>
                        <a
                          className="text-indigo-600 hover:underline text-sm"
                          href={`${process.env.REACT_APP_BACKEND_URL}${ev.url}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          View
                        </a>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No evidence uploaded yet.</p>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Upload file</Label>
                    <Input
                      type="file"
                      onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
                      data-testid="evidence-file-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Note (optional)</Label>
                    <Input
                      value={evidenceNote}
                      onChange={(e) => setEvidenceNote(e.target.value)}
                      placeholder="e.g., screenshot of error / invoice / chat log"
                      data-testid="evidence-note-input"
                    />
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleUploadEvidence}
                    disabled={submitting}
                    data-testid="upload-evidence-btn"
                  >
                    {submitting ? 'Uploading...' : 'Upload Evidence'}
                  </Button>
                </div>
              </div>

              {/* Verification */}
              {selectedCase.verification_status && (
                <div className={`rounded-lg p-4 ${
                  selectedCase.verification_status === 'passed'
                    ? 'bg-emerald-50'
                    : selectedCase.verification_status === 'failed'
                      ? 'bg-rose-50'
                      : 'bg-amber-50'
                }`}>
                  <Label className="text-muted-foreground text-xs">Verification</Label>
                  <p className="mt-1 text-sm">
                    {selectedCase.verification_status === 'pending' && 'Pending customer verification'}
                    {selectedCase.verification_status === 'passed' && `Passed (${selectedCase.verification_rating}/5)`}
                    {selectedCase.verification_status === 'failed' && `Failed (${selectedCase.verification_rating}/5)`}
                  </p>
                </div>
              )}

              {/* Activity Log */}
              <div>
                <Label className="text-muted-foreground text-xs">Activity Log</Label>
                <div className="mt-2 space-y-2">
                  {caseLogs.length > 0 ? (
                    caseLogs.map((log) => (
                      <div key={log.id} className="flex items-start gap-3 text-sm p-2 border-l-2 border-slate-200">
                        <div>
                          <p className="font-medium capitalize">{log.action}</p>
                          <p className="text-muted-foreground">{log.notes}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(log.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted-foreground text-sm">No activity yet</p>
                  )}
                </div>
              </div>

              {/* Actions */}
              {selectedCase.status === 'assigned' && (
                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button
                    variant="outline"
                    onClick={() => setShowStartDialog(true)}
                    disabled={submitting}
                  >
                    <Clock size={16} className="mr-2" />
                    Start Work
                  </Button>
                </div>
              )}

              {selectedCase.status !== 'closed' && selectedCase.status !== 'resolved' && selectedCase.status !== 'assigned' && (
                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button 
                    className="bg-emerald-600 hover:bg-emerald-700"
                    onClick={() => setShowResolveDialog(true)}
                    data-testid="resolve-case-btn"
                  >
                    <CheckCircle size={16} className="mr-2" />
                    Resolve Case
                  </Button>
                </div>
              )}

              {selectedCase.status === 'resolved' && (
                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button
                    className="bg-indigo-600 hover:bg-indigo-700"
                    onClick={() => setShowVerifyDialog(true)}
                    data-testid="verify-case-btn"
                  >
                    <CheckCircle size={16} className="mr-2" />
                    Verify & Close
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Assign Dialog */}
      <Dialog open={showAssignDialog} onOpenChange={setShowAssignDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading">Assign Case</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Select Assignee</Label>
              <Select value={assigneeId} onValueChange={setAssigneeId}>
                <SelectTrigger data-testid="assignee-select">
                  <SelectValue placeholder="Select team member" />
                </SelectTrigger>
                <SelectContent>
                  {users.filter(u => u.role === 'agent' || u.role === 'manager').map(u => (
                    <SelectItem key={u.id} value={u.id}>{u.name} ({u.role})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowAssignDialog(false)}>Cancel</Button>
              <Button 
                className="bg-indigo-600 hover:bg-indigo-700"
                onClick={handleAssign}
                disabled={submitting}
                data-testid="confirm-assign-btn"
              >
                {submitting ? 'Assigning...' : 'Assign'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Resolve Dialog */}
      <Dialog open={showResolveDialog} onOpenChange={setShowResolveDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading">Resolve Case</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Resolution Notes</Label>
              <Textarea
                placeholder="Describe how the issue was resolved..."
                rows={4}
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                data-testid="resolution-notes-input"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowResolveDialog(false)}>Cancel</Button>
              <Button 
                className="bg-emerald-600 hover:bg-emerald-700"
                onClick={handleResolve}
                disabled={submitting}
                data-testid="confirm-resolve-btn"
              >
                {submitting ? 'Resolving...' : 'Resolve'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Start Work Dialog */}
      <Dialog open={showStartDialog} onOpenChange={setShowStartDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading">Start Work</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <p className="text-sm text-muted-foreground">Mark this case as in progress.</p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowStartDialog(false)}>Cancel</Button>
              <Button className="bg-indigo-600 hover:bg-indigo-700" onClick={handleStartWork} disabled={submitting}>
                {submitting ? 'Updating...' : 'Start'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Verify Dialog */}
      <Dialog open={showVerifyDialog} onOpenChange={setShowVerifyDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading">Customer Verification</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Rating</Label>
              <Select value={String(verificationRating)} onValueChange={(v) => setVerificationRating(parseInt(v, 10))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[5, 4, 3, 2, 1].map((r) => (
                    <SelectItem key={r} value={String(r)}>{r} / 5</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Rating ≥ 4 will close the case; otherwise it reopens to In Progress.</p>
            </div>
            <div className="space-y-2">
              <Label>Comments (optional)</Label>
              <Textarea
                rows={4}
                value={verificationComments}
                onChange={(e) => setVerificationComments(e.target.value)}
                placeholder="Customer feedback on resolution..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowVerifyDialog(false)}>Cancel</Button>
              <Button className="bg-indigo-600 hover:bg-indigo-700" onClick={handleVerify} disabled={submitting}>
                {submitting ? 'Submitting...' : 'Submit'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Smart Routing Dialog */}
      <Dialog open={showSmartRoutingDialog} onOpenChange={setShowSmartRoutingDialog}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Lightning size={20} weight="fill" className="text-indigo-600" />
              Smart Routing Analysis
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-6 mt-4">
            {routingLoading ? (
              <div className="text-center py-12">
                <Robot size={48} className="mx-auto mb-4 text-indigo-600 animate-pulse" />
                <p className="text-muted-foreground">AI is analyzing the case...</p>
              </div>
            ) : routingResult ? (
              <>
                {/* AI Analysis */}
                <div className="bg-indigo-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkle size={18} weight="fill" className="text-indigo-600" />
                    <Label className="text-indigo-700">AI Analysis</Label>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Category:</span>
                      <p className="font-medium capitalize">{routingResult.analysis?.category}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Complexity:</span>
                      <p className="font-medium">{routingResult.analysis?.complexity_score}/10</p>
                    </div>
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Required Skills:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {routingResult.analysis?.required_skills?.map((skill) => (
                          <Badge key={skill} variant="secondary" className="text-xs capitalize">
                            {skill.replace('_', ' ')}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Reasoning:</span>
                      <p className="text-sm mt-1">{routingResult.analysis?.reasoning}</p>
                    </div>
                  </div>
                </div>

                {/* Recommended Agent */}
                {routingResult.routing ? (
                  <div className="border rounded-lg p-4">
                    <Label className="text-muted-foreground text-xs">Recommended Agent</Label>
                    <div className="flex items-center gap-4 mt-3">
                      <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center">
                        <UserCircle size={28} className="text-emerald-600" />
                      </div>
                      <div className="flex-1">
                        <p className="font-semibold text-lg">{routingResult.routing.recommended_agent_name}</p>
                        <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                          <span>{Math.round(routingResult.routing.confidence_score * 100)}% match</span>
                          <span>•</span>
                          <span>{routingResult.routing.agent_workload} active cases</span>
                        </div>
                      </div>
                      <Badge className="bg-emerald-100 text-emerald-700">Best Match</Badge>
                    </div>
                    <div className="mt-3">
                      <span className="text-xs text-muted-foreground">Matched Skills:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {routingResult.routing.matched_skills?.map((skill) => (
                          <Badge key={skill} className="bg-emerald-50 text-emerald-700 text-xs">
                            {skill.replace('_', ' ')}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mt-3">{routingResult.routing.reasoning}</p>

                    {/* Alternative Agents */}
                    {routingResult.routing.alternative_agents?.length > 0 && (
                      <div className="mt-4 pt-4 border-t">
                        <Label className="text-xs text-muted-foreground">Alternative Agents</Label>
                        <div className="space-y-2 mt-2">
                          {routingResult.routing.alternative_agents.map((alt) => (
                            <div key={alt.agent_id} className="flex items-center justify-between text-sm">
                              <span>{alt.agent_name}</span>
                              <div className="flex items-center gap-2">
                                <span className="text-muted-foreground">{Math.round(alt.score)}% match</span>
                                <span className="text-muted-foreground">•</span>
                                <span className="text-muted-foreground">{alt.workload} cases</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 border rounded-lg">
                    <Warning size={48} className="mx-auto mb-2 text-amber-500" />
                    <p className="text-muted-foreground">No available agents found for this case</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button variant="outline" onClick={() => setShowSmartRoutingDialog(false)}>
                    Cancel
                  </Button>
                  {routingResult.routing && (
                    <Button 
                      className="bg-indigo-600 hover:bg-indigo-700"
                      onClick={handleAutoAssign}
                      disabled={submitting}
                      data-testid="auto-assign-btn"
                    >
                      <Lightning size={16} className="mr-2" />
                      {submitting ? 'Assigning...' : 'Auto-Assign to Best Match'}
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-8">
                <Warning size={48} className="mx-auto mb-2 text-amber-500" />
                <p className="text-muted-foreground">Failed to analyze case</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
