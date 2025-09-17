"use client";

import React, { useState, useRef } from 'react';
import { Upload, FileText, Settings, Send, X, CheckCircle, ChevronDown, ChevronRight, Palette, AlignLeft, Table, Layout, Type, Eye, Download, Maximize2, Clock, CheckCircle2, AlertCircle, Loader } from 'lucide-react';

interface UploadPageProps {}

const UploadPage: React.FC<UploadPageProps> = () => {
  const [rfpFiles, setRfpFiles] = useState<File[]>([]);
  const [supportingFiles, setSupportingFiles] = useState<File[]>([]);
  const [config, setConfig] = useState<string>('');
  const [dragActiveRfp, setDragActiveRfp] = useState(false);
  const [dragActiveSupporting, setDragActiveSupporting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingStage, setProcessingStage] = useState('');
  const [generatedDocument, setGeneratedDocument] = useState<string | null>(null);
  const [outputDocumentUrl, setOutputDocumentUrl] = useState<string | null>(null);
  
  // Document configuration state
  const [docConfig, setDocConfig] = useState({
    // Layout
    page_orientation: 'portrait',
    text_alignment: 'left',
    reading_direction: 'ltr',
    top_margin: '1.0',
    bottom_margin: '1.0',
    left_margin: '1.0',
    right_margin: '1.0',
    
    // Typography
    body_font_size: '11',
    heading_font_size: '14',
    title_font_size: '16',
    bullet_font_size: '11',
    table_font_size: '10',
    title_color: '#1a1a1a',
    heading_color: '#2d2d2d',
    body_color: '#4a4a4a',
    
    // Table Styling
    auto_fit_tables: true,
    table_width: '100',
    show_table_borders: true,
    border_color: '#cccccc',
    border_style: 'single',
    border_preset: 'grid',
    header_background: '#f8f9fa',
    table_background: '#ffffff',
    
    // Header & Footer
    include_header: true,
    include_footer: true,
    company_name: '',
    company_tagline: '',
    logo_file_path: '',
    footer_left: '',
    footer_center: '',
    footer_right: '',
    show_page_numbers: true
  });

  const [expandedSections, setExpandedSections] = useState({
    layout: true,
    typography: false,
    tables: false,
    branding: false
  });
  
  const rfpInputRef = useRef<HTMLInputElement>(null);
  const supportingInputRef = useRef<HTMLInputElement>(null);

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const updateConfig = (key: string, value: string | boolean) => {
    setDocConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleDrag = (e: React.DragEvent, setDragActive: (active: boolean) => void) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent, fileType: 'rfp' | 'supporting') => {
    e.preventDefault();
    e.stopPropagation();
    if (fileType === 'rfp') setDragActiveRfp(false);
    else setDragActiveSupporting(false);

    const files = Array.from(e.dataTransfer.files).filter(file => 
      file.type === 'application/pdf' || 
      file.type === 'application/msword' || 
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    );

    if (fileType === 'rfp') {
      setRfpFiles(prev => [...prev, ...files]);
    } else {
      setSupportingFiles(prev => [...prev, ...files]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, fileType: 'rfp' | 'supporting') => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      if (fileType === 'rfp') {
        setRfpFiles(prev => [...prev, ...files]);
      } else {
        setSupportingFiles(prev => [...prev, ...files]);
      }
    }
  };

  const removeFile = (index: number, fileType: 'rfp' | 'supporting') => {
    if (fileType === 'rfp') {
      setRfpFiles(prev => prev.filter((_, i) => i !== index));
    } else {
      setSupportingFiles(prev => prev.filter((_, i) => i !== index));
    }
  };

  const generateUUID = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c == 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };

  const checkOneDriveConnection = async () => {
    try {
      const res = await fetch("/api/check-onedrive");
      if (!res.ok) {
        console.error("check-onedrive HTTP NOT OKAY", res.status);
        return false;
      }
      else 
        {
          console.log("check-onedrive HTTP OKAY", res.status);
        }
      const data = await res.json();
      if (data.connected) {
        console.log("✅ OneDrive connected", data.drive);
        return true;
      } else {
        console.log("❌ OneDrive not connected:", data.message);
        return false;
      }
    } catch (err) {
      console.error("OneDrive check failed", err);
      return false;
    }
  };

  const postUuidConfig = async (uuid: string, config: string) => {
    const res = await fetch(`http://localhost:8000/ocr/${uuid}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        config: config,
        docConfig: docConfig, // Send all document formatting settings
        timestamp: new Date().toISOString()
      }),
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`Backend /upload failed: ${res.status} ${txt}`);
    }
    const result = await res.json().catch(() => ({}));
    
    // If the response contains a URL for the output document
    if (result.download_url) {
      const fullDownloadUrl = `http://localhost:8000${result.download_url}`;
      setOutputDocumentUrl(fullDownloadUrl);
      setGeneratedDocument(`${result.folder_name || 'Generated_Proposal'}.docx`);
    }
    
    return result;
  };

  const simulateProgress = () => {
    const stages = [
      { stage: 'Uploading files...', progress: 20 },
      { stage: 'Processing documents...', progress: 40 },
      { stage: 'Analyzing RFP content...', progress: 60 },
      { stage: 'Generating proposal...', progress: 80 },
      { stage: 'Finalizing document...', progress: 95 }
    ];

    let currentStage = 0;
    const interval = setInterval(() => {
      if (currentStage < stages.length) {
        setProcessingStage(stages[currentStage].stage);
        setUploadProgress(stages[currentStage].progress);
        currentStage++;
      } else {
        clearInterval(interval);
        setProcessingStage('Complete!');
        setUploadProgress(100);
      }
    }, 1000);

    return interval;
  };

  // Fixed download function
  const handleDownload = async () => {
    if (!outputDocumentUrl) return;

    try {
      const response = await fetch(outputDocumentUrl);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = generatedDocument || 'proposal.docx';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed. Please try again.');
    }
  };

  const handleUpload = async () => {
    if (rfpFiles.length === 0) {
      alert('Please upload at least one RFP document');
      return;
    }

    if (!config.trim()) {
      alert('Please provide configuration preferences');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setProcessingStage('Checking OneDrive connection...');
    
    const progressInterval = simulateProgress();
    
    try {
      const uuid = generateUUID();
      const connected = await checkOneDriveConnection();
      if (!connected) {
        alert("Please connect OneDrive first!");
        setIsUploading(false);
        clearInterval(progressInterval);
        return;
      }
      const form = new FormData();
      form.append("uuid", uuid);
      form.append("config", config);
      form.append("docConfig", JSON.stringify(docConfig));

      rfpFiles.forEach((f) => form.append("rfpFiles", f, f.name));
      supportingFiles.forEach((f) => form.append("supportingFiles", f, f.name));

      const res = await fetch("/api/upload", {
        method: "POST",
        body: form,
      });

      const data = await res.json();

      if (!res.ok) {
        console.error("Upload failed:", data);
        alert(`Upload failed: ${data?.error || res.status}`);
        return;
      }

      console.log("✅ Uploaded:", data);
      await postUuidConfig(uuid, config);
      
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
      clearInterval(progressInterval);
    } finally {
      setTimeout(() => {
        setIsUploading(false);
        setUploadProgress(0);
        setProcessingStage('');
      }, 2000);
    }
  };

  const FileUploadZone = ({ 
    title, 
    files, 
    dragActive, 
    onDragEnter, 
    onDragLeave, 
    onDragOver, 
    onDrop, 
    onClick, 
    fileType 
  }: {
    title: string;
    files: File[];
    dragActive: boolean;
    onDragEnter: (e: React.DragEvent) => void;
    onDragLeave: (e: React.DragEvent) => void;
    onDragOver: (e: React.DragEvent) => void;
    onDrop: (e: React.DragEvent) => void;
    onClick: () => void;
    fileType: 'rfp' | 'supporting';
  }) => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
      <div className="border-b border-gray-100 p-4">
        <h3 className="text-sm font-medium text-gray-800 flex items-center gap-2">
          <FileText className="text-gray-500" size={16} />
          {title}
        </h3>
      </div>
      
      <div className="p-4">
        <div
          className={`relative border-2 border-dashed rounded-md p-6 text-center transition-all duration-200 cursor-pointer
            ${dragActive 
              ? 'border-gray-400 bg-gray-50' 
              : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
            }`}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
          onClick={onClick}
        >
          <Upload 
            className={`mx-auto mb-3 ${dragActive ? 'text-gray-600' : 'text-gray-400'}`} 
            size={24} 
          />
          <p className="text-sm font-medium text-gray-700 mb-1">
            Drag & drop files here
          </p>
          <p className="text-xs text-gray-500 mb-2">or click to browse</p>
          <p className="text-xs text-gray-400">
            PDF, DOC, DOCX files
          </p>
        </div>

        {files.length > 0 && (
          <div className="mt-4">
            <h4 className="text-xs font-medium text-gray-600 flex items-center gap-1 mb-2">
              <CheckCircle className="text-green-500" size={12} />
              Files ({files.length})
            </h4>
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between bg-gray-50 rounded p-2 mb-2 border border-gray-100">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <FileText className="text-gray-400 flex-shrink-0" size={14} />
                  <span className="text-xs text-gray-700 truncate">
                    {file.name}
                  </span>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {(file.size / 1024 / 1024).toFixed(1)}MB
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(index, fileType);
                    }}
                    className="text-gray-400 hover:text-red-500 p-1 flex-shrink-0"
                  >
                    <X size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const ConfigSection = ({ 
    title, 
    icon: Icon, 
    isExpanded, 
    onToggle, 
    children 
  }: {
    title: string;
    icon: any;
    isExpanded: boolean;
    onToggle: () => void;
    children: React.ReactNode;
  }) => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-4">
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors duration-200"
      >
        <div className="flex items-center gap-2">
          <Icon className="text-gray-500" size={16} />
          <h3 className="text-sm font-medium text-gray-800">{title}</h3>
        </div>
        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      
      {isExpanded && (
        <div className="border-t border-gray-100 p-4 space-y-4">
          {children}
        </div>
      )}
    </div>
  );

  const InputField = ({ 
    label, 
    value, 
    onChange, 
    type = 'text', 
    placeholder = '', 
    options = [] 
  }: {
    label: string;
    value: string | boolean;
    onChange: (value: string | boolean) => void;
    type?: 'text' | 'number' | 'select' | 'checkbox' | 'color';
    placeholder?: string;
    options?: { value: string; label: string }[];
  }) => (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {type === 'select' ? (
        <select
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:ring-1 focus:ring-gray-400 focus:border-gray-400 text-gray-900"
        >
          {options.map(option => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      ) : type === 'checkbox' ? (
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={value as boolean}
            onChange={(e) => onChange(e.target.checked)}
            className="w-3 h-3 text-gray-600 border-gray-300 rounded focus:ring-1 focus:ring-gray-400 text-gray-900"
          />
          <span className="text-xs text-gray-600">Enable</span>
        </label>
      ) : (
        <input
          type={type}
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:ring-1 focus:ring-gray-400 focus:border-gray-400 text-gray-900"
        />
      )}
    </div>
  );

  const LoadingDisplay = () => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex items-center justify-center">
      <div className="text-center max-w-md w-full mx-4">
        <div className="mb-4">
          <Loader className="animate-spin mx-auto text-gray-600" size={48} />
        </div>
        <h3 className="text-xl font-medium text-gray-900 mb-2">Processing Your Documents</h3>
        {/* <p className="text-sm text-gray-600 mb-6">{processingStage}</p>
         */}
        <div className="w-full bg-gray-200 rounded-full h-3 mb-4">
          <div 
            className="bg-gray-600 h-3 rounded-full transition-all duration-500 ease-out" 
            style={{ width: `${uploadProgress}%` }}
          ></div>
        </div>
        
        {/* <div className="text-sm text-gray-500 font-medium">
          {uploadProgress}% Complete
        </div> */}
      </div>
    </div>
  );

  // Simplified document preview component with client-side PDF conversion
  const OutputDocumentDisplay = () => {
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [isLoadingPdf, setIsLoadingPdf] = useState(false);

    const convertToPdfClientSide = async () => {
      if (!outputDocumentUrl || pdfUrl) return;
      
      setIsLoadingPdf(true);
      try {
        // Fetch the document
        const response = await fetch(outputDocumentUrl);
        if (!response.ok) throw new Error('Failed to fetch document');
        
        const arrayBuffer = await response.arrayBuffer();
        
        // Convert DOCX to HTML using mammoth
        const mammoth = await import('mammoth');
        const result = await mammoth.convertToHtml({ arrayBuffer });
        
        // Create a styled HTML document with proper RTL support
        const styledHtml = `
          <!DOCTYPE html>
          <html dir="rtl">
            <head>
              <meta charset="utf-8">
              <style>
                body {
                  font-family: 'Arabic Typesetting', 'Traditional Arabic', 'Times New Roman', serif;
                  line-height: 1.8;
                  max-width: 8.5in;
                  margin: 0 auto;
                  padding: 1in;
                  background: white;
                  color: #333;
                  direction: rtl;
                  text-align: right;
                }
                
                /* Arabic text styling */
                p, div, span {
                  direction: rtl;
                  text-align: right;
                  unicode-bidi: embed;
                  font-size: 14px;
                  line-height: 1.8;
                  margin-bottom: 12px;
                }
                
                /* Headers with RTL support */
                h1, h2, h3, h4, h5, h6 {
                  color: #2d2d2d;
                  margin-top: 24px;
                  margin-bottom: 16px;
                  direction: rtl;
                  text-align: center;
                  font-weight: bold;
                }
                
                h1 { font-size: 18px; }
                h2 { font-size: 16px; }
                h3 { font-size: 14px; }
                
                /* Table styling for RTL */
                table {
                  width: 100%;
                  border-collapse: collapse;
                  margin: 16px 0;
                  direction: rtl;
                  text-align: right;
                }
                
                th, td {
                  border: 1px solid #ddd;
                  padding: 8px 12px;
                  text-align: right;
                  direction: rtl;
                  vertical-align: top;
                }
                
                th {
                  background-color: #f8f9fa;
                  font-weight: bold;
                  text-align: center;
                }
                
                /* Lists with RTL support */
                ul, ol {
                  direction: rtl;
                  text-align: right;
                  padding-right: 20px;
                  margin-right: 0;
                }
                
                li {
                  direction: rtl;
                  text-align: right;
                  margin-bottom: 8px;
                }
                
                /* Strong/bold text */
                strong, b {
                  font-weight: bold;
                }
                
                /* Preserve spacing and formatting */
                .page-break {
                  page-break-before: always;
                }
                
                /* Print styles */
                @media print {
                  body { 
                    margin: 0; 
                    padding: 0.5in;
                    font-size: 12px;
                  }
                  table { font-size: 11px; }
                }
                
                /* Handle mixed content */
                .ltr-content {
                  direction: ltr;
                  text-align: left;
                }
                
                /* Ensure proper word wrapping for Arabic */
                * {
                  word-wrap: break-word;
                  overflow-wrap: break-word;
                }
              </style>
            </head>
            <body>
              ${result.value}
            </body>
          </html>
        `;
        
        // Create a blob URL for the HTML content
        const htmlBlob = new Blob([styledHtml], { type: 'text/html' });
        const htmlUrl = URL.createObjectURL(htmlBlob);
        setPdfUrl(htmlUrl);
        
      } catch (error) {
        console.error('Error converting document:', error);
        // Fallback: try to display the document directly
        setPdfUrl(outputDocumentUrl);
      } finally {
        setIsLoadingPdf(false);
      }
    };

    // Auto-convert when document is ready
    React.useEffect(() => {
      if (outputDocumentUrl && !pdfUrl && !isLoadingPdf) {
        convertToPdfClientSide();
      }
    }, [outputDocumentUrl]);

    // Clean up blob URLs when component unmounts
    React.useEffect(() => {
      return () => {
        if (pdfUrl && pdfUrl.startsWith('blob:')) {
          URL.revokeObjectURL(pdfUrl);
        }
      };
    }, [pdfUrl]);

    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex flex-col">
        {/* Header with Download Button */}
        <div className="border-b border-gray-100 p-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="text-green-500" size={16} />
            <h3 className="text-sm font-medium text-gray-800">Generated Proposal</h3>
            {generatedDocument && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                {generatedDocument}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {pdfUrl && (
              <button 
                className="bg-blue-600 text-white px-3 py-1 rounded text-xs font-medium hover:bg-blue-700 transition-colors duration-200 flex items-center gap-1"
                onClick={() => window.print()}
                title="Print document"
              >
                <FileText size={12} />
                Print
              </button>
            )}
            <button 
              className="bg-green-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-green-700 transition-colors duration-200 flex items-center gap-2"
              onClick={handleDownload}
              title="Download original document"
            >
              <Download size={16} />
              Download
            </button>
          </div>
        </div>
        
        {/* Document Preview Area */}
        <div className="flex-1 overflow-hidden">
          {isLoadingPdf ? (
            <div className="h-full flex items-center justify-center bg-gray-50">
              <div className="text-center">
                <Loader className="animate-spin mx-auto mb-4 text-gray-600" size={48} />
                <h4 className="text-lg font-medium text-gray-800 mb-2">Preparing Document Preview</h4>
                <p className="text-sm text-gray-600">Converting document for display...</p>
              </div>
            </div>
          ) : pdfUrl ? (
            <div className="h-full">
              <iframe
                src={pdfUrl}
                className="w-full h-full"
                title="Document Preview"
                style={{ border: 'none' }}
                onError={() => {
                  console.error('Error loading document preview');
                }}
              />
            </div>
          ) : (
            <div className="h-full flex items-center justify-center bg-gray-50">
              <div className="text-center max-w-md">
                <FileText className="mx-auto mb-4 text-green-500" size={64} />
                <h4 className="text-lg font-medium text-gray-800 mb-2">Document Ready</h4>
                <p className="text-sm text-gray-600 mb-4">
                  Your proposal document has been generated successfully.
                </p>
                <div className="bg-white p-4 rounded-lg shadow-sm border mb-6">
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">Format: Microsoft Word (.docx)</p>
                    <p className="text-xs text-gray-500">Status: Generated Successfully</p>
                    {generatedDocument && (
                      <p className="text-xs text-gray-500">File: {generatedDocument}</p>
                    )}
                  </div>
                </div>
                <button 
                  onClick={convertToPdfClientSide}
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors duration-200 flex items-center justify-center gap-2 mx-auto"
                >
                  <Eye size={16} />
                  Show Preview
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const GeneratedDocumentSection = () => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="border-b border-gray-100 p-4">
        <h3 className="text-sm font-medium text-gray-800 flex items-center gap-2">
          <CheckCircle2 className="text-green-500" size={16} />
          Generated Document
        </h3>
      </div>
      
      <div className="p-4">
        <div className="flex items-center justify-between bg-green-50 rounded p-3 border border-green-200">
          <div className="flex items-center gap-3">
            <FileText className="text-green-600" size={20} />
            <div>
              <p className="text-sm font-medium text-green-800">{generatedDocument}</p>
              <p className="text-xs text-green-600">Generated proposal ready for download</p>
            </div>
          </div>
          <button 
            onClick={handleDownload}
            className="bg-green-600 text-white px-3 py-2 rounded text-xs font-medium hover:bg-green-700 transition-colors duration-200 flex items-center gap-1"
          >
            <Download size={12} />
            Download
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet" />
      
      <div className="min-h-screen bg-gray-50" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
        <div className="flex">
          {/* Left Panel - Upload Form */}
          <div className="w-96 bg-white border-r border-gray-200 min-h-screen p-6">
            <div className="mb-8">
              <h1 className="text-lg font-semibold text-gray-900 mb-2">
                RFP Processing
              </h1>
              <p className="text-xs text-gray-600 leading-relaxed">
                Upload documents and configure your proposal generation
              </p>
            </div>

            <div className="space-y-1">
              <FileUploadZone
                title="RFP Documents"
                files={rfpFiles}
                dragActive={dragActiveRfp}
                onDragEnter={(e) => handleDrag(e, setDragActiveRfp)}
                onDragLeave={(e) => handleDrag(e, setDragActiveRfp)}
                onDragOver={(e) => handleDrag(e, setDragActiveRfp)}
                onDrop={(e) => handleDrop(e, 'rfp')}
                onClick={() => rfpInputRef.current?.click()}
                fileType="rfp"
              />

              <FileUploadZone
                title="Supporting Files"
                files={supportingFiles}
                dragActive={dragActiveSupporting}
                onDragEnter={(e) => handleDrag(e, setDragActiveSupporting)}
                onDragLeave={(e) => handleDrag(e, setDragActiveSupporting)}
                onDragOver={(e) => handleDrag(e, setDragActiveSupporting)}
                onDrop={(e) => handleDrop(e, 'supporting')}
                onClick={() => supportingInputRef.current?.click()}
                fileType="supporting"
              />

              <div className="bg-white rounded-lg shadow-sm border border-gray-200">
                <div className="border-b border-gray-100 p-4">
                  <h3 className="text-sm font-medium text-gray-800 flex items-center gap-2">
                    <Settings className="text-gray-500" size={16} />
                    General Preferences
                  </h3>
                </div>
                
                <div className="p-4">
                  <textarea
                    value={config}
                    onChange={(e) => setConfig(e.target.value)}
                    placeholder="Describe your proposal generation preferences..."
                    rows={4}
                    className="w-full px-3 py-2 bg-white border border-gray-200 text-gray-700 rounded text-xs focus:ring-1 focus:ring-gray-400 focus:border-gray-400 resize-none placeholder-gray-400"
                  />
                  <p className="text-xs text-gray-400 mt-2 leading-relaxed">
                    Include tone, structure, and specific requirements
                  </p>
                </div>
              </div>

              {generatedDocument && <GeneratedDocumentSection />}

              <div className="pt-4">
                <button
                  onClick={handleUpload}
                  disabled={isUploading || rfpFiles.length === 0 || !config.trim()}
                  className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded text-sm font-medium transition-all duration-200
                    ${isUploading || rfpFiles.length === 0 || !config.trim()
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200' 
                      : 'bg-gray-900 text-white hover:bg-gray-800 border border-gray-900'
                    }`}
                >
                  {isUploading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      Processing...
                    </>
                  ) : (
                    <>
                      <Send size={16} />
                      Upload & Process
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Center Panel - Loading/Output Display */}
          <div className="flex-1 p-6 min-w-0">
            {isUploading ? (
              <LoadingDisplay />
            ) : outputDocumentUrl || generatedDocument ? (
              <OutputDocumentDisplay />
            ) : (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex items-center justify-center">
                <div className="text-center">
                  <FileText className="mx-auto mb-4 text-gray-300" size={64} />
                  <h3 className="text-lg font-medium text-gray-600 mb-2">Ready to Process</h3>
                  <p className="text-sm text-gray-500">
                    Upload your RFP documents and click "Upload & Process" to begin
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Right Panel - Document Configuration */}
          <div className="w-96 p-6 overflow-y-auto border-l border-gray-200 bg-white">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-2">
                Document Formatting
              </h2>
              <p className="text-sm text-gray-600">
                Customize the appearance and layout of your generated proposal
              </p>
            </div>

            {/* Page Layout */}
            <ConfigSection
              title="Page Layout"
              icon={AlignLeft}
              isExpanded={expandedSections.layout}
              onToggle={() => toggleSection('layout')}
            >
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  label="Page Orientation"
                  value={docConfig.page_orientation}
                  onChange={(value) => updateConfig('page_orientation', value)}
                  type="select"
                  options={[
                    { value: 'portrait', label: 'Portrait' },
                    { value: 'landscape', label: 'Landscape' }
                  ]}
                />
                <InputField
                  label="Text Alignment"
                  value={docConfig.text_alignment}
                  onChange={(value) => updateConfig('text_alignment', value)}
                  type="select"
                  options={[
                    { value: 'left', label: 'Left' },
                    { value: 'center', label: 'Center' },
                    { value: 'right', label: 'Right' },
                    { value: 'justify', label: 'Justify' }
                  ]}
                />
              </div>
              
              <div className="grid grid-cols-4 gap-2">
                <InputField
                  label="Top Margin (in)"
                  value={docConfig.top_margin}
                  onChange={(value) => updateConfig('top_margin', value)}
                  type="number"
                />
                <InputField
                  label="Bottom Margin (in)"
                  value={docConfig.bottom_margin}
                  onChange={(value) => updateConfig('bottom_margin', value)}
                  type="number"
                />
                <InputField
                  label="Left Margin (in)"
                  value={docConfig.left_margin}
                  onChange={(value) => updateConfig('left_margin', value)}
                  type="number"
                />
                <InputField
                  label="Right Margin (in)"
                  value={docConfig.right_margin}
                  onChange={(value) => updateConfig('right_margin', value)}
                  type="number"
                />
              </div>
            </ConfigSection>

            {/* Typography */}
            <ConfigSection
              title="Typography & Colors"
              icon={Type}
              isExpanded={expandedSections.typography}
              onToggle={() => toggleSection('typography')}
            >
              <div className="grid grid-cols-3 gap-4">
                <InputField
                  label="Body Text Size (pt)"
                  value={docConfig.body_font_size}
                  onChange={(value) => updateConfig('body_font_size', value)}
                  type="number"
                />
                <InputField
                  label="Heading Size (pt)"
                  value={docConfig.heading_font_size}
                  onChange={(value) => updateConfig('heading_font_size', value)}
                  type="number"
                />
                <InputField
                  label="Title Size (pt)"
                  value={docConfig.title_font_size}
                  onChange={(value) => updateConfig('title_font_size', value)}
                  type="number"
                />
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                <InputField
                  label="Main Title Color"
                  value={docConfig.title_color}
                  onChange={(value) => updateConfig('title_color', value)}
                  type="color"
                />
                <InputField
                  label="Heading Color"
                  value={docConfig.heading_color}
                  onChange={(value) => updateConfig('heading_color', value)}
                  type="color"
                />
                <InputField
                  label="Body Text Color"
                  value={docConfig.body_color}
                  onChange={(value) => updateConfig('body_color', value)}
                  type="color"
                />
              </div>
            </ConfigSection>

            {/* Table Styling */}
            <ConfigSection
              title="Table Styling"
              icon={Table}
              isExpanded={expandedSections.tables}
              onToggle={() => toggleSection('tables')}
            >
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  label="Auto-fit Tables"
                  value={docConfig.auto_fit_tables}
                  onChange={(value) => updateConfig('auto_fit_tables', value)}
                  type="checkbox"
                />
                <InputField
                  label="Show Borders"
                  value={docConfig.show_table_borders}
                  onChange={(value) => updateConfig('show_table_borders', value)}
                  type="checkbox"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  label="Table Width (%)"
                  value={docConfig.table_width}
                  onChange={(value) => updateConfig('table_width', value)}
                  type="number"
                />
                <InputField
                  label="Table Font Size"
                  value={docConfig.table_font_size}
                  onChange={(value) => updateConfig('table_font_size', value)}
                  type="number"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  label="Header Background"
                  value={docConfig.header_background}
                  onChange={(value) => updateConfig('header_background', value)}
                  type="color"
                />
                <InputField
                  label="Border Color"
                  value={docConfig.border_color}
                  onChange={(value) => updateConfig('border_color', value)}
                  type="color"
                />
              </div>
            </ConfigSection>

            {/* Header & Footer */}
            <ConfigSection
              title="Branding & Headers"
              icon={Layout}
              isExpanded={expandedSections.branding}
              onToggle={() => toggleSection('branding')}
            >
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  label="Include Header"
                  value={docConfig.include_header}
                  onChange={(value) => updateConfig('include_header', value)}
                  type="checkbox"
                />
                <InputField
                  label="Include Footer"
                  value={docConfig.include_footer}
                  onChange={(value) => updateConfig('include_footer', value)}
                  type="checkbox"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  label="Company Name"
                  value={docConfig.company_name}
                  onChange={(value) => updateConfig('company_name', value)}
                  placeholder="Your Company Name"
                />
                <InputField
                  label="Company Tagline"
                  value={docConfig.company_tagline}
                  onChange={(value) => updateConfig('company_tagline', value)}
                  placeholder="Your tagline or slogan"
                />
              </div>
              
              <div className="space-y-4">
                <InputField
                  label="Footer Left Text"
                  value={docConfig.footer_left}
                  onChange={(value) => updateConfig('footer_left', value)}
                  placeholder="Left footer content"
                />
                <InputField
                  label="Footer Center Text"
                  value={docConfig.footer_center}
                  onChange={(value) => updateConfig('footer_center', value)}
                  placeholder="Center footer content"
                />
                <InputField
                  label="Footer Right Text"
                  value={docConfig.footer_right}
                  onChange={(value) => updateConfig('footer_right', value)}
                  placeholder="Right footer content"
                />
              </div>
              
              <InputField
                label="Show Page Numbers"
                value={docConfig.show_page_numbers}
                onChange={(value) => updateConfig('show_page_numbers', value)}
                type="checkbox"
              />
            </ConfigSection>
          </div>
        </div>

        {/* Hidden file inputs */}
        <input
          ref={rfpInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx"
          onChange={(e) => handleFileSelect(e, 'rfp')}
          className="hidden"
        />
        <input
          ref={supportingInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx"
          onChange={(e) => handleFileSelect(e, 'supporting')}
          className="hidden"
        />
      </div>
    </>
  );
};

export default UploadPage;