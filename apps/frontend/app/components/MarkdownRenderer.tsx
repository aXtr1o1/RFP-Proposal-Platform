import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface DocConfig {
  // Layout
  page_orientation: string;
  text_alignment: string;
  reading_direction: string;
  top_margin: string;
  bottom_margin: string;
  left_margin: string;
  right_margin: string;
  
  // Typography
  body_font_size: string;
  heading_font_size: string;
  title_font_size: string;
  bullet_font_size: string;
  table_font_size: string;
  title_color: string;
  heading_color: string;
  body_color: string;
  
  // Table Styling
  auto_fit_tables: boolean;
  table_width: string;
  show_table_borders: boolean;
  border_color: string;
  border_style: string;
  border_preset: string;
  header_background: string;
  table_background: string;
  
  // Header & Footer
  include_header: boolean;
  include_footer: boolean;
  company_name: string;
  company_tagline: string;
  logo_file_path: string;
  footer_left: string;
  footer_center: string;
  footer_right: string;
  show_page_numbers: boolean;
}

const normalizeMarkdown = (input: string): string => {
  if (!input) {
    return '';
  }

  const normalized = input.replace(/\r\n/g, '\n').trim();
  const fencedMatch = normalized.match(/^```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)\s*```$/);

  if (fencedMatch) {
    return fencedMatch[1].trim();
  }

  return normalized;
};

