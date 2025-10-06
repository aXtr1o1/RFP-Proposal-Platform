"use client";

import React, { useState, useRef } from 'react';
import { Upload, FileText, Settings, Send, X, CheckCircle, ChevronDown, ChevronRight, AlignLeft, Text ,Table, Layout, Type, Download, Globe, Loader, Database, CheckCircle2, AlertCircle } from 'lucide-react';
import { createClient } from '@supabase/supabase-js';
import MarkdownRenderer from './MarkdownRenderer.tsx';
import { saveAllComments } from "./utils";

type OutputProps = {
  generatedDocument: string | null;
  markdownContent: string | null;
  wordLink: string | null;
  pdfLink: string | null;
  jobUuid: string | null;
};


const OutputDocumentDisplayBase: React.FC<OutputProps> = ({
  generatedDocument,
  markdownContent,
  wordLink,
  pdfLink,
  jobUuid,
}) => {
  
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex flex-col">
      {/* Header with actions */}
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
          {wordLink && (
            <button
              className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 transition-colors duration-200 flex items-center gap-2"
              onClick={() => {
                const t = Date.now();
                const url = `${wordLink}${wordLink.includes('?') ? '&' : '?'}download=proposal_${jobUuid||'file'}.docx&t=${t}`;
                window.open(url, "_blank");
              }}
              title="Download Word document"
            >
              <Download size={16} /> Word
            </button>
          )}
          {pdfLink && (
            <button
              className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 transition-colors duration-200 flex items-center gap-2"
              onClick={() => {
                const t = Date.now();
                const url = `${pdfLink}${pdfLink.includes('?') ? '&' : '?'}download=proposal_${jobUuid||'file'}.pdf&t=${t}`;
                window.open(url, "_blank");
              }}
              title="Download PDF document"
            >
              <Download size={16} /> PDF
            </button>
          )}
        </div>
      </div>

      {/* Body / Markdown Preview */}
      <div className="flex-1 overflow-auto  p-6 bg-gray-50">
        {markdownContent ? (
          <div className="max-w-4xl max-h-screen mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-8" style={{ overflow: "scroll" }}>
          <MarkdownRenderer markdownContent={markdownContent} />
          
          </div>
          
          ) : (
          <div className="h-full flex items-center justify-center">
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
                    </div>
                  </div>
                )},

                
    </div>
            </div>
  );
};

export const OutputDocumentDisplay = React.memo(
  OutputDocumentDisplayBase,
  (prev, next) =>
    prev.generatedDocument === next.generatedDocument &&
    prev.markdownContent === next.markdownContent &&
    prev.wordLink === next.wordLink &&
    prev.pdfLink === next.pdfLink &&
    prev.jobUuid === next.jobUuid
);

interface UploadPageProps {}

