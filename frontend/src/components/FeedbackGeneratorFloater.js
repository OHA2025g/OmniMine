import { useEffect, useRef, useState } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { generateDummyFeedbackBatch } from '../services/api';
import { toast } from 'sonner';
import { Play, Pause, SpinnerGap } from '@phosphor-icons/react';

export function FeedbackGeneratorFloater() {
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [count, setCount] = useState(0);
  const [lastId, setLastId] = useState(null);
  const [lastBatchNeg, setLastBatchNeg] = useState(null);
  const timerRef = useRef(null);
  const runningRef = useRef(false);

  const stop = () => {
    runningRef.current = false;
    setRunning(false);
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const tick = async () => {
    if (!runningRef.current) return;
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await generateDummyFeedbackBatch(10, 0.55, 0.6);
      const items = res?.items || [];
      setCount((c) => c + (res?.created || items.length || 0));
      setLastId(items?.[items.length - 1]?.id || null);
      setLastBatchNeg(res?.negative_target ?? null);
    } catch (e) {
      stop();
      toast.warning('Dummy feedback stopped', {
        description: 'Failed generating dummy feedback (check backend logs / permissions).',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const start = () => {
    if (runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    // generate immediately, then on interval
    tick();
    timerRef.current = window.setInterval(tick, 1000);
    toast.message('Dummy feedback started', { description: 'Generating 10 feedbacks per second.' });
  };

  useEffect(() => {
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="fixed bottom-5 right-5 z-[60]">
      <div className="rounded-2xl border border-slate-200 bg-white/90 backdrop-blur-md shadow-lg p-3 w-[260px]">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-slate-900 truncate">Feedback Generator</p>
              <Badge className={running ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'}>
                {running ? 'Running' : 'Stopped'}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Generated: <span className="font-medium text-slate-900">{count}</span>
              {lastBatchNeg != null ? <span className="ml-2">Neg/batch: {lastBatchNeg}/10</span> : null}
              {lastId ? <span className="ml-2">Last: {String(lastId).slice(0, 8)}…</span> : null}
            </p>
          </div>
          <Button
            size="icon"
            className={running ? 'bg-rose-600 hover:bg-rose-700' : 'bg-indigo-600 hover:bg-indigo-700'}
            onClick={() => (running ? stop() : start())}
            data-testid="dummy-feedback-toggle"
            title={running ? 'Stop' : 'Play'}
          >
            {submitting ? <SpinnerGap size={18} className="animate-spin" /> : running ? <Pause size={18} /> : <Play size={18} />}
          </Button>
        </div>
      </div>
    </div>
  );
}

