import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { getSurveys, getCases, createSurvey } from '../services/api';
import { toast } from 'sonner';
import { 
  Star, 
  StarHalf,
  Plus,
  ClipboardText
} from '@phosphor-icons/react';

export const SurveysPage = () => {
  const [surveys, setSurveys] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newSurvey, setNewSurvey] = useState({ case_id: '', feedback_id: '', rating: 5, comments: '' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [surveysData, casesData] = await Promise.all([
        getSurveys(),
        getCases({ status: 'resolved' })
      ]);
      setSurveys(surveysData);
      setCases(casesData);
    } catch (error) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  const handleAddSurvey = async () => {
    if (!newSurvey.case_id) {
      toast.error('Please select a case');
      return;
    }
    setSubmitting(true);
    try {
      const selectedCase = cases.find(c => c.id === newSurvey.case_id);
      await createSurvey({
        ...newSurvey,
        feedback_id: selectedCase?.feedback_id || ''
      });
      toast.success('Survey submitted successfully');
      setShowAddDialog(false);
      setNewSurvey({ case_id: '', feedback_id: '', rating: 5, comments: '' });
      fetchData();
    } catch (error) {
      toast.error('Failed to submit survey');
    } finally {
      setSubmitting(false);
    }
  };

  const renderStars = (rating) => {
    return (
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            size={16}
            weight={star <= rating ? 'fill' : 'regular'}
            className={star <= rating ? 'text-amber-400' : 'text-slate-300'}
          />
        ))}
      </div>
    );
  };

  const avgRating = surveys.length > 0 
    ? (surveys.reduce((sum, s) => sum + s.rating, 0) / surveys.length).toFixed(1)
    : 0;

  return (
    <div className="space-y-6" data-testid="surveys-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-slate-900">Surveys</h1>
          <p className="text-muted-foreground mt-1">Post-resolution customer satisfaction surveys</p>
        </div>
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogTrigger asChild>
            <Button className="bg-indigo-600 hover:bg-indigo-700" data-testid="add-survey-btn">
              <Plus size={18} className="mr-2" />
              Add Survey Response
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="font-heading">Record Survey Response</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label>Resolved Case</Label>
                <Select value={newSurvey.case_id} onValueChange={(v) => setNewSurvey({ ...newSurvey, case_id: v })}>
                  <SelectTrigger data-testid="survey-case-select">
                    <SelectValue placeholder="Select a resolved case" />
                  </SelectTrigger>
                  <SelectContent>
                    {cases.map(c => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.title.slice(0, 50)}...
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Rating</Label>
                <div className="flex items-center gap-2">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setNewSurvey({ ...newSurvey, rating: star })}
                      className="focus:outline-none"
                    >
                      <Star
                        size={32}
                        weight={star <= newSurvey.rating ? 'fill' : 'regular'}
                        className={`transition-colors ${star <= newSurvey.rating ? 'text-amber-400' : 'text-slate-300 hover:text-amber-200'}`}
                      />
                    </button>
                  ))}
                  <span className="ml-2 text-lg font-semibold">{newSurvey.rating}/5</span>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Comments (optional)</Label>
                <Textarea
                  placeholder="Customer feedback comments..."
                  rows={3}
                  value={newSurvey.comments}
                  onChange={(e) => setNewSurvey({ ...newSurvey, comments: e.target.value })}
                  data-testid="survey-comments-input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowAddDialog(false)}>Cancel</Button>
                <Button 
                  className="bg-indigo-600 hover:bg-indigo-700"
                  onClick={handleAddSurvey}
                  disabled={submitting}
                  data-testid="submit-survey-btn"
                >
                  {submitting ? 'Submitting...' : 'Submit'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Surveys</p>
                <p className="text-3xl font-heading font-bold mt-1">{surveys.length}</p>
              </div>
              <div className="p-3 bg-indigo-50 rounded-lg">
                <ClipboardText size={24} weight="duotone" className="text-indigo-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Average Rating</p>
                <p className="text-3xl font-heading font-bold mt-1">{avgRating}/5</p>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <Star size={24} weight="fill" className="text-amber-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">5-Star Reviews</p>
                <p className="text-3xl font-heading font-bold mt-1">
                  {surveys.filter(s => s.rating === 5).length}
                </p>
              </div>
              <div className="p-3 bg-emerald-50 rounded-lg">
                <div className="flex">
                  {[1,2,3,4,5].map(i => (
                    <Star key={i} size={12} weight="fill" className="text-amber-400" />
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Surveys Table */}
      <Card className="dashboard-card">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rating</TableHead>
                <TableHead className="w-[50%]">Comments</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                    Loading...
                  </TableCell>
                </TableRow>
              ) : surveys.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                    <ClipboardText size={48} className="mx-auto mb-2 opacity-50" />
                    No surveys recorded yet
                  </TableCell>
                </TableRow>
              ) : (
                surveys.map((survey) => (
                  <TableRow key={survey.id} className="hover:bg-slate-50">
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {renderStars(survey.rating)}
                        <span className="text-sm font-medium">{survey.rating}/5</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <p className="text-sm text-muted-foreground">
                        {survey.comments || 'No comments provided'}
                      </p>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(survey.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};
