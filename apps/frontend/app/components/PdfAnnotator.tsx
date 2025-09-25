"use client";

import React, { useState } from "react";

interface IHighlight {
  id: string;
  selectedText: string;
  comment: string;
  page?: number;
  timestamp: number;
}

type Props = {
  url: string;
  initialHighlights?: IHighlight[];
  onSave?: (highlights: IHighlight[]) => void;
};

const PdfAnnotator: React.FC<Props> = ({ url, initialHighlights = [], onSave }) => {
  const [highlights, setHighlights] = useState<IHighlight[]>(initialHighlights);
  const [showCommentForm, setShowCommentForm] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const [comment, setComment] = useState("");

  const handleAddComment = () => {
    setShowCommentForm(true);
  };

  const saveHighlight = () => {
    if (!selectedText.trim() || !comment.trim()) return;

    const highlight: IHighlight = {
      id: Math.random().toString(36).slice(2),
      selectedText: selectedText.trim(),
      comment: comment.trim(),
      timestamp: Date.now(),
    };

    const updated = [highlight, ...highlights];
    setHighlights(updated);
    onSave?.(updated);
    
    // Reset form
    setSelectedText("");
    setComment("");
    setShowCommentForm(false);
  };

  const cancelComment = () => {
    setSelectedText("");
    setComment("");
    setShowCommentForm(false);
  };

  const removeHighlight = (id: string) => {
    const updated = highlights.filter(h => h.id !== id);
    setHighlights(updated);
    onSave?.(updated);
  };

  const viewerUrl = `https://mozilla.github.io/pdf.js/web/viewer.html?file=${encodeURIComponent(url)}`;

  return (
    <div className="h-full w-full flex">
      {/* PDF Viewer */}
      <div className="flex-1 h-full relative bg-gray-50">
        <iframe
          src={viewerUrl}
          className="w-full h-full border-none"
          title="PDF Document Viewer"
        />
        

      </div>

      {/* Comments Panel */}
      <div className="w-96 border-l bg-white flex flex-col">
        {/* Header */}
        <div className="p-4 border-b bg-gray-50">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-800">Comments</h3>
            <div className="flex items-center gap-2">
              <span className="bg-gray-200 text-gray-700 px-2 py-1 rounded-full text-sm">
                {highlights.length}
              </span>
              <button
                onClick={handleAddComment}
                className="bg-slate-600 text-white px-3 py-1.5 rounded text-sm hover:bg-slate-700 transition-colors flex items-center gap-1.5"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                </svg>
                New
              </button>
            </div>
          </div>
        </div>

        {/* Comment Form */}
        {showCommentForm && (
          <div className="p-4 border-b bg-blue-50">
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Selected Text (copy from PDF):
                </label>
                <textarea
                  value={selectedText}
                  onChange={(e) => setSelectedText(e.target.value)}
                  placeholder="Paste or type the text you want to comment on..."
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900 placeholder-gray-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Your Comment:
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Enter your comment here..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900 placeholder-gray-500"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={saveHighlight}
                  disabled={!selectedText.trim() || !comment.trim()}
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  Save Comment
                </button>
                <button
                  onClick={cancelComment}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Comments List */}
        <div className="flex-1 overflow-y-auto">
          {highlights.length === 0 ? (
            <div className="p-6 text-center">
              <div className="text-gray-400 mb-3">
                <svg className="w-16 h-16 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
                </svg>
              </div>
              <h4 className="text-lg font-medium text-gray-600 mb-2">No comments yet</h4>
              <p className="text-sm text-gray-500">
                Click "Add Comment" to create your first annotation
              </p>
            </div>
          ) : (
            <div className="divide-y">
              {highlights.map((highlight, index) => (
                <div key={highlight.id} className="p-4 hover:bg-gray-50">
                  <div className="flex justify-between items-start mb-3">
                    <div className="text-xs text-gray-500 font-medium">
                      Comment #{highlights.length - index}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-xs text-gray-400">
                        {new Date(highlight.timestamp).toLocaleDateString()} {new Date(highlight.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                      <button
                        onClick={() => removeHighlight(highlight.id)}
                        className="text-gray-400 hover:text-red-500 p-1"
                        title="Delete comment"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" clipRule="evenodd" />
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414L7.586 12l-1.293 1.293a1 1 0 101.414 1.414L9 13.414l1.293 1.293a1 1 0 001.414-1.414L10.414 12l1.293-1.293z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  
                  <div className="mb-3">
                    <div className="text-sm font-medium text-gray-800 mb-2">Comment:</div>
                    <div className="text-sm text-gray-700 bg-white p-3 rounded border-l-4 border-blue-500">
                      {highlight.comment}
                    </div>
                  </div>
                  
                  <div className="text-xs text-gray-600">
                    <div className="font-medium mb-1">Referenced text:</div>
                    <div className="bg-gray-100 p-2 rounded italic text-gray-700 leading-relaxed">
                      "{highlight.selectedText.length > 200 ? `${highlight.selectedText.slice(0, 200)}...` : highlight.selectedText}"
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="p-4 border-t bg-gray-50 text-xs text-gray-600">
          <div className="space-y-1">
            <div className="font-medium">How to add comments:</div>
            <div>1. Select and copy text from the PDF</div>
            <div>2. Click "Add Comment" button</div>
            <div>3. Paste the text and add your comment</div>
            <div>4. Click "Save Comment"</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PdfAnnotator;