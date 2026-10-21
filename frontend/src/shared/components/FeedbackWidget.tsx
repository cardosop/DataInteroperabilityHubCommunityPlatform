/**
 * FeedbackWidget — "Was this helpful?" inline feedback (281.A.11.4).
 *
 * Renders on key screens. POSTs feedback to /api/v1/analytics/feedback/.
 * Dismissible per-session (localStorage). Routes to product backlog via Linear.
 */
import { useState, useCallback } from 'react';
import './FeedbackWidget.css';

interface FeedbackWidgetProps {
  /** Screen identifier — sent to analytics for routing. */
  screenId: string;
  /** Optional callback after feedback submitted. */
  onFeedback?: (helpful: boolean, comment?: string) => void;
}

const DISMISSED_KEY = 'meshant_feedback_dismissed';

export function FeedbackWidget({ screenId, onFeedback }: FeedbackWidgetProps) {
  const [submitted, setSubmitted] = useState(false);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');
  const [dismissed, setDismissed] = useState(() => {
    try {
      const data = JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? '{}');
      return data[screenId] === true;
    } catch {
      return false;
    }
  });

  const dismiss = useCallback(() => {
    try {
      const data = JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? '{}');
      data[screenId] = true;
      localStorage.setItem(DISMISSED_KEY, JSON.stringify(data));
    } catch { /* localStorage may be unavailable */ }
    setDismissed(true);
  }, [screenId]);

  const submitFeedback = useCallback(async (helpful: boolean) => {
    setSubmitted(true);
    try {
      await fetch('/api/v1/analytics/feedback/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          screen_id: screenId,
          helpful,
          comment: comment || undefined,
          url: window.location.href,
          timestamp: new Date().toISOString(),
        }),
      });
    } catch {
      /* non-critical — analytics may be down */
    }
    onFeedback?.(helpful, comment || undefined);
  }, [screenId, comment, onFeedback]);

  if (dismissed || submitted) return null;

  return (
    <div className="feedback-widget" data-testid="feedback-widget" role="complementary">
      {!showComment ? (
        <div className="feedback-widget__prompt">
          <span className="feedback-widget__question">Was this helpful?</span>
          <button
            type="button"
            className="feedback-widget__btn feedback-widget__btn--yes"
            onClick={() => submitFeedback(true)}
            aria-label="Yes, this was helpful"
          >
            👍 Yes
          </button>
          <button
            type="button"
            className="feedback-widget__btn feedback-widget__btn--no"
            onClick={() => setShowComment(true)}
            aria-label="No, this needs improvement"
          >
            👎 No
          </button>
          <button
            type="button"
            className="feedback-widget__dismiss"
            onClick={dismiss}
            aria-label="Dismiss feedback prompt"
          >
            ✕
          </button>
        </div>
      ) : (
        <div className="feedback-widget__comment">
          <label htmlFor={`feedback-comment-${screenId}`}>
            What could be better?
          </label>
          <textarea
            id={`feedback-comment-${screenId}`}
            rows={2}
            maxLength={500}
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder="Tell us what you were trying to do…"
          />
          <div className="feedback-widget__comment-actions">
            <button
              type="button"
              className="feedback-widget__btn feedback-widget__btn--submit"
              onClick={() => submitFeedback(false)}
            >
              Submit feedback
            </button>
            <button
              type="button"
              className="feedback-widget__btn feedback-widget__btn--cancel"
              onClick={() => setShowComment(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
