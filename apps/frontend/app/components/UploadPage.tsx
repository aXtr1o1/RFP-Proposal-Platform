"use client";

import React, { useState, useRef } from 'react';
import { Upload, FileText, Settings, Send, X, CheckCircle } from 'lucide-react';

interface UploadPageProps {}

const UploadPage: React.FC<UploadPageProps> = () => {
  const [rfpFiles, setRfpFiles] = useState<File[]>([]);
  const [supportingFiles, setSupportingFiles] = useState<File[]>([]);
  const [config, setConfig] = useState<string>('');
  const [dragActiveRfp, setDragActiveRfp] = useState(false);
  const [dragActiveSupporting, setDragActiveSupporting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  const rfpInputRef = useRef<HTMLInputElement>(null);
  const supportingInputRef = useRef<HTMLInputElement>(null);

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
    /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    const res = await fetch("http://localhost:8000/upload", {   
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uuid, config }),
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`Backend /upload failed: ${res.status} ${txt}`);
    }
    return res.json().catch(() => ({}));
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
    
    try {
      const uuid = generateUUID();
      const connected = await checkOneDriveConnection();
      if (!connected) {
        alert("Please connect OneDrive first!");
        setIsUploading(false);
        return;
      }
      const form = new FormData();
      form.append("uuid", uuid);
      form.append("config", config);

      // IMPORTANT: field names must match what the API expects
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
      // Optionally send UUID and config to backend 
      window.location.href = '/loading';
      
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
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
    <div className="bg-gray-900 rounded-2xl shadow-2xl border border-gray-800 overflow-hidden transition-all duration-300 hover:shadow-3xl hover:border-gray-700">
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 p-6 border-b border-gray-700">
        <h3 className="text-xl font-bold text-white flex items-center gap-3">
          <FileText className="text-gray-300" size={24} />
          {title}
        </h3>
      </div>
      
      <div className="p-6">
        <div
          className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 cursor-pointer group
            ${dragActive 
              ? 'border-white bg-gray-800 scale-105 shadow-lg' 
              : 'border-gray-600 hover:border-gray-400 hover:bg-gray-800'
            }`}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
          onClick={onClick}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-xl"></div>
          <Upload 
            className={`mx-auto mb-4 transition-colors ${dragActive ? 'text-white' : 'text-gray-400 group-hover:text-gray-300'}`} 
            size={48} 
          />
          <p className="text-lg font-semibold text-white mb-2">
            Drag & drop files here
          </p>
          <p className="text-gray-400 mb-4">or click to browse</p>
          <p className="text-sm text-gray-500">
            Supports PDF, DOC, DOCX files
          </p>
        </div>

        {files.length > 0 && (
          <div className="mt-6 space-y-3">
            <h4 className="font-semibold text-gray-200 flex items-center gap-2">
              <CheckCircle className="text-green-400" size={18} />
              Uploaded Files ({files.length})
            </h4>
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between bg-gray-800 rounded-lg p-3 border border-gray-700 hover:border-gray-600 transition-colors">
                <div className="flex items-center gap-3">
                  <FileText className="text-gray-400" size={20} />
                  <span className="text-sm font-medium text-gray-200 truncate max-w-64">
                    {file.name}
                  </span>
                  <span className="text-xs text-gray-500">
                    ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index, fileType);
                  }}
                  className="text-gray-400 hover:text-red-400 p-1 rounded-full hover:bg-gray-700 transition-colors"
                >
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-black">
      {/* Animated background */}
      <div className="fixed inset-0 bg-gradient-to-br from-gray-900 via-black to-gray-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.1),transparent)] animate-pulse"></div>
      </div>
      
      {/* Header */}
      <div className="relative bg-gray-900/90 backdrop-blur-sm shadow-2xl border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="text-center">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent mb-2">
              RFP Document Processing
            </h1>
            <p className="text-lg text-gray-400">
              Upload your documents and configure your proposal generation preferences
            </p>
          </div>
        </div>
      </div>

      <div className="relative max-w-6xl mx-auto px-6 py-12">
        <div className="space-y-8">
          {/* RFP Documents Upload */}
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

          {/* Supporting Files Upload */}
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

          {/* Configuration Section */}
          <div className="bg-gray-900 rounded-2xl shadow-2xl border border-gray-800 overflow-hidden transition-all duration-300 hover:shadow-3xl hover:border-gray-700">
            <div className="bg-gradient-to-r from-gray-800 to-gray-900 p-6 border-b border-gray-700">
              <h3 className="text-xl font-bold text-white flex items-center gap-3">
                <Settings className="text-gray-300" size={24} />
                Proposal Generation Configuration
              </h3>
            </div>
            
            <div className="p-6">
              <label className="block text-sm font-semibold text-gray-200 mb-3">
                Configuration Preferences
              </label>
              <textarea
                value={config}
                onChange={(e) => setConfig(e.target.value)}
                placeholder="Enter your preferences for proposal generation in normal paragraph text..."
                rows={6}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-white focus:border-white transition-colors resize-none placeholder-gray-400"
              />
              <p className="text-sm text-gray-500 mt-2">
                Describe how you want your proposal to be generated, including tone, structure, and any specific requirements.
              </p>
            </div>
          </div>

          {/* Upload Button */}
          <div className="text-center">
            

            <button
              onClick={handleUpload}
              disabled={isUploading || rfpFiles.length === 0 || !config.trim()}
              className={`relative overflow-hidden inline-flex items-center gap-3 px-12 py-4 rounded-2xl font-bold text-lg transition-all duration-300 transform hover:scale-105 shadow-2xl
                ${isUploading || rfpFiles.length === 0 || !config.trim()
                  ? 'bg-gray-800 text-gray-500 cursor-not-allowed border border-gray-700' 
                  : 'bg-white text-black hover:bg-gray-100 border border-gray-300 hover:shadow-3xl'
                }`}
            >
              {/* Shine effect */}
              {!isUploading && rfpFiles.length > 0 && config.trim() && (
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full hover:translate-x-full transition-transform duration-700"></div>
              )}
              
              {isUploading ? (
                <>
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-500"></div>
                  Processing...
                </>
              ) : (
                <>
                  <Send size={24} />
                  Upload & Process
                </>
              )}
            </button>
          </div>
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
  );
};

export default UploadPage;