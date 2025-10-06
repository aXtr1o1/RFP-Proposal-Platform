import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MarkdownRenderer = ({ markdownContent }: { markdownContent: string }) => {
  // Pre-process markdown to ensure proper rendering
  const processedContent = markdownContent || '';
  
  return (
    <div className="flex-1 overflow-auto p-6 bg-gray-50">
      {processedContent ? (
        <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Headings - Much darker colors
              h1: ({ node, ...props }) => (
                <h1 className="teclxt-3xl font-bold text-black mb-4 mt-6 pb-2 border-b-2 border-gray-300" {...props} />
              ),
              h2: ({ node, ...props }) => (
                <h2 className="text-2xl font-bold text-black mb-3 mt-5 pb-2 border-b border-gray-300" {...props} />
              ),
              h3: ({ node, ...props }) => (
                <h3 className="text-xl font-semibold text-black mb-3 mt-4" {...props} />
              ),
              h4: ({ node, ...props }) => (
                <h4 className="text-lg font-semibold text-black mb-2 mt-3" {...props} />
              ),
              h5: ({ node, ...props }) => (
                <h5 className="text-base font-semibold text-black mb-2 mt-3" {...props} />
              ),
              h6: ({ node, ...props }) => (
                <h6 className="text-sm font-semibold text-gray-900 mb-2 mt-2" {...props} />
              ),
              
              // Paragraphs - Darker text
              p: ({ node, ...props }) => (
                <p className="text-black leading-7 mb-4" {...props} />
              ),
              
              // Links - Brighter blue
              a: ({ node, ...props }) => (
                <a className="text-blue-700 hover:text-blue-900 underline font-medium" {...props} />
              ),
              
              // Lists - Darker text
              ul: ({ node, ...props }) => (
                <ul className="list-disc list-inside mb-4 text-black space-y-2" {...props} />
              ),
              ol: ({ node, ...props }) => (
                <ol className="list-decimal list-inside mb-4 text-black space-y-2" {...props} />
              ),
              li: ({ node, ...props }) => (
                <li className="text-black leading-7" {...props} />
              ),
              
              // Code blocks
              code: ({ node, inline, ...props }: any) => 
                inline ? (
                  <code className="bg-red-100 text-red-800 px-2 py-1 rounded text-sm font-mono font-semibold" {...props} />
                ) : (
                  <code className="block bg-gray-900 text-white p-4 rounded-lg overflow-x-auto mb-4 text-sm font-mono" {...props} />
                ),
              pre: ({ node, ...props }) => (
                <pre className="bg-gray-900 rounded-lg overflow-x-auto mb-4" {...props} />
              ),
              
              // Blockquotes
              blockquote: ({ node, ...props }) => (
                <blockquote className="border-l-4 border-blue-600 pl-4 py-2 mb-4 italic text-gray-900 bg-blue-50 font-medium" {...props} />
              ),
              
              // Tables - High contrast
              table: ({ node, ...props }) => (
                <div className="overflow-x-auto mb-6">
                  <table className="min-w-full border-collapse border-2 border-gray-400" {...props} />
                </div>
              ),
              thead: ({ node, ...props }) => (
                <thead className="bg-black" {...props} />
              ),
              tbody: ({ node, ...props }) => (
                <tbody className="bg-white" {...props} />
              ),
              tr: ({ node, ...props }) => (
                <tr className="border-b-2 border-gray-400 hover:bg-gray-100" {...props} />
              ),
              th: ({ node, ...props }) => (
                <th className="border-2 border-gray-400 px-4 py-3 text-left font-bold text-white" {...props} />
              ),
              td: ({ node, ...props }) => (
                <td className="border-2 border-gray-400 px-4 py-3 text-black font-medium" {...props} />
              ),
              
              // Horizontal rule
              hr: ({ node, ...props }) => (
                <hr className="my-6 border-t-2 border-gray-400" {...props} />
              ),
              
              // Images
              img: ({ node, ...props }) => (
                <img className="max-w-full h-auto rounded-lg my-4 border-2 border-gray-300" {...props} />
              ),
              
              // Strong and emphasis - Darker
              strong: ({ node, ...props }) => (
                <strong className="font-bold text-black" {...props} />
              ),
              em: ({ node, ...props }) => (
                <em className="italic text-black" {...props} />
              ),
            }}
          >
            {processedContent}
          </ReactMarkdown>
        </div>
      ) : (
        <p className="text-gray-900 text-center font-medium">No content available</p>
      )}
    </div>
  );
};

export default MarkdownRenderer;