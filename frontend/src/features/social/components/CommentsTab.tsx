/**
 * Comments Tab
 * Displays and manages asset comments with threading support
 */

import { useEffect, useState } from 'react';
import { useComments, useSubmitComment } from '../hooks/useSocial';
import { useAssets } from '../../assets/hooks/useAssets';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import type { Comment } from '../../../shared/types/social';
import './CommentsTab.css';
import { Button } from '../../../shared/components/Button';

interface CommentsTabProps {
  assetId: string | null;
  onAssetSelect?: (assetId: string) => void;
  /** When true, hide asset selector (e.g. when embedded in AssetDetailPage with assetId from route) */
  assetIdOnly?: boolean;
}

export function CommentsTab({ assetId, assetIdOnly = false }: CommentsTabProps) {
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(assetId);

  useEffect(() => {
    if (!assetIdOnly) setSelectedAssetId(assetId);
  }, [assetId, assetIdOnly]);
  const [showForm, setShowForm] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [replyingTo, setReplyingTo] = useState<Comment | null>(null);

  const effectiveAssetId = assetIdOnly ? assetId : selectedAssetId;
  const { data: commentsData, isLoading, error, refetch } = useComments(effectiveAssetId || '', {
    page_size: 100,
  });
  const { data: assetsData } = useAssets({ page_size: 100 });
  const submitCommentMutation = useSubmitComment();

  const handleSubmitComment = async () => {
    if (!effectiveAssetId || !commentText.trim()) return;

    try {
      await submitCommentMutation.mutateAsync({
        asset_id: effectiveAssetId,
        comment_text: commentText,
        parent_comment_id: replyingTo?.id,
      });
      setCommentText('');
      setReplyingTo(null);
      setShowForm(false);
      refetch();
    } catch {
      // Error handled by mutation
    }
  };

  const buildCommentTree = (comments: Comment[]): Comment[] => {
    const commentMap = new Map<string, Comment & { replies?: Comment[] }>();
    const rootComments: Comment[] = [];

    // First pass: create map of all comments
    comments.forEach(comment => {
      commentMap.set(comment.id, { ...comment, replies: [] });
    });

    // Second pass: build tree
    comments.forEach(comment => {
      const commentWithReplies = commentMap.get(comment.id)!;
      if (comment.parent_comment_id) {
        const parent = commentMap.get(comment.parent_comment_id);
        if (parent) {
          if (!parent.replies) parent.replies = [];
          parent.replies.push(commentWithReplies);
        }
      } else {
        rootComments.push(commentWithReplies);
      }
    });

    return rootComments;
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading comments..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load comments" onRetry={() => refetch()} />;
  }

  const comments = commentsData?.results || [];
  const commentTree = buildCommentTree(comments);

  const renderComment = (comment: Comment & { replies?: Comment[] }, depth = 0) => (
    <div key={comment.id} className={`comment-item ${depth > 0 ? 'reply' : ''}`} style={{ marginLeft: `${depth * 40}px` }}>
      <div className="comment-header">
        <span className="comment-date">
          {new Date(comment.created_at).toLocaleDateString()}
        </span>
        {comment.mentions.length > 0 && (
          <span className="mentions">
            Mentions: {comment.mentions.join(', ')}
          </span>
        )}
        {comment.status !== 'APPROVED' && (
          <span className={`comment-status status-${comment.status.toLowerCase()}`}>
            {comment.status}
          </span>
        )}
      </div>
      <p className="comment-text">{comment.comment_text}</p>
      <div className="comment-actions">
        <button
          className="btn-link"
          onClick={() => {
            setReplyingTo(comment);
            setShowForm(true);
          }}
          type="button"
        >
          Reply
        </button>
      </div>
      {comment.replies && comment.replies.length > 0 && (
        <div className="comment-replies">
          {comment.replies.map(reply => renderComment(reply, depth + 1))}
        </div>
      )}
    </div>
  );

  return (
    <div className="comments-tab">
      {!assetIdOnly && (
        <div className="comments-tab-header">
          <div className="asset-selector">
            <label htmlFor="asset-select">Select Asset:</label>
            <select
              id="asset-select"
              value={selectedAssetId || ''}
              onChange={(e) => {
                setSelectedAssetId(e.target.value || null);
                setShowForm(false);
                setReplyingTo(null);
              }}
            >
              <option value="">-- Select an asset --</option>
              {assetsData?.results?.map(asset => (
                <option key={asset.id} value={asset.id}>
                  {asset.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {effectiveAssetId && (
        <>
          {!showForm && (
            <Button
 variant="primary"
 onClick={() => {
 setShowForm(true);
 setReplyingTo(null);
 }}>
              Add Comment
            </Button>
          )}

          {showForm && (
            <div className="comment-form">
              <h3>{replyingTo ? `Reply to comment` : 'Add Comment'}</h3>
              {replyingTo && (
                <div className="replying-to">
                  Replying to: "{replyingTo.comment_text.substring(0, 50)}..."
                </div>
              )}
              <textarea
                placeholder={replyingTo ? "Write your reply..." : "Write your comment..."}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                maxLength={1000}
                rows={4}
                required
              />
              <div className="char-count">
                {commentText.length}/1000 characters
              </div>
              <div className="form-actions">
                <Button
 variant="primary"
 onClick={handleSubmitComment}
 disabled={!commentText.trim() || submitCommentMutation.isPending}>
                  {submitCommentMutation.isPending ? 'Submitting...' : 'Submit'}
                </Button>
                <Button
 variant="secondary"
 onClick={() => {
 setShowForm(false);
 setCommentText('');
 setReplyingTo(null);
 }}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {commentTree.length === 0 ? (
            <EmptyState
              title="No comments yet"
              message="Be the first to comment on this asset!"
            />
          ) : (
            <div className="comments-list">
              {commentTree.map(comment => renderComment(comment))}
            </div>
          )}
        </>
      )}

      {!effectiveAssetId && (
        <EmptyState
          title="Select an asset"
          message="Choose an asset from the dropdown above to view and add comments."
        />
      )}
    </div>
  );
}
