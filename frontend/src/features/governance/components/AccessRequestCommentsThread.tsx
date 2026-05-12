/**
 * Phase 272.1 — AccessRequestCommentsThread
 *
 * Chronological comment thread for an access request.
 * Renders existing comments and a form to submit a new comment.
 */
import { useState } from 'react';
import type { AccessRequestComment } from '../../../shared/types/governance';
import { Button } from '../../../shared/components/Button';
import {
  useAccessRequestComments,
  useCreateAccessRequestComment,
} from '../hooks/useGovernance';
import './AccessRequestCommentsThread.css';

interface Props {
  accessRequestId: string;
}

export function AccessRequestCommentsThread({ accessRequestId }: Props) {
  const { data: comments, isLoading, error, refetch } = useAccessRequestComments(
    accessRequestId,
  );
  const createComment = useCreateAccessRequestComment();
  const [body, setBody] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    try {
      await createComment.mutateAsync({ id: accessRequestId, body: trimmed });
      setBody('');
      refetch();
    } catch {
      // Error shown by mutation hook
    }
  };

  if (isLoading) {
    return <div className="comments-thread-loading">Loading comments…</div>;
  }

  if (error) {
    return (
      <div className="comments-thread-error">
        Failed to load comments.
        <Button variant="ghost" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="access-request-comments-thread">
      <h3>Comments</h3>

      {(!comments || comments.length === 0) ? (
        <p className="comments-thread-empty">No comments yet.</p>
      ) : (
        <ul className="comments-list">
          {(comments as AccessRequestComment[]).map((c) => (
            <li key={c.id} className="comment-item">
              <div className="comment-meta">
                <span className="comment-author">
                  {c.author_email || 'System'}
                </span>
                <span className="comment-time">
                  {new Date(c.created_at).toLocaleString()}
                </span>
              </div>
              <p className="comment-body">{c.body}</p>
            </li>
          ))}
        </ul>
      )}

      <form className="comment-form" onSubmit={handleSubmit}>
        <textarea
          className="comment-input"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Add a comment…"
          rows={3}
          required
        />
        <Button
          type="submit"
          variant="primary"
          disabled={!body.trim() || createComment.isPending}
          loading={createComment.isPending}
        >
          Post Comment
        </Button>
      </form>
    </div>
  );
}