const UploadPage: React.FC<UploadPageProps> = () => {
  const [rfpFiles, setRfpFiles] = useState<File[]>([]);
  const [supportingFiles, setSupportingFiles] = useState<File[]>([]);
  const [config, setConfig] = useState<string>('');
  const [language, setLanguage] = useState<string>('arabic');
  const [dragActiveRfp, setDragActiveRfp] = useState(false);
  const [dragActiveSupporting, setDragActiveSupporting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingStage, setProcessingStage] = useState('');
  const [generatedDocument, setGeneratedDocument] = useState<string | null>(null);
  const [wordLink, setWordLink] = useState<string | null>(null);
  const [pdfLink, setPdfLink] = useState<string | null>(null);
  const [markdownContent, setMarkdownContent] = useState<string | null>(null);
  const [isGenerated, setIsGenerated] = useState(false);
  const [jobUuid, setJobUuid] = useState<string | null>(null);
  const [supabaseConnected, setSupabaseConnected] = useState<boolean | null>(null);
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  const supabase = createClient(supabaseUrl, supabaseAnonKey)
  const [currentCommentContent, setCurrentCommentContent] = useState('');
  const [currentCommentText, setCurrentCommentText] = useState('');
  
  // Document configuration state
  type CommentItem = {
  comment1: string; // selected content
  comment2: string; // comment text
};

const [commentConfigList, setCommentConfigList] = useState<CommentItem[]>([]);
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
    show_page_numbers: true,

    
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

  const uploadFileToSupabase = async (
        file: File,
        bucket: string,
        uuid: string,
        index: number
      ): Promise<{ name: string; url: string; size: number }> => {
        try {
          // Create unique file path
          const timestamp = Date.now();
          const sanitizedFileName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
          const filePath = `${uuid}/${timestamp}_${index}_${sanitizedFileName}`;

          console.log(`Uploading ${file.name} to bucket: ${bucket}, path: ${filePath}`);

          // Upload to Supabase storage
          const { data: uploadData, error: uploadError } = await supabase.storage
            .from(bucket)
            .upload(filePath, file, {
              contentType: file.type || "application/octet-stream",
              upsert: true,
            });

          if (uploadError) {
            console.error(`Upload error for ${file.name}:`, uploadError);
            throw new Error(`Failed to upload ${file.name}: ${uploadError.message}`);
          }

          console.log(`Successfully uploaded ${file.name}:`, uploadData);

          // Get public URL
          const { data: urlData } = supabase.storage
            .from(bucket)
            .getPublicUrl(filePath);

          if (!urlData.publicUrl) {
            throw new Error(`Failed to get public URL for ${file.name}`);
          }

          return { 
            name: file.name, 
            url: urlData.publicUrl,
            size: file.size
          };

        } catch (error) {
          console.error(`Error processing file ${file.name}:`, error);
          throw error;
        }
      };
 const updateConfig = (key: string, value: string | boolean) => {
    setDocConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const updateComment = (key: 'comment1' | 'comment2', value: string | boolean) => {
     setCommentConfigList(prev => [...prev, { comment1: '', comment2: '', [key]: value }]);
  };
  // Check Supabase connection
  const checkSupabaseConnection = async () => {
    try {
      const res = await fetch("/nextapi/check-supabase");
      if (!res.ok) {
        console.error("check-supabase HTTP NOT OKAY", res.status);
        return false;
      }
      const data = await res.json();
      if (data.connected) {
        console.log("✅ Supabase connected");
        setSupabaseConnected(true);
        return true;
      } else {
        console.log("❌ Supabase not connected:", data.error);
        setSupabaseConnected(false);
        return false;
      }
    } catch (err) {
      console.error("Supabase check failed", err);
      setSupabaseConnected(false);
      return false;
    }
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

    const valid = Array.from(e.dataTransfer.files).filter(f =>
      f.type === 'application/pdf' ||
      f.type === 'application/msword' ||
      f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    );
    const file = valid[0];
    if (!file) return;

    if (fileType === 'rfp') setRfpFiles([file]);
    else setSupportingFiles([file]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, fileType: 'rfp' | 'supporting') => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (
      file.type === 'application/pdf' ||
      file.type === 'application/msword' ||
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ) {
      if (fileType === 'rfp') setRfpFiles([file]);
      else setSupportingFiles([file]);
    }
    e.currentTarget.value = '';
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

  const postUuidConfig = async (uuid: string, config: string) => {
    const res = await fetch(`http://127.0.0.1:8000/api/initialgen/${uuid}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        config: config,
        docConfig: docConfig,
        timestamp: new Date().toISOString(),
        language: language
      }),
    });
    
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`Backend /upload failed: ${res.status} ${txt}`);
    }

    const result = await res.json().catch(() => ({}));
    const docxShareUrl = result.wordLink;
    const pdfShareUrl = result.pdfLink;
    const proposalContent = result.proposal_content;
    
    console.log("Word download link:", docxShareUrl);
    console.log("PDF download link:", pdfShareUrl);
    console.log("Proposal content received:", proposalContent ? "Yes" : "No");
    
    return { docxShareUrl, pdfShareUrl, proposalContent };
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

  const handleDownload = () => {
    if (pdfLink) {
      window.open(`${pdfLink}?download=1`, "_blank");
    } else if (wordLink) {
      window.open(`${wordLink}?download=1`, "_blank");
    } else {
      alert("No file available to download yet.");
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
    setProcessingStage('Checking connections...');
    
    const progressInterval = simulateProgress();
    
    try {
      const uuid = generateUUID();
      setJobUuid(uuid);
      
      // Check Supabase connection
      const supabaseConnected = await checkSupabaseConnection();

      if (!supabaseConnected) {
        alert("Supabase connection failed. Comments will not be saved.");
      }
      
     


       const updateDatabaseRecord = async (
        uuid: string,
        rfpFileData: string | null,
        supportingFileData: string | null
      ) => {
        try {
          // Try to update existing record first
          const { data: updateData, error: updateError } = await supabase
            .from("Data_Table")
            .update({
              RFP_Files: rfpFileData,
              Supporting_Files: supportingFileData,
            })
            .eq("uuid", uuid)
            .select();

          // If no rows were updated, insert a new record
          if (!updateError && (!updateData || updateData.length === 0)) {
            console.log('No existing record found, creating new record...');
            
            const { data: insertData, error: insertError } = await supabase
              .from("Data_Table")
              .insert({
                uuid: uuid,
                RFP_Files: rfpFileData,
                Supporting_Files: supportingFileData,
              })
              .select();

            if (insertError) {
              console.error('Database insert error:', insertError);
              throw new Error(`Database insert failed: ${insertError.message}`);
            }

            console.log('New record created successfully:', insertData);
            return insertData;
          } else if (updateError) {
            console.error('Database update error:', updateError);
            throw new Error(`Database update failed: ${updateError.message}`);
          } else {
            console.log('Existing record updated successfully:', updateData);
            return updateData;
          }
        } catch (error) {
          console.error('Database operation failed:', error);
          throw error;
        }
      };
      

      const MAX_FILE_SIZE = 50 * 1024 * 1024;
      const allFiles = [...rfpFiles, ...supportingFiles];
    
      for (const file of allFiles) {
        if (file.size > MAX_FILE_SIZE) {
          throw new Error(`File ${file.name} exceeds 50MB size limit`);
        }
        
        if (file.size === 0) {
          throw new Error(`File ${file.name} is empty`);
        }
      }

      setProcessingStage('Uploading files to cloud storage...');
      
      console.log('Starting RFP file uploads...');
      const rfpResults = await Promise.allSettled(
        rfpFiles.map((file, index) => uploadFileToSupabase(file, "rfp", uuid, index))
      );

      console.log('Starting supporting file uploads...');
      const supportingResults = await Promise.allSettled(
        supportingFiles.map((file, index) => uploadFileToSupabase(file, "supporting", uuid, index))
      );

      const failedRfpUploads = rfpResults.filter(result => result.status === 'rejected');
      const failedSupportingUploads = supportingResults.filter(result => result.status === 'rejected');

      if (failedRfpUploads.length > 0 || failedSupportingUploads.length > 0) {
        console.error('Some uploads failed:');
        failedRfpUploads.forEach((result, index) => {
          if (result.status === 'rejected') {
            console.error(`RFP file ${index}:`, result.reason);
          }
        });
        failedSupportingUploads.forEach((result, index) => {
          if (result.status === 'rejected') {
            console.error(`Supporting file ${index}:`, result.reason);
          }
        });
        
        const totalFailed = failedRfpUploads.length + failedSupportingUploads.length;
        console.warn(`${totalFailed} files failed to upload, continuing with successful uploads`);
      }

      const successfulRfpUploads = rfpResults
        .filter((result): result is PromiseFulfilledResult<{ name: string; url: string; size: number }> => 
          result.status === 'fulfilled'
        )
        .map(result => result.value);

      const successfulSupportingUploads = supportingResults
        .filter((result): result is PromiseFulfilledResult<{ name: string; url: string; size: number }> => 
          result.status === 'fulfilled'
        )
        .map(result => result.value);

      console.log('Successful RFP uploads:', successfulRfpUploads.length);
      console.log('Successful supporting uploads:', successfulSupportingUploads.length);

      if (successfulRfpUploads.length === 0) {
        throw new Error("No RFP files were successfully uploaded. Cannot proceed.");
      }

      setProcessingStage('Updating database records...');
      
      const rfpFileData = successfulRfpUploads.length > 0 ? successfulRfpUploads[0].url : null;
      const supportingFileData = successfulSupportingUploads.length > 0 ? successfulSupportingUploads[0].url : null;

      await updateDatabaseRecord(uuid, rfpFileData, supportingFileData);

      setProcessingStage('Sending to AI processing engine...');

      const { docxShareUrl, pdfShareUrl, proposalContent } = await postUuidConfig(uuid, config);

      setWordLink(docxShareUrl);
      setPdfLink(pdfShareUrl);
      setMarkdownContent(proposalContent || null);
      setGeneratedDocument('Generated_Proposal.docx'); 
      setIsGenerated(true);
      
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

  const handleRegenerate = async () => {
    if (!jobUuid) {
      alert('No job to regenerate. Please run Upload & Process first.');
      return;
    }

    try {
      setIsUploading(true);
      setUploadProgress(0);
      setProcessingStage('Regenerating document...');
      console.log('Regenerating with commentConfig', commentConfigList);
      saveAllComments(supabase,jobUuid, commentConfigList);
      
      setCommentConfigList([]);
      const res = await fetch(`http://127.0.0.1:8000/api/regenerate/${jobUuid}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config: config,
          docConfig: docConfig,
          timestamp: new Date().toISOString(),
          language: language,
        }),
      });

      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(`Backend /regenerate failed: ${res.status} ${txt}`);
      }

      const result = await res.json().catch(() => ({}));
      const docxShareUrl = result.wordLink;
      const pdfShareUrl = result.pdfLink;
      const contents = result.updated_markdown;
      
      console.log("Updated markdown content received:", contents? "Yes" : "No");
      console.log("Regenerated Content:", contents);
      

      setWordLink(docxShareUrl);
      setPdfLink(pdfShareUrl);
      setMarkdownContent(contents || null);
      setGeneratedDocument('Regenerated_Proposal.docx');
    } catch (error) {
      console.error('Regenerate failed:', error);
      alert('Regenerate failed. Please try again.');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
      setProcessingStage('');
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
        onClick={
          onToggle}
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

  const InputField = React.memo(({ 
    label, 
    value, 
    onChange, 
    type = 'text', 
    placeholder = '', 
    options = [],
    isTextarea = false,
    rows = 4
  }: {
    label: string;
    value: string | boolean;
    onChange: (value: string | boolean) => void;
    type?: 'text' | 'number' | 'select' | 'checkbox' | 'color';
    placeholder?: string;
    options?: { value: string; label: string }[];
     isTextarea?: boolean;
  rows?: number; // Number of rows for the textarea
  }) => {
    const [localValue, setLocalValue] = React.useState(value);
    const [isFocused, setIsFocused] = React.useState(false);

    React.useEffect(() => {
      if (!isFocused) {
        setLocalValue(value);
      }
    }, [value, isFocused]);

    const handleFocus = () => {
      setIsFocused(true);
    };

    const handleBlur = () => {
      setIsFocused(false);
      onChange(localValue);
    };

    const handleChange = (newValue: string | boolean) => {
      setLocalValue(newValue);
      
      if (type === 'select' || type === 'checkbox') {
        onChange(newValue);
      }
    };

    return (
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
       {isTextarea ? (
        <textarea
          value={localValue as string}
            onChange={(e) => setLocalValue(e.target.value)}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder={placeholder}
          rows={rows}
          className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:ring-1 focus:ring-gray-400 focus:border-gray-400 text-gray-900 resize-none"
        />
      ) : type === 'select' ? (
          <select
            value={localValue as string}
            onChange={(e) => handleChange(e.target.value)}
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
              checked={localValue as boolean}
              onChange={(e) => handleChange(e.target.checked)}
              className="w-3 h-3 text-gray-600 border-gray-300 rounded focus:ring-1 focus:ring-gray-400 text-gray-900"
            />
            <span className="text-xs text-gray-600">Enable</span>
          </label>
        ) : (
          <input
            type={type}
            value={localValue as string}
            onChange={(e) => setLocalValue(e.target.value)}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder={placeholder}
            className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:ring-1 focus:ring-gray-400 focus:border-gray-400 text-gray-900"
          />
        )}
      </div>
    );
  });

  const LoadingDisplay = () => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex items-center justify-center">
      <div className="text-center max-w-md w-full mx-4">
        <div className="mb-4">
          <Loader className="animate-spin mx-auto text-gray-600" size={48} />
        </div>
        <h3 className="text-xl font-medium text-gray-900 mb-2">Processing Your Documents</h3>
        <div className="w-full bg-gray-200 rounded-full h-3 mb-4">
          <div 
            className="bg-gray-600 h-3 rounded-full transition-all duration-500 ease-out" 
            style={{ width: `${uploadProgress}%` }}
          ></div>
        </div>
      </div>
    </div>
  );

  const GeneratedDocumentSection = () => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="border-b border-gray-100 p-4">
        <h3 className="text-sm font-medium text-gray-800 flex items-center gap-2">
          <CheckCircle2 className="text-green-500" size={16} />
          Generated Document
        </h3> 
      </div>
    </div>
  );

  React.useEffect(() => {
    checkSupabaseConnection();
  }, []);
 

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
              {/* Language Selection */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-4 p-4">
                <h3 className="text-sm font-medium text-gray-800 mb-2 flex items-center gap-2">
                  <Globe className="text-gray-500" size={16} /> Language
                </h3>
                <div className="flex gap-2">
                  <button
                    onClick={() => setLanguage('arabic')}
                    className={`flex-1 py-2 px-3 rounded-md text-sm font-medium border transition-colors
                      ${language === 'arabic' 
                        ? 'bg-blue-600 text-white border-blue-600' 
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                  >
                    Arabic
                  </button>
                  <button
                    onClick={() => setLanguage('english')}
                    className={`flex-1 py-2 px-3 rounded-md text-sm font-medium border transition-colors
                      ${language === 'english' 
                        ? 'bg-blue-600 text-white border-blue-600' 
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                      }`}
                  >
                    English
                  </button>
                </div>
              </div>

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
                {!isGenerated ? (
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
                ) : (
                  <button
                    onClick={handleRegenerate}
                    disabled={isUploading}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded text-sm font-medium transition-all duration-200
                      ${isUploading
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200' 
                        : 'bg-indigo-600 text-white hover:bg-indigo-700 border border-indigo-600'
                      }`}
                  >
                    {isUploading ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        Regenerating...
                      </>
                    ) : (
                      <>
                        <Send size={16} />
                        Regenerate Document
                      </>
                    )}
                  </button>
                )}
              </div>
              
            </div>
          </div>

          {/* Center Panel - Loading/Output Display */}
          <div className="flex-1 p-6 min-w-0">
            {isUploading ? (
              <LoadingDisplay />
            ) : generatedDocument ? (
              <OutputDocumentDisplay
                generatedDocument={generatedDocument}
                markdownContent={markdownContent}
                wordLink={wordLink}
                pdfLink={pdfLink}
                jobUuid={jobUuid}
              />
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
          <div className="w-96 p-6  border-l border-gray-200 bg-white">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-2">
                Document Formatting
              </h2>
              <p className="text-sm text-gray-600">
                Customize the appearance and layout of your generated proposal
              </p>
            </div>
            
            
            {/* Page Layout */}
             { !markdownContent &&(<ConfigSection
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
            </ConfigSection>)}

            {/* Typography */}
            { !markdownContent &&( <ConfigSection
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
            </ConfigSection>)}

            {/* Table Styling */}
             { !markdownContent &&(<ConfigSection
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
            </ConfigSection>)}
            {/* Comments ConfigSection */}
            {markdownContent && (<ConfigSection
              title="Comments"
              icon={Text}
              isExpanded={true}
              onToggle={() => {}}
            >
             {commentConfigList.length > 0 && (
  <div className="mt-4 space-y-3">
    <h4 className="text-sm font-medium text-gray-700">Added Comments</h4>
    {commentConfigList.map((comment, index) => (
      <div
        key={index}
        className="p-3 border border-gray-200 rounded bg-gray-50 flex justify-between items-start gap-2"
      >
        <div className="flex-1">
          <p className="text-xs text-gray-500 mb-1">
            <span className="font-semibold">Content:</span> {comment.comment1}
          </p>
          <p className="text-xs text-gray-500">
            <span className="font-semibold">Comment:</span> {comment.comment2}
          </p>
        </div>
        
      </div>
    ))}
  </div>
)}
            <div className="grid grid-cols-1 gap-4">
              <InputField
                label="Content"
                value={currentCommentContent} // local state
                onChange={(value) => setCurrentCommentContent(value as string)}
                placeholder="Enter the Content"
                isTextarea={true}
                rows={6}
              />
            </div>
            <div className="grid grid-cols-1 gap-4">
              <InputField
                label="Comment"
                value={currentCommentText} // local state
                onChange={(value) => setCurrentCommentText(value as string)}
                placeholder="Enter the Comment"
                isTextarea={true}
                rows={6}
              />
            </div>
            <div className="mt-2">
              <button
                type="button"
                className="px-4 py-2 bg-blue-600 text-white rounded text-sm"
                onClick={() => {
                  // Append new comment to the list
                  setCommentConfigList(prev => [
                    ...prev,
                    { comment1: currentCommentContent, comment2: currentCommentText }
                  ]);
                  // Clear local inputs
                  setCurrentCommentContent('');
                  setCurrentCommentText('');
                }}
              >
                Add Comment
              </button>
            </div>
                        </ConfigSection>)}

            {/* Header & Footer */}
            { !markdownContent &&(
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
            </ConfigSection>)}
          </div>
        </div>

        {/* Hidden file inputs */}
        <input
          ref={rfpInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          onChange={(e) => handleFileSelect(e, 'rfp')}
          className="hidden"
        />
        <input
          ref={supportingInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          onChange={(e) => handleFileSelect(e, 'supporting')}
          className="hidden"
        />
      </div>
      
    </>
  );
};

export default UploadPage;