const MarkdownRenderer = ({ 
  markdownContent, 
  docConfig 
}: { 
  markdownContent: string;
  docConfig?: DocConfig;
}) => {
  // Pre-process markdown to strip stray code fences the model sometimes adds
  const processedContent = normalizeMarkdown(markdownContent || '');
  
  // Helper function to convert pt to rem (assuming 16px base font size)
  const ptToRem = (pt: string) => `${parseFloat(pt) / 12}rem`;
  
  // Get text alignment class
  const getTextAlignment = (alignment: string) => {
    switch (alignment) {
      case 'center': return 'text-center';
      case 'right': return 'text-right';
      case 'justify': return 'text-justify';
      default: return 'text-left';
    }
  };
  
  return (
    <div className="flex-1 overflow-auto p-6 bg-gray-50">
      {processedContent ? (
        <div 
          className="max-w-4xl mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-8 content-display-area markdown-content"
          style={{
            textAlign: (docConfig?.text_alignment as any) || 'left',
            direction: (docConfig?.reading_direction as any) || 'ltr',
            backgroundColor: '#ffffff',
            color: '#000000'
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Headings - Use docConfig colors and sizes
              h1: ({ node, ...props }) => (
                <h1 
                  className="font-bold mb-4 mt-6 pb-2 border-b-2 border-gray-300" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.title_font_size) : '2rem',
                    color: docConfig?.title_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              h2: ({ node, ...props }) => (
                <h2 
                  className="font-bold mb-3 mt-5 pb-2 border-b border-gray-300" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.heading_font_size) : '1.5rem',
                    color: docConfig?.heading_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              h3: ({ node, ...props }) => (
                <h3 
                  className="font-semibold mb-3 mt-4" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.heading_font_size) : '1.25rem',
                    color: docConfig?.heading_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              h4: ({ node, ...props }) => (
                <h4 
                  className="font-semibold mb-2 mt-3" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.heading_font_size) : '1.125rem',
                    color: docConfig?.heading_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              h5: ({ node, ...props }) => (
                <h5 
                  className="font-semibold mb-2 mt-3" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.heading_font_size) : '1rem',
                    color: docConfig?.heading_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              h6: ({ node, ...props }) => (
                <h6 
                  className="font-semibold mb-2 mt-2" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.heading_font_size) : '0.875rem',
                    color: docConfig?.heading_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              
              // Paragraphs - Use docConfig body color and size
              p: ({ node, ...props }) => (
                <p 
                  className="leading-7 mb-4" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.body_font_size) : '1rem',
                    color: docConfig?.body_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              
              // Links - Brighter blue
              a: ({ node, ...props }) => (
                <a className="text-blue-700 hover:text-blue-900 underline font-medium" {...props} />
              ),
              
              // Lists - Use docConfig bullet font size and body color
              ul: ({ node, ...props }) => (
                <ul 
                  className="list-disc list-inside mb-4 space-y-2" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.bullet_font_size) : '1rem',
                    color: docConfig?.body_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              ol: ({ node, ...props }) => (
                <ol 
                  className="list-decimal list-inside mb-4 space-y-2" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.bullet_font_size) : '1rem',
                    color: docConfig?.body_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              li: ({ node, ...props }) => (
                <li 
                  className="leading-7" 
                  style={{
                    fontSize: docConfig ? ptToRem(docConfig.bullet_font_size) : '1rem',
                    color: docConfig?.body_color || '#000000'
                  }}
                  {...props} 
                />
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
              
              // Tables - Use docConfig table styling
              table: ({ node, ...props }) => (
                <div 
                  className="overflow-x-auto mb-6" 
                  style={{
                    width: docConfig?.table_width ? `${docConfig.table_width}%` : '100%'
                  }}
                >
                  <table 
                    className={`min-w-full border-collapse ${docConfig?.show_table_borders ? 'border-2' : ''}`}
                    style={{
                      borderColor: docConfig?.border_color || '#9ca3af',
                      backgroundColor: docConfig?.table_background || '#ffffff'
                    }}
                    {...props} 
                  />
                </div>
              ),
              thead: ({ node, ...props }) => (
                <thead 
                  style={{
                    backgroundColor: docConfig?.header_background || '#f8f9fa'
                  }}
                  {...props} 
                />
              ),
              tbody: ({ node, ...props }) => (
                <tbody 
                  style={{
                    backgroundColor: docConfig?.table_background || '#ffffff'
                  }}
                  {...props} 
                />
              ),
              tr: ({ node, ...props }) => (
                <tr 
                  className={`${docConfig?.show_table_borders ? 'border-b-2' : ''} hover:bg-gray-100`}
                  style={{
                    borderColor: docConfig?.border_color || '#9ca3af'
                  }}
                  {...props} 
                />
              ),
              th: ({ node, ...props }) => (
                <th 
                  className={`${docConfig?.show_table_borders ? 'border-2' : ''} px-4 py-3 text-left font-bold`}
                  style={{
                    borderColor: docConfig?.border_color || '#9ca3af',
                    color: docConfig?.header_background === '#000000' ? '#ffffff' : '#000000',
                    fontSize: docConfig ? ptToRem(docConfig.table_font_size) : '0.875rem'
                  }}
                  {...props} 
                />
              ),
              td: ({ node, ...props }) => (
                <td 
                  className={`${docConfig?.show_table_borders ? 'border-2' : ''} px-4 py-3 font-medium`}
                  style={{
                    borderColor: docConfig?.border_color || '#9ca3af',
                    color: docConfig?.body_color || '#000000',
                    fontSize: docConfig ? ptToRem(docConfig.table_font_size) : '0.875rem'
                  }}
                  {...props} 
                />
              ),
              
              // Horizontal rule
              hr: ({ node, ...props }) => (
                <hr className="my-6 border-t-2 border-gray-400" {...props} />
              ),
              
              // Images
              img: ({ node, ...props }) => (
                <img className="max-w-full h-auto rounded-lg my-4 border-2 border-gray-300" {...props} />
              ),
              
              // Strong and emphasis - Use docConfig body color
              strong: ({ node, ...props }) => (
                <strong 
                  className="font-bold" 
                  style={{
                    color: docConfig?.body_color || '#000000'
                  }}
                  {...props} 
                />
              ),
              em: ({ node, ...props }) => (
                <em 
                  className="italic" 
                  style={{
                    color: docConfig?.body_color || '#000000'
                  }}
                  {...props} 
                />
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
