import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { getFeedbacks, createFeedback, reanalyzeFeedback, createCase } from '../services/api';
import { toast } from 'sonner';
import { 
  Plus, 
  MagnifyingGlass, 
  FunnelSimple, 
  ArrowClockwise,
  Eye,
  FolderOpen,
  ChatCircleDots,
  Sparkle
} from '@phosphor-icons/react';

const SOURCES = [
  { value: 'twitter', label: 'Twitter' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'website', label: 'Website' },
  { value: 'support_ticket', label: 'Support Ticket' },
  { value: 'email', label: 'Email' },
  { value: 'survey', label: 'Survey' },
  { value: 'manual', label: 'Manual' },
];

export const FeedbackPage = () => {
  const [feedbacks, setFeedbacks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [sentimentFilter, setSentimentFilter] = useState('all');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [selectedFeedback, setSelectedFeedback] = useState(null);
  const [newFeedback, setNewFeedback] = useState({ content: '', source: 'manual', author_name: '' });
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchFeedbacks();
  }, [sourceFilter, sentimentFilter]);

  const fetchFeedbacks = async () => {
    setLoading(true);
    try {
      const params = {};
      if (sourceFilter !== 'all') params.source = sourceFilter;
      if (sentimentFilter !== 'all') params.sentiment = sentimentFilter;
      const data = await getFeedbacks(params);
      setFeedbacks(data);
    } catch (error) {
      toast.error('Failed to fetch feedbacks');
    } finally {
      setLoading(false);
    }
  };

  const handleAddFeedback = async () => {
    if (!newFeedback.content.trim()) {
      toast.error('Please enter feedback content');
      return;
    }
    setSubmitting(true);
    try {
      const created = await createFeedback(newFeedback);
      toast.success('Feedback added and analyzed!');
      setShowAddDialog(false);
      setNewFeedback({ content: '', source: 'manual', author_name: '' });
      if (created?.case_id) {
        toast.success('Auto-case created from negative feedback');
      }
      fetchFeedbacks();
    } catch (error) {
      toast.error('Failed to add feedback');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReanalyze = async (id) => {
    try {
      await reanalyzeFeedback(id);
      toast.success('Feedback re-analyzed');
      fetchFeedbacks();
    } catch (error) {
      toast.error('Failed to re-analyze');
    }
  };

  const handleCreateCase = async (feedback) => {
    try {
      await createCase({
        feedback_id: feedback.id,
        title: `Issue: ${feedback.content.slice(0, 50)}...`,
        priority: feedback.analysis?.sentiment === 'negative' ? 'high' : 'medium'
      });
      toast.success('Case created successfully');
      fetchFeedbacks();
    } catch (error) {
      toast.error('Failed to create case');
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

  const filteredFeedbacks = feedbacks.filter(fb => 
    fb.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
    fb.author_name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6" data-testid="feedback-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Feedback</h1>
          <p className="text-muted-foreground mt-1">Manage and analyze customer feedback</p>
        </div>
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogTrigger asChild>
            <Button className="bg-indigo-600 hover:bg-indigo-700" data-testid="add-feedback-btn">
              <Plus size={18} className="mr-2" />
              Add Feedback
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-heading">Add New Feedback</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label>Source</Label>
                <Select value={newFeedback.source} onValueChange={(v) => setNewFeedback({ ...newFeedback, source: v })}>
                  <SelectTrigger data-testid="feedback-source-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SOURCES.map(s => (
                      <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Author Name (optional)</Label>
                <Input
                  placeholder="Customer name"
                  value={newFeedback.author_name}
                  onChange={(e) => setNewFeedback({ ...newFeedback, author_name: e.target.value })}
                  data-testid="feedback-author-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Feedback Content</Label>
                <Textarea
                  placeholder="Enter the customer feedback..."
                  rows={4}
                  value={newFeedback.content}
                  onChange={(e) => setNewFeedback({ ...newFeedback, content: e.target.value })}
                  data-testid="feedback-content-input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowAddDialog(false)}>Cancel</Button>
                <Button 
                  className="bg-indigo-600 hover:bg-indigo-700" 
                  onClick={handleAddFeedback}
                  disabled={submitting}
                  data-testid="submit-feedback-btn"
                >
                  {submitting ? 'Analyzing...' : 'Add & Analyze'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <Card className="dashboard-card">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search feedback..."
                  className="pl-10"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  data-testid="feedback-search-input"
                />
              </div>
            </div>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-[150px]" data-testid="source-filter">
                <FunnelSimple size={16} className="mr-2" />
                <SelectValue placeholder="Source" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                {SOURCES.map(s => (
                  <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sentimentFilter} onValueChange={setSentimentFilter}>
              <SelectTrigger className="w-[150px]" data-testid="sentiment-filter">
                <SelectValue placeholder="Sentiment" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sentiments</SelectItem>
                <SelectItem value="positive">Positive</SelectItem>
                <SelectItem value="neutral">Neutral</SelectItem>
                <SelectItem value="negative">Negative</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Feedback Table */}
      <Card className="dashboard-card">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Feedback</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Sentiment</TableHead>
                <TableHead>Themes</TableHead>
                <TableHead>Date</TableHead>
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
              ) : filteredFeedbacks.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    <ChatCircleDots size={48} className="mx-auto mb-2 opacity-50" />
                    No feedback found
                  </TableCell>
                </TableRow>
              ) : (
                filteredFeedbacks.map((feedback) => (
                  <TableRow key={feedback.id} className="hover:bg-slate-50">
                    <TableCell>
                      <div className="max-w-md">
                        <p className="text-sm line-clamp-2">{feedback.content}</p>
                        {feedback.author_name && (
                          <p className="text-xs text-muted-foreground mt-1">— {feedback.author_name}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="capitalize">
                        {feedback.source?.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {feedback.analysis ? getSentimentBadge(feedback.analysis.sentiment) : (
                        <Badge variant="outline">Pending</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {feedback.analysis?.themes?.slice(0, 2).map((theme, i) => (
                          <Badge key={i} variant="secondary" className="text-xs">
                            {theme}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(feedback.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedFeedback(feedback)}
                          data-testid={`view-feedback-${feedback.id}`}
                        >
                          <Eye size={16} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReanalyze(feedback.id)}
                          title="Re-analyze"
                        >
                          <ArrowClockwise size={16} />
                        </Button>
                        {!feedback.case_id && feedback.analysis?.sentiment === 'negative' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCreateCase(feedback)}
                            title="Create Case"
                            data-testid={`create-case-${feedback.id}`}
                          >
                            <FolderOpen size={16} />
                          </Button>
                        )}
                        {feedback.case_id && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate('/cases')}
                            title="View Case"
                          >
                            <FolderOpen size={16} />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Feedback Detail Dialog */}
      <Dialog open={!!selectedFeedback} onOpenChange={() => setSelectedFeedback(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-heading">Feedback Details</DialogTitle>
          </DialogHeader>
          {selectedFeedback && (
            <div className="space-y-6 mt-4">
              <div>
                <Label className="text-muted-foreground">Content</Label>
                <p className="mt-1 text-sm">{selectedFeedback.content}</p>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-muted-foreground">Source</Label>
                  <p className="mt-1 capitalize">{selectedFeedback.source?.replace('_', ' ')}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Author</Label>
                  <p className="mt-1">{selectedFeedback.author_name || 'Anonymous'}</p>
                </div>
              </div>

              {selectedFeedback.analysis && (
                <>
                  <div className="border-t pt-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Sparkle size={18} weight="duotone" className="text-indigo-600" />
                      <Label>AI Analysis</Label>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-muted-foreground text-xs">Sentiment</Label>
                        <div className="mt-1">
                          {getSentimentBadge(selectedFeedback.analysis.sentiment)}
                          <span className="text-sm text-muted-foreground ml-2">
                            ({(selectedFeedback.analysis.confidence * 100).toFixed(0)}% confidence)
                          </span>
                        </div>
                      </div>
                      <div>
                        <Label className="text-muted-foreground text-xs">Sarcasm Detected</Label>
                        <p className="mt-1 text-sm">
                          {selectedFeedback.analysis.sarcasm_detected ? 'Yes' : 'No'}
                        </p>
                      </div>
                    </div>

                    {selectedFeedback.analysis.emotions?.length > 0 && (
                      <div className="mt-4">
                        <Label className="text-muted-foreground text-xs">Emotions</Label>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {selectedFeedback.analysis.emotions.map((emotion, i) => (
                            <Badge key={i} variant="secondary">{emotion}</Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedFeedback.analysis.themes?.length > 0 && (
                      <div className="mt-4">
                        <Label className="text-muted-foreground text-xs">Themes</Label>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {selectedFeedback.analysis.themes.map((theme, i) => (
                            <Badge key={i} variant="outline">{theme}</Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedFeedback.analysis.key_phrases?.length > 0 && (
                      <div className="mt-4">
                        <Label className="text-muted-foreground text-xs">Key Phrases</Label>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {selectedFeedback.analysis.key_phrases.map((phrase, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">{phrase}</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}

              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button variant="outline" onClick={() => handleReanalyze(selectedFeedback.id)}>
                  <ArrowClockwise size={16} className="mr-2" />
                  Re-analyze
                </Button>
                {!selectedFeedback.case_id && (
                  <Button 
                    className="bg-indigo-600 hover:bg-indigo-700"
                    onClick={() => {
                      handleCreateCase(selectedFeedback);
                      setSelectedFeedback(null);
                    }}
                  >
                    <FolderOpen size={16} className="mr-2" />
                    Create Case
                  </Button>
                )}
                {selectedFeedback.case_id && (
                  <Button
                    className="bg-indigo-600 hover:bg-indigo-700"
                    onClick={() => navigate('/cases')}
                  >
                    <FolderOpen size={16} className="mr-2" />
                    View Case
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
