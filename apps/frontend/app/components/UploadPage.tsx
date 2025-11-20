"use client";

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Upload, FileText, Settings, Send, X, CheckCircle, ChevronDown, ChevronRight, ChevronUp, AlignLeft, Text ,Table, Layout, Type, Download, Globe, Loader, Database, CheckCircle2, AlertCircle, Menu, Trash2 } from 'lucide-react';
import { createClient } from '@supabase/supabase-js';
import MarkdownRenderer from './MarkdownRenderer.tsx';
import { saveAllComments, safeJsonParse } from "./utils";

const DEFAULT_API_BASE_URL = `http://${process.env.NEXT_PUBLIC_API_HOST}:8000/api`; 
const resolveApiBaseUrl = () => {
  const raw = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
  if (!raw) {
    return DEFAULT_API_BASE_URL;
  }
  const withoutTrailingSlash = raw.replace(/\/$/, "");
  if (withoutTrailingSlash.endsWith("/api") || withoutTrailingSlash.includes("/api/")) {
    return withoutTrailingSlash;
  }
  return `${withoutTrailingSlash}/api`;
};
const API_BASE_URL = resolveApiBaseUrl().replace(/\/$/, "");
const apiPath = (path: string) => `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

type OutputProps = {
  generatedDocument: string | null;
  markdownContent: string | null;
  wordLink: string | null;
  pdfLink: string | null;
  jobUuid: string | null;
  isRegenerating: boolean;
  isRegenerationComplete: boolean;
  docConfig?: any;
  onPdfDownload: () => void;
  isPdfConverting: boolean;
  pdfError: string | null;
  wordDownloadName: string;
  markdownRef?: React.MutableRefObject<HTMLDivElement | null>;
};

type CommentItem = {
  comment1: string;
  comment2: string;
};

type StoredFileInfo = {
  name: string;
  url: string;
  size?: number | null;
};

type StoredProposalSnapshot = {
  config?: string;
  language?: string;
  docConfig?: Record<string, any>;
  wordLink?: string | null;
  pdfLink?: string | null;
  generatedDocument?: string | null;
};

type WordGenRow = {
  id: number;
  uuid: string;
  gen_id: string;
  created_at: string;
  rfp_files: string | null;
  supporting_files: string | null;
  proposal: string | null;
  generated_markdown: string | null;
  regen_comments: string | null;
  delete_at?: string | null;
  general_preference?: string | null;
};

type ParsedWordGenRecord = WordGenRow & {
  rfpFiles: StoredFileInfo[];
  supportingFiles: StoredFileInfo[];
  proposalMeta: StoredProposalSnapshot;
  regenComments: CommentItem[];
};

type UseCaseHistoryEntry = {
  uuid: string;
  items: ParsedWordGenRecord[];
  label: string;
  latestVersion: number;
  latestCreatedAt: string | null;
};

type SseHandlers = {
  onChunk?: (chunk: string) => void;
  onStage?: (payload: Record<string, any> | string) => void;
  onDone?: (payload: Record<string, any> | string) => void;
  onResult?: (payload: Record<string, any> | string) => void;
  onError?: (payload: Record<string, any> | string) => void;
  onEvent?: (eventType: string, rawData: string) => void;
};

type PptSlide = {
  title?: string;
  content?: any[];
  notes?: string;
  layout_type?: string;
  layout_index?: number;
  chart_data?: {
    type?: string;
    title?: string;
    data?: {
      labels?: any[];
      values?: any[];
    };
  };
  image_path?: string;
};

type PptTemplateInfo = {
  id: string;
  name: string;
  description?: string;
  version?: string;
};

type PptStats = {
  total_slides?: number;
  sections?: number;
  content_slides?: number;
  two_column_slides?: number;
  charts?: number;
  tables?: number;
  images?: number;
  icons_count?: number;
};

type ParsedPptContent = {
  slides: PptSlide[];
  meta: {
    title?: string;
    template_id?: string;
    language?: string;
    stats?: PptStats;
  };
};

const extractFileNameFromUrl = (url: string | null | undefined): string => {
  if (!url) {
    return "document";
  }

  try {
    const sanitized = url.split("?")[0];
    const segments = sanitized.split("/");
    const candidate = segments[segments.length - 1] || "document";
    return decodeURIComponent(candidate);
  } catch {
    return "document";
  }
};

const formatNameForSidebar = (input: string | null | undefined, maxLength = 40): string => {
  const name = (input || "").trim();
  if (!name) {
    return "";
  }

  if (name.length <= maxLength) {
    return name;
  }

  const dotIndex = name.lastIndexOf(".");
  if (dotIndex > 0 && dotIndex < name.length - 1) {
    const extension = name.slice(dotIndex);
    const remaining = maxLength - extension.length - 3;
    if (remaining <= 0) {
      return `${name.slice(0, maxLength - 3)}...`;
    }
    return `${name.slice(0, remaining)}...${extension}`;
  }

  return `${name.slice(0, maxLength - 3)}...`;
};

const formatRelativeTimestamp = (value: string | null | undefined): string => {
  if (!value) {
    return "Unknown";
  }
  const parsed = new Date(value);
  const timestamp = parsed.getTime();
  if (Number.isNaN(timestamp)) {
    return "Unknown";
  }

  const now = Date.now();
  const diff = now - timestamp;
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  const week = 7 * day;

  if (diff < minute) {
    return "Just now";
  }
  if (diff < hour) {
    return `${Math.max(1, Math.round(diff / minute))}m ago`;
  }
  if (diff < day) {
    return `${Math.max(1, Math.round(diff / hour))}h ago`;
  }
  if (diff < week) {
    return `${Math.max(1, Math.round(diff / day))}d ago`;
  }
  return parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

const formatSidebarTimestamp = (value: string | null | undefined): string => {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }
  return parsed.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const collectSlideTextParts = (slide?: PptSlide): string[] => {
  if (!slide) {
    return [];
  }
  const parts: string[] = [];
  if (typeof slide.title === "string" && slide.title.trim()) {
    parts.push(slide.title.trim());
  }
  if (Array.isArray(slide.content)) {
    slide.content.forEach((item) => {
      if (typeof item === "string" && item.trim()) {
        parts.push(item.trim());
        return;
      }
      if (item && typeof item === "object") {
        const typed = item as any;
        if (typeof typed.heading === "string" && typed.heading.trim()) {
          parts.push(typed.heading.trim());
        } else if (typeof typed.text === "string" && typed.text.trim()) {
          parts.push(typed.text.trim());
        }
        if (Array.isArray(typed.items)) {
          const firstBullet = typed.items.find((entry: any) => typeof entry === "string" && entry.trim());
          if (typeof firstBullet === "string" && firstBullet.trim()) {
            parts.push(firstBullet.trim());
          }
        }
      }
    });
  }
  if (typeof slide.notes === "string" && slide.notes.trim()) {
    parts.push(slide.notes.trim());
  }
  return parts.filter(Boolean);
};

const getSlidePreviewLines = (slide?: PptSlide, maxLines = 3): string[] => {
  const parts = collectSlideTextParts(slide);
  return parts.slice(0, maxLines);
};

const toStoredFileInfo = (file: { name: string; url: string; size?: number | null }): StoredFileInfo => ({
  name: file?.name || extractFileNameFromUrl(file?.url),
  url: file?.url || "",
  size: file?.size ?? null,
});

const STAGE_MESSAGE_MAP: Record<string, string> = {
  starting: 'Starting...',
  uploading_files: 'Uploading PDFs to AI...',
  downloading_and_uploading_pdfs: 'Uploading PDFs to AI...',
  prompting_model: 'Generating proposal...',
  saving_generated_text: 'Saving content...',
  saving_markdown: 'Saving content...',
  building_word: 'Building Word document...',
  generating_word: 'Building Word document...',
  validating_input: 'Validating requested changes...',
  processing_with_ai: 'Applying requested edits...',
  no_modifications: 'Reusing previous content...',
};

const resolveStageMessage = (stageKey?: string) => {
  if (!stageKey) {
    return 'Processing...';
  }
  return STAGE_MESSAGE_MAP[stageKey] || stageKey.replace(/_/g, ' ');
};

const streamSseResponse = async (response: Response, handlers: SseHandlers = {}) => {
  if (!response.body) {
    throw new Error("No response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatchEventBlock = (eventBlock: string) => {
    if (!eventBlock.trim()) {
      return;
    }
    const lines = eventBlock.split("\n");
    let eventType = "";
    const dataLines: string[] = [];

    for (const rawLine of lines) {
      const line = rawLine.replace(/\r$/, "");
      if (line.startsWith("event:")) {
        eventType = line.substring(6).trim();
      } else if (line.startsWith("data:")) {
        const dataContent = line.substring(5);
        dataLines.push(dataContent.startsWith(" ") ? dataContent.substring(1) : dataContent);
      }
    }

    if (!eventType || dataLines.length === 0) {
      return;
    }

    const rawData = dataLines.join("\n");
    handlers.onEvent?.(eventType, rawData);

    const safeParse = () => {
      try {
        return JSON.parse(rawData);
      } catch {
        return rawData;
      }
    };

    if (eventType === "chunk") {
      const chunkPayload = safeParse();
      if (typeof chunkPayload === "string") {
        handlers.onChunk?.(chunkPayload);
      } else {
        handlers.onChunk?.(JSON.stringify(chunkPayload));
      }
      return;
    }

    const payload = safeParse();

    if (eventType === "stage") {
      handlers.onStage?.(payload);
      return;
    }
    if (eventType === "done") {
      handlers.onDone?.(payload);
      return;
    }
    if (eventType === "result") {
      handlers.onResult?.(payload);
      return;
    }
    if (eventType === "error") {
      handlers.onError?.(payload);
      const message =
        typeof payload === "string"
          ? payload
          : (payload && typeof payload === "object" && "message" in payload)
            ? String((payload as { message?: string }).message || "Stream error")
            : "Stream error";
      throw new Error(message);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        buffer = buffer.replace(/\r\n/g, "\n");
        if (buffer.trim()) {
          dispatchEventBlock(buffer);
        }
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const eventBlock of events) {
        dispatchEventBlock(eventBlock);
      }
    }
  } catch (error) {
    try {
      await reader.cancel();
    } catch {
      // ignore cancellation errors
    }
    throw error;
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // ignore release errors
    }
  }
};


const OutputDocumentDisplayBase: React.FC<OutputProps> = ({
  generatedDocument,
  markdownContent,
  wordLink,
  pdfLink,
  jobUuid,
  isRegenerating,
  isRegenerationComplete,
  docConfig,
  onPdfDownload,
  isPdfConverting,
  pdfError,
  wordDownloadName,
  markdownRef,
}) => {
  const hasWordLink = Boolean(wordLink);
  const hasPdfLink = Boolean(pdfLink);
  const pdfButtonDisabled = isPdfConverting || (!hasWordLink && !hasPdfLink);
  const pdfButtonTitle = hasPdfLink || hasWordLink ? "Download PDF" : "PDF document is not available";

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex flex-col">
      {/* Header with actions */}
      <div className="border-b border-gray-100 p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRegenerating ? (
            <Loader className="animate-spin text-blue-500" size={16} />
          ) : generatedDocument ? (
            <CheckCircle2 className="text-green-500" size={16} />
          ) : (
            <Loader className="animate-spin text-blue-500" size={16} />
          )}
          <h3 className="text-sm font-medium text-gray-800">
            {isRegenerating 
              ? 'Regenerating Proposal...' 
              : generatedDocument 
                ? (isRegenerationComplete ? 'Regenerated Proposal' : 'Generated Proposal')
                : 'Generating Proposal...'
            }
          </h3>
          {generatedDocument && !isRegenerating && (
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
              {generatedDocument}
            </span>
          )}
        </div>
      </div>

      {/* Download buttons on top of markdown */}
      {markdownContent && (hasWordLink || hasPdfLink) && !isRegenerating && (
        <div className="border-b border-gray-100 p-4 bg-gray-50">
          <div className="flex items-center justify-center gap-3">
            {wordLink && (
              <button
                className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 transition-colors duration-200 flex items-center gap-2"
                onClick={() => {
                  const t = Date.now();
                  const url = `${wordLink}${wordLink.includes('?') ? '&' : '?'}download=${encodeURIComponent(
                    wordDownloadName
                  )}&t=${t}`;
                  window.open(url, "_blank");
                }}
                title="Download Word document"
              >
                <Download size={16} /> Word
              </button>
            )}
            <button
              className={`px-4 py-2 rounded text-sm font-medium transition-colors duration-200 flex items-center gap-2 ${
                pdfButtonDisabled ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
              onClick={onPdfDownload}
              disabled={pdfButtonDisabled}
              title={pdfButtonTitle}
            >
              {isPdfConverting ? (
                <>
                  <Loader className="animate-spin" size={16} /> Downloading...
                </>
              ) : (
                <>
                  <Download size={16} /> PDF
                </>
              )}
            </button>
          </div>
          {pdfError && (
            <p className="mt-2 text-xs text-red-600 text-center">{pdfError}</p>
          )}
        </div>
      )}

      {/* Body / Markdown Preview */}
      <div
        className="flex-1 overflow-auto p-6 bg-gray-50"
        ref={(node) => {
          if (markdownRef) {
            markdownRef.current = node;
          }
        }}
      >
        {markdownContent && (
          <div
            className="w-full max-w-4xl mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-8 content-display-area"
            style={{ backgroundColor: '#ffffff', color: '#000000' }}
          >
            <MarkdownRenderer markdownContent={markdownContent} docConfig={docConfig} />
          </div>
        )}
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
    prev.jobUuid === next.jobUuid &&
    prev.isRegenerating === next.isRegenerating &&
    prev.isRegenerationComplete === next.isRegenerationComplete &&
    prev.onPdfDownload === next.onPdfDownload &&
    prev.isPdfConverting === next.isPdfConverting &&
    prev.pdfError === next.pdfError &&
    prev.wordDownloadName === next.wordDownloadName &&
    prev.markdownRef === next.markdownRef &&
    JSON.stringify(prev.docConfig) === JSON.stringify(next.docConfig)
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
  const [isPdfConverting, setIsPdfConverting] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [markdownContent, setMarkdownContent] = useState<string | null>(null);
  const [isGenerated, setIsGenerated] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRegenerationComplete, setIsRegenerationComplete] = useState(false);
  const [jobUuid, setJobUuid] = useState<string | null>(null);
  const [supabaseConnected, setSupabaseConnected] = useState<boolean | null>(null);
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
  const supabase = useMemo(() => {
    if (!supabaseUrl || !supabaseAnonKey) {
      console.error("Supabase environment variables are missing");
      return null;
    }
    try {
      return createClient(supabaseUrl, supabaseAnonKey);
    } catch (err) {
      console.error("Failed to create Supabase client", err);
      return null;
    }
  }, [supabaseUrl, supabaseAnonKey]);
  const supabaseEnvMissing = !supabaseUrl || !supabaseAnonKey;
  const [currentCommentContent, setCurrentCommentContent] = useState('');
  const [currentCommentText, setCurrentCommentText] = useState('');
  const [savedRfpFiles, setSavedRfpFiles] = useState<StoredFileInfo[]>([]);
  const [savedSupportingFiles, setSavedSupportingFiles] = useState<StoredFileInfo[]>([]);
  const [generationHistory, setGenerationHistory] = useState<Record<string, ParsedWordGenRecord[]>>({});
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [expandedUseCases, setExpandedUseCases] = useState<Record<string, boolean>>({});
  const [expandedVersionDetails, setExpandedVersionDetails] = useState<Record<string, boolean>>({});
  const [selectedUseCase, setSelectedUseCase] = useState<string | null>(null);
  const [selectedGenId, setSelectedGenId] = useState<string | null>(null);
  const [deletingGenId, setDeletingGenId] = useState<string | null>(null);
  const [pptSlides, setPptSlides] = useState<PptSlide[]>([]);
  const [selectedSlideIndex, setSelectedSlideIndex] = useState(0);
  const [pptLoading, setPptLoading] = useState(false);
  const [pptError, setPptError] = useState<string | null>(null);
  const [pptPreviewUrl, setPptPreviewUrl] = useState<string | null>(null);
  const [activePptGenId, setActivePptGenId] = useState<string | null>(null);
  const [pptSummary, setPptSummary] = useState<{ title?: string; template_id?: string; language?: string; stats?: PptStats } | null>(null);
  const [pptTemplates, setPptTemplates] = useState<PptTemplateInfo[]>([]);
  const [selectedPptTemplate, setSelectedPptTemplate] = useState<string>("arweqah");
  const [pptTemplatesLoading, setPptTemplatesLoading] = useState(false);
  const [pptTemplatesError, setPptTemplatesError] = useState<string | null>(null);
  const [pptActionStatus, setPptActionStatus] = useState<string | null>(null);
  const [pptAction, setPptAction] = useState<"initial" | "regen" | null>(null);
  const [previewMode, setPreviewMode] = useState<"word" | "ppt">("word");
  const normalizedLanguageLabel = language === "arabic" ? "Arabic" : "English";
  const pendingRegenCommentsRef = useRef<CommentItem[]>([]);
  const versionLanguageRef = useRef<Record<string, string>>({});
  const [currentVersionLanguage, setCurrentVersionLanguage] = useState<string>('arabic');
  const setPdfLinkSafely = useCallback(
    (nextLink: string | null) => {
      setPdfLink(prev => {
        if (prev && prev.startsWith("blob:")) {
          URL.revokeObjectURL(prev);
        }
        return nextLink;
      });
    },
    [setPdfLink]
  );

  const resetPdfState = useCallback(() => {
    setPdfLinkSafely(null);
    setPdfError(null);
    setIsPdfConverting(false);
  }, [setPdfLinkSafely]);

  const resetPptState = useCallback(() => {
    setPptSlides([]);
    setPptPreviewUrl(null);
    setPptError(null);
    setPptSummary(null);
    setActivePptGenId(null);
    setSelectedSlideIndex(0);
    setPptActionStatus(null);
    setPptAction(null);
    setPptLoading(false);
  }, []);

  useEffect(() => {
    return () => {
      if (pdfLink && pdfLink.startsWith("blob:")) {
        URL.revokeObjectURL(pdfLink);
      }
    };
  }, [pdfLink]);
  useEffect(() => {
    setExpandedVersionDetails({});
  }, [generationHistory]);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    const fetchTemplates = async () => {
      setPptTemplatesLoading(true);
      setPptTemplatesError(null);
      try {
        const response = await fetch(apiPath("/templates"), {
          signal: controller.signal,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail =
            (payload && typeof payload === "object" && "detail" in payload ? payload.detail : null) ||
            "Failed to load templates";
          throw new Error(detail);
        }
        const templates = Array.isArray(payload.templates) ? payload.templates : [];
        if (isMounted) {
          setPptTemplates(templates);
          setSelectedPptTemplate((current) => {
            if (current && templates.some((tpl: PptTemplateInfo) => tpl.id === current)) {
              return current;
            }
            return templates[0]?.id || current;
          });
        }
      } catch (err) {
        if (!isMounted || (err instanceof DOMException && err.name === "AbortError")) {
          return;
        }
        setPptTemplatesError(err instanceof Error ? err.message : "Unable to load templates");
      } finally {
        if (isMounted) {
          setPptTemplatesLoading(false);
        }
      }
    };

    fetchTemplates();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  const getWordFileName = useCallback((): string => {
    const explicitName = wordLink ? extractFileNameFromUrl(wordLink) : null;
    if (explicitName) {
      return explicitName;
    }
    if (generatedDocument) {
      return generatedDocument.endsWith(".doc") || generatedDocument.endsWith(".docx")
        ? generatedDocument
        : `${generatedDocument}.docx`;
    }
    return `proposal_${jobUuid || "file"}.docx`;
  }, [wordLink, generatedDocument, jobUuid]);

  const getPdfFileName = useCallback((): string => {
    const wordName = getWordFileName();
    if (wordName.toLowerCase().endsWith(".pdf")) {
      return wordName;
    }
    if (/\.(docx?|doc)$/i.test(wordName)) {
      return wordName.replace(/\.(docx?|doc)$/i, ".pdf");
    }
    return `${wordName}.pdf`;
  }, [getWordFileName]);

  // Document configuration state
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

  useEffect(() => {
    const targetAlignment = language === 'arabic' ? 'right' : 'left';
    const targetDirection = language === 'arabic' ? 'rtl' : 'ltr';

    setDocConfig(prev => {
      if (
        prev.text_alignment === targetAlignment &&
        prev.reading_direction === targetDirection
      ) {
        return prev;
      }

      return {
        ...prev,
        text_alignment: targetAlignment,
        reading_direction: targetDirection,
      };
    });
  }, [language]);

  const [expandedSections, setExpandedSections] = useState({
    layout: true,
    typography: false,
    tables: false,
    branding: false
  });
  
  const rfpInputRef = useRef<HTMLInputElement>(null);
  const supportingInputRef = useRef<HTMLInputElement>(null);
  const markdownContainerRef = useRef<HTMLDivElement | null>(null);

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  type GenerationSnapshotInput = {
    uuid: string;
    genId: string;
    generalPreference?: string;
    regenComments?: CommentItem[];
    rfpFiles?: StoredFileInfo[];
    supportingFiles?: StoredFileInfo[];
    proposalSnapshot: StoredProposalSnapshot;
    generatedMarkdown: string | null;
    createdAt?: string;
    deleteAt?: string | null;
  };

  const buildParsedRecord = useCallback((snapshot: GenerationSnapshotInput): ParsedWordGenRecord => {
    const regenComments = snapshot.regenComments ?? [];
    const rfpFiles = snapshot.rfpFiles ?? [];
    const supportingFiles = snapshot.supportingFiles ?? [];
    const proposalMeta = snapshot.proposalSnapshot ?? {};

    return {
      id: Date.now(),
      uuid: snapshot.uuid,
      gen_id: snapshot.genId,
      created_at: snapshot.createdAt ?? new Date().toISOString(),
      rfp_files: rfpFiles[0]?.url ?? null,
      supporting_files: supportingFiles[0]?.url ?? null,
      proposal: proposalMeta ? JSON.stringify(proposalMeta) : null,
      generated_markdown: snapshot.generatedMarkdown ?? null,
      regen_comments: regenComments.length ? JSON.stringify(regenComments) : null,
      delete_at: snapshot.deleteAt ?? null,
      general_preference: snapshot.generalPreference ?? null,
      rfpFiles,
      supportingFiles,
      proposalMeta,
      regenComments,
    };
  }, []);

  const recordVersionHistory = useCallback(
    (record: ParsedWordGenRecord) => {
      setGenerationHistory(prev => {
        const next = { ...prev };
        const existing = next[record.uuid] ? [...next[record.uuid]] : [];
        const index = existing.findIndex(item => item.gen_id === record.gen_id);
        if (index >= 0) {
          existing[index] = record;
        } else {
          existing.unshift(record);
        }
        existing.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        next[record.uuid] = existing;
        return next;
      });
    },
    [setGenerationHistory]
  );

  const findGenerationRecord = useCallback(
    (uuid: string, genId: string) => {
      const items = generationHistory[uuid];
      if (!items) {
        return null;
      }
      return items.find(item => item.gen_id === genId) ?? null;
    },
    [generationHistory]
  );

  const getLocalMarkdownForGen = useCallback(
    (uuid: string, genId: string): string | null => {
      const record = findGenerationRecord(uuid, genId);
      return record?.generated_markdown ?? null;
    },
    [findGenerationRecord]
  );

  const parsePptContent = (raw: any): ParsedPptContent => {
    const meta: ParsedPptContent["meta"] = {};
    const normalizeSlide = (slide: any): PptSlide => ({
      title: slide?.title || "",
      content: Array.isArray(slide?.content)
        ? slide.content
        : Array.isArray(slide)
          ? slide
          : [],
      notes: slide?.notes || "",
      layout_type: slide?.layout_type,
      layout_index: slide?.layout_index,
      chart_data: slide?.chart_data,
      image_path: slide?.image_path,
    });

    if (!raw) {
      return { slides: [], meta };
    }
    try {
      const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
      if (Array.isArray(parsed)) {
        return {
          slides: parsed.map(normalizeSlide),
          meta,
        };
      }
      if (parsed && typeof parsed === "object") {
        if (parsed.title) {
          meta.title = parsed.title;
        }
        if (parsed.template_id) {
          meta.template_id = parsed.template_id;
        }
        if (parsed.language) {
          meta.language = parsed.language;
        }
        if (parsed.stats && typeof parsed.stats === "object") {
          meta.stats = parsed.stats as PptStats;
        }
        const slidesSource = Array.isArray(parsed.slides) ? parsed.slides : [];
        return {
          slides: slidesSource.map(normalizeSlide),
          meta,
        };
      }
    } catch (err) {
      console.error("Failed to parse PPT content", err);
    }
    return { slides: [], meta };
  };

  const readJsonOrThrow = async (response: Response, fallbackMessage: string) => {
    const raw = await response.text();
    const payload = safeJsonParse<any>(raw, {});
    if (!response.ok) {
      const detail =
        (payload && typeof payload === "object" && typeof payload.detail === "string" && payload.detail) ||
        (payload && typeof payload === "object" && typeof payload.error === "string" && payload.error) ||
        raw ||
        fallbackMessage;
      throw new Error(detail);
    }
    return payload;
  };

  const loadPptSlidesForGen = useCallback(
    async (uuid: string, genId: string) => {
      if (!supabase) {
        setPptSlides([]);
        setPptPreviewUrl(null);
        setPptSummary(null);
        setActivePptGenId(null);
        setPptError("Supabase is not configured for PPT preview.");
        return;
      }
      setPptLoading(true);
      setPptError(null);
      setSelectedSlideIndex(0);
      try {
        const { data, error } = await supabase
          .from("ppt_gen")
          .select("generated_content, ppt_genid, proposal_ppt, created_at, ppt_template")
          .eq("uuid", uuid)
          .eq("gen_id", genId)
          .order("created_at", { ascending: false })
          .limit(1);

        if (error) {
          throw error;
        }

        const row = data?.[0];
        if (!row) {
          setPptSlides([]);
          setPptPreviewUrl(null);
          setPptSummary(null);
          setActivePptGenId(null);
          setPptError("No PPT found for this version yet.");
          return;
        }

        const { slides, meta } = parsePptContent(row.generated_content);
        const summary = {
          ...meta,
          template_id: meta.template_id || row.ppt_template || undefined,
        };
        setPptSlides(slides);
        setPptPreviewUrl(row.proposal_ppt || null);
        setActivePptGenId(row.ppt_genid || null);
        setPptSummary(summary);
        if (!slides.length) {
          setPptError("Slides are not ready yet for this version.");
        }
      } catch (err) {
        console.error("Failed to load PPT preview", err);
        setPptSlides([]);
        setPptPreviewUrl(null);
        setPptSummary(null);
        setActivePptGenId(null);
        setPptError("Unable to load PPT preview.");
      } finally {
        setPptLoading(false);
      }
    },
    [supabase]
  );

  const persistGenerationRecord = useCallback(
    async (snapshot: GenerationSnapshotInput, options?: { skipSupabase?: boolean }) => {
      const record = buildParsedRecord(snapshot);
      const shouldPersist = !options?.skipSupabase;

      try {
        if (supabase && shouldPersist) {
          const ensurePptGenRow = async () => {
            const attempts = [
              { ppt_genid: snapshot.genId, gen_id: snapshot.genId, uuid: snapshot.uuid },
              { ppt_genid: snapshot.genId, gen_id: snapshot.genId },
            ];
            let ensured = false;
            let lastError: any = null;

            for (const attempt of attempts) {
              const { error: pptError } = await supabase
                .from("ppt_gen")
                .upsert(attempt, { ignoreDuplicates: true });
              if (!pptError) {
                ensured = true;
                break;
              }
              const message = pptError.message?.toLowerCase?.() || "";
              if (
                message.includes("duplicate key value") ||
                message.includes("duplicate key") ||
                message.includes("violates unique constraint")
              ) {
                ensured = true;
                break;
              }
              if (message.includes('column "uuid" does not exist')) {
                lastError = pptError;
                continue;
              }
              lastError = pptError;
              console.warn("Failed attempt to ensure ppt_gen row", pptError);
            }

            if (!ensured) {
              const err = lastError || new Error("Unknown error ensuring ppt_gen row");
              throw err;
            }
          };

          await ensurePptGenRow();

          const deleteAtIso =
            snapshot.deleteAt ??
            new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString().split(".")[0].replace("T", " ");

          const recordPayload: Record<string, any> = {
            uuid: snapshot.uuid,
            gen_id: snapshot.genId,
            delete_at: deleteAtIso,
            general_preference: snapshot.generalPreference ?? null,
            regen_comments:
              snapshot.regenComments && snapshot.regenComments.length
                ? JSON.stringify(snapshot.regenComments)
                : null,
            proposal: snapshot.proposalSnapshot ? JSON.stringify(snapshot.proposalSnapshot) : null,
            generated_markdown: snapshot.generatedMarkdown,
            rfp_files: snapshot.rfpFiles && snapshot.rfpFiles.length ? snapshot.rfpFiles[0].url : null,
            supporting_files:
              snapshot.supportingFiles && snapshot.supportingFiles.length ? snapshot.supportingFiles[0].url : null,
          };

          const { error } = await supabase
            .from("word_gen")
            .upsert(recordPayload, { onConflict: "gen_id" });

          if (error) {
            throw error;
          }
        }
      } catch (err) {
        console.error("Failed to persist generation record", err);
      } finally {
        setSelectedUseCase(snapshot.uuid);
        setSelectedGenId(snapshot.genId);
        if (snapshot.rfpFiles) {
          setSavedRfpFiles(snapshot.rfpFiles);
        }
        if (snapshot.supportingFiles) {
          setSavedSupportingFiles(snapshot.supportingFiles);
        }
        recordVersionHistory(record);
      }

      return record;
    },
    [buildParsedRecord, recordVersionHistory, supabase]
  );

  const getGenerationLabel = useCallback((record: ParsedWordGenRecord) => {
    const [first] = record.regenComments || [];
    const base = first?.comment2?.trim() || first?.comment1?.trim();
    if (base) {
      const trimmed = base.replace(/\s+/g, " ").trim();
      return trimmed.length > 60 ? `${trimmed.substring(0, 60)}...` : trimmed;
    }

    if (record.proposalMeta.generatedDocument) {
      return record.proposalMeta.generatedDocument.replace(/_/g, " ");
    }

    return record.regenComments.length > 0 ? "Regenerated Version" : "Initial Version";
  }, []);

  const applyRecordToState = useCallback(
    (record: ParsedWordGenRecord) => {
      setSelectedUseCase(record.uuid);
      setSelectedGenId(record.gen_id);
      setJobUuid(record.uuid);
      setExpandedUseCases(prev => ({
        ...prev,
        [record.uuid]: true,
      }));

      const proposalSnapshot = record.proposalMeta || {};

      if (proposalSnapshot.config !== undefined) {
        setConfig(proposalSnapshot.config);
      } else if (record.general_preference) {
        setConfig(record.general_preference);
      }
      const snapshotLanguage = proposalSnapshot.language;
      if (snapshotLanguage) {
        versionLanguageRef.current[record.gen_id] = snapshotLanguage;
        setLanguage(snapshotLanguage);
        setCurrentVersionLanguage(snapshotLanguage);
      } else {
        const rememberedLanguage = versionLanguageRef.current[record.gen_id];
        if (rememberedLanguage) {
          setLanguage(rememberedLanguage);
          setCurrentVersionLanguage(rememberedLanguage);
        } else {
          setCurrentVersionLanguage(language);
        }
      }
      if (proposalSnapshot.docConfig) {
        setDocConfig(prev => ({
          ...prev,
          ...proposalSnapshot.docConfig
        }));
      }

      setWordLink(proposalSnapshot.wordLink ?? null);
      setPdfLinkSafely(proposalSnapshot.pdfLink ?? null);
      setPdfError(null);
      setIsPdfConverting(false);

      const markdown = record.generated_markdown || "";
      setMarkdownContent(markdown);
      setGeneratedDocument(
        proposalSnapshot.generatedDocument ||
          (record.regenComments.length ? "Regenerated_Proposal.docx" : "Generated_Proposal.docx")
      );
      setIsGenerated(Boolean(markdown || proposalSnapshot.wordLink || proposalSnapshot.pdfLink));
      setIsRegenerating(false);
      setIsRegenerationComplete(record.regenComments.length > 0);

      setSavedRfpFiles(record.rfpFiles);
      setSavedSupportingFiles(record.supportingFiles);
      setRfpFiles([]);
      setSupportingFiles([]);

      setCommentConfigList(record.regenComments || []);
      setCurrentCommentContent("");
      setCurrentCommentText("");
      pendingRegenCommentsRef.current = record.regenComments || [];

      setProcessingStage("");
      setUploadProgress(0);
    },
    [pendingRegenCommentsRef, setPdfLinkSafely, setPdfError, setIsPdfConverting]
  );

  const useCaseEntries = useMemo<UseCaseHistoryEntry[]>(() => {
    return Object.entries(generationHistory).map(([uuid, items]) => {
      const sortedItems = [...items].sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      const reference = sortedItems[sortedItems.length - 1] ?? sortedItems[0];
      const rfpName = reference?.rfpFiles?.[0]?.name || `Use Case ${uuid.substring(0, 8)}`;
      const latestCreatedAt = sortedItems[0]?.created_at ?? null;

      return {
        uuid,
        items: sortedItems,
        label: rfpName,
        latestVersion: sortedItems.length,
        latestCreatedAt,
      };
    });
  }, [generationHistory]);

  const sortedUseCases = useMemo(() => {
    const toTimestamp = (value: string | null) =>
      value ? new Date(value).getTime() : 0;

    return [...useCaseEntries].sort(
      (a, b) => toTimestamp(b.latestCreatedAt) - toTimestamp(a.latestCreatedAt)
    );
  }, [useCaseEntries]);

  useEffect(() => {
    if (selectedUseCase && selectedGenId) {
      loadPptSlidesForGen(selectedUseCase, selectedGenId);
      return;
    }
    resetPptState();
  }, [selectedUseCase, selectedGenId, loadPptSlidesForGen, resetPptState]);

  const toggleUseCaseExpansion = useCallback((uuid: string) => {
    setExpandedUseCases(prev => ({
      ...prev,
      [uuid]: !prev[uuid],
    }));
  }, []);

  const toggleVersionDetails = useCallback((genId: string) => {
    setExpandedVersionDetails(prev => ({
      ...prev,
      [genId]: !prev[genId],
    }));
  }, []);

  const handleDeleteGeneration = useCallback(async (record: ParsedWordGenRecord) => {
    const descriptor = record.regenComments.length > 0 ? 'regeneration' : 'generation';
    const label = getGenerationLabel(record);
    const confirmMessage = `Delete this ${descriptor}${label ? ` ("${label}")` : ''}? This action cannot be undone.`;
    if (typeof window === 'undefined' || !window.confirm(confirmMessage)) {
      return;
    }
    if (!supabase) {
      alert('Supabase configuration missing. Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
      return;
    }

    const prevUseCaseLength = generationHistory[record.uuid]?.length ?? 0;
    const willRemoveUseCase = prevUseCaseLength <= 1;

    setDeletingGenId(record.gen_id);
    try {
      const { error } = await supabase.from('word_gen').delete().eq('gen_id', record.gen_id);
      if (error) {
        throw error;
      }

      setGenerationHistory(prev => {
        const next = { ...prev };
        const prevItems = next[record.uuid] || [];
        const filtered = prevItems.filter(item => item.gen_id !== record.gen_id);
        if (filtered.length > 0) {
          next[record.uuid] = filtered;
        } else {
          delete next[record.uuid];
        }
        return next;
      });

      setExpandedVersionDetails(prev => {
        if (!prev[record.gen_id]) {
          return prev;
        }
        const next = { ...prev };
        delete next[record.gen_id];
        return next;
      });

      if (willRemoveUseCase) {
        setExpandedUseCases(prev => {
          if (!prev[record.uuid]) {
            return prev;
          }
          const next = { ...prev };
          delete next[record.uuid];
          return next;
        });
      }

      setSelectedGenId(prev => (prev === record.gen_id ? null : prev));
      if (willRemoveUseCase) {
        setSelectedUseCase(prev => (prev === record.uuid ? null : prev));
      }
    } catch (err) {
      console.error('Failed to delete generation', err);
      const message = err instanceof Error ? err.message : 'Unknown error';
      alert(`Failed to delete generation: ${message}`);
    } finally {
      setDeletingGenId(null);
    }
  }, [generationHistory, getGenerationLabel, supabase]);

  const handleSelectHistoryItem = useCallback((record: ParsedWordGenRecord) => {
    applyRecordToState(record);
    setExpandedVersionDetails(prev => ({
      ...prev,
      [record.gen_id]: true,
    }));
    setIsHistoryOpen(false);
  }, [applyRecordToState]);

  const activeUseCaseLabel = useMemo(() => {
    if (!selectedUseCase) {
      return null;
    }
    const matchFromSorted = sortedUseCases.find(item => item.uuid === selectedUseCase);
    if (matchFromSorted) {
      return matchFromSorted.label;
    }
    const items = generationHistory[selectedUseCase];
    if (!items || items.length === 0) {
      return null;
    }
    return items[0]?.rfpFiles?.[0]?.name || `Use Case ${selectedUseCase.substring(0, 8)}`;
  }, [generationHistory, selectedUseCase, sortedUseCases]);

  const activeVersionLabel = useMemo(() => {
    if (!selectedUseCase || !selectedGenId) {
      return null;
    }
    const useCaseEntry = sortedUseCases.find(item => item.uuid === selectedUseCase);
    const records = useCaseEntry?.items || generationHistory[selectedUseCase];
    if (!records) {
      return null;
    }
    const sortedRecords = useCaseEntry?.items
      ? useCaseEntry.items
      : [...records].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    const index = sortedRecords.findIndex(item => item.gen_id === selectedGenId);
    if (index === -1) {
      return null;
    }
    const versionNumber = sortedRecords.length - index;
    const label = getGenerationLabel(sortedRecords[index]);
    const formatted = label ? formatNameForSidebar(label, 36) : null;
    return formatted ? `V${versionNumber} • ${formatted}` : `V${versionNumber}`;
  }, [generationHistory, getGenerationLabel, selectedGenId, selectedUseCase, sortedUseCases]);

  const wordDownloadName = useMemo(() => getWordFileName(), [getWordFileName]);
  const selectedTemplateDetails = useMemo(
    () => pptTemplates.find((tpl) => tpl.id === selectedPptTemplate) || null,
    [pptTemplates, selectedPptTemplate]
  );
  const pptEmbedUrl = useMemo(() => {
    if (!pptPreviewUrl) {
      return null;
    }
    try {
      return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(pptPreviewUrl)}`;
    } catch (err) {
      console.warn("Failed to build PPT embed URL", err);
      return null;
    }
  }, [pptPreviewUrl]);

  const hasHistory = sortedUseCases.length > 0;
  const historyHelperText = hasHistory
    ? "Select a version from this session to review or restore it."
    : "Generate or regenerate to build history for this session.";

  const uploadFileToSupabase = async (
        file: File,
        bucket: string,
        uuid: string,
        index: number
      ): Promise<{ name: string; url: string; size: number }> => {
        if (!supabase) {
          throw new Error("Supabase client not configured");
        }
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

  // Check Supabase connection
  const checkSupabaseConnection = useCallback(async () => {
    if (!supabase) {
      setSupabaseConnected(false);
      return false;
    }
    try {
      const { error } = await supabase
        .from("word_gen")
        .select("id")
        .limit(1);

      if (error) {
        console.error("Supabase ping failed", error);
        setSupabaseConnected(false);
        return false;
      }

      setSupabaseConnected(true);
      return true;
    } catch (err) {
      console.error("Supabase check failed", err);
      setSupabaseConnected(false);
      return false;
    }
  }, [supabase]);

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

    if (fileType === 'rfp') {
      setSavedRfpFiles([]);
      setRfpFiles([file]);
    } else {
      setSavedSupportingFiles([]);
      setSupportingFiles([file]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, fileType: 'rfp' | 'supporting') => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (
      file.type === 'application/pdf' ||
      file.type === 'application/msword' ||
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ) {
      if (fileType === 'rfp') {
        setSavedRfpFiles([]);
        setRfpFiles([file]);
      } else {
        setSavedSupportingFiles([]);
        setSupportingFiles([file]);
      }
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
    const response = await fetch(apiPath(`/initialgen/${uuid}`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify({
        config: config,
        docConfig: docConfig,
        timestamp: new Date().toISOString(),
        language: language,
      }),
    });

    if (!response.ok) {
      const txt = await response.text().catch(() => "");
      throw new Error(`Backend /initialgen failed: ${response.status} ${txt}`);
    }

    let accumulatedMarkdown = "";
    await streamSseResponse(response, {
      onChunk: (chunk) => {
        accumulatedMarkdown += chunk;
        setMarkdownContent(accumulatedMarkdown);
      },
      onStage: (payload) => {
        const stageKey =
          typeof payload === "string"
            ? payload
            : (payload && typeof payload === "object" ? (payload as { stage?: string }).stage : "");
        if (stageKey) {
          setProcessingStage(resolveStageMessage(stageKey));
        }
      },
      onError: (payload) => {
        console.error("Initial generation stream error", payload);
      },
    });

    let docxShareUrl: string | null = null;
    try {
      const docRes = await fetch(apiPath(`/download/${uuid}`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          docConfig: docConfig,
          language: language,
        }),
      });

      if (!docRes.ok) {
        console.error("Failed to generate documents from /download");
      } else {
        const docResult = await docRes.json();
        docxShareUrl = docResult.proposal_word_url || null;
      }
    } catch (error) {
      console.error("Error generating documents:", error);
    } finally {
      setIsUploading(false);
    }

    return {
      docxShareUrl,
      proposalContent: accumulatedMarkdown,
    };
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

  const handlePdfDownload = useCallback(async () => {
    const pdfFileName = getPdfFileName();
    const wordFileName = getWordFileName();
    if (pdfLink) {
      if (pdfLink.startsWith("blob:")) {
        const anchor = document.createElement("a");
        anchor.href = pdfLink;
        anchor.download = pdfFileName;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      } else {
        try {
          setIsPdfConverting(true);
          setPdfError(null);
          const t = Date.now();
          const url = `${pdfLink}${pdfLink.includes('?') ? '&' : '?'}download=${encodeURIComponent(
            pdfFileName
          )}&t=${t}`;
          const response = await fetch(url);
          if (!response.ok) {
            throw new Error(`Failed to download PDF (${response.status})`);
          }
          const blob = await response.blob();
          const objectUrl = URL.createObjectURL(blob);
          setPdfLinkSafely(objectUrl);

          const anchor = document.createElement("a");
          anchor.href = objectUrl;
          anchor.download = pdfFileName;
          document.body.appendChild(anchor);
          anchor.click();
          anchor.remove();
        } catch (error) {
          console.error("Failed to download PDF", error);
          setPdfError("Unable to download PDF. Please try again.");
        } finally {
          setIsPdfConverting(false);
        }
      }
      return;
    }

    if (!wordLink) {
      alert("Word document is not yet available. Please generate it first.");
      return;
    }

    try {
      setIsPdfConverting(true);
      setPdfError(null);

      const t = Date.now();
      const downloadUrl = `${wordLink}${wordLink.includes('?') ? '&' : '?'}download=${encodeURIComponent(
        wordFileName
      )}&t=${t}`;
      const wordResponse = await fetch(downloadUrl);
      if (!wordResponse.ok) {
        throw new Error(`Failed to download Word document (${wordResponse.status})`);
      }

      const wordBlob = await wordResponse.blob();
      const originalName = wordFileName;
      const hasExtension = /\.[^./\\]+$/.test(originalName);
      const normalizedName = hasExtension ? originalName : `${originalName}.docx`;
      const extension = normalizedName.split('.').pop()?.toLowerCase();
      const mimeType =
        extension === "doc"
          ? "application/msword"
          : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

      const formData = new FormData();
      formData.append(
        "file",
        new File([wordBlob], normalizedName, {
          type: mimeType,
        })
      );

      const convertResponse = await fetch("/nextapi/convert", {
        method: "POST",
        body: formData,
      });

      if (!convertResponse.ok) {
        let message = `LibreOffice conversion failed (${convertResponse.status})`;
        const contentType = convertResponse.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const errorData = await convertResponse.json().catch(() => null);
          if (errorData?.error) {
            message = errorData.error;
          }
        } else {
          const text = await convertResponse.text().catch(() => "");
          if (text) {
            message = text;
          }
        }
        throw new Error(message);
      }

      const pdfBlob = await convertResponse.blob();
      const pdfUrl = URL.createObjectURL(pdfBlob);
      setPdfLinkSafely(pdfUrl);

      const anchor = document.createElement("a");
      anchor.href = pdfUrl;
      anchor.download = pdfFileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (error) {
      console.error("Failed to convert Word to PDF", error);
      setPdfError("Unable to download PDF. Please try again.");
    } finally {
      setIsPdfConverting(false);
    }
  }, [pdfLink, wordLink, jobUuid, setPdfLinkSafely, setPdfError, setIsPdfConverting, getPdfFileName, getWordFileName]);

  const handleGeneratePpt = async () => {
    if (!jobUuid || !selectedGenId) {
      alert("Select a proposal version before generating a presentation.");
      return;
    }
    if (!selectedPptTemplate) {
      alert("Select a PPT template before generating a presentation.");
      return;
    }

    const normalizedLanguage = normalizedLanguageLabel;
    setPreviewMode("ppt");
    setPptAction("initial");
    setPptActionStatus("Generating presentation...");
    setPptError(null);
    setPptLoading(true);

    try {
      const response = await fetch(apiPath("/ppt-initialgen"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          uuid: jobUuid,
          gen_id: selectedGenId,
          language: normalizedLanguage,
          template_id: selectedPptTemplate,
          user_preference: config,
        }),
      });

      const payload = await readJsonOrThrow(response, "Failed to generate presentation");
      const { slides, meta } = parsePptContent(payload.generated_content);
      const summary = {
        ...meta,
        template_id: meta.template_id || selectedPptTemplate,
      };

      setPptSlides(slides);
      setSelectedSlideIndex(0);
      setPptSummary(summary);
      setPptPreviewUrl(payload.ppt_url || null);
      setActivePptGenId(payload.ppt_genid || null);
      if (!slides.length) {
        setPptError("Slides will appear here once processing finishes.");
      }
      setPptActionStatus("Presentation ready.");
    } catch (error) {
      console.error("ppt-initialgen failed:", error);
      setPptError(error instanceof Error ? error.message : "Unable to generate presentation.");
      setPptActionStatus(null);
    } finally {
      setPptLoading(false);
      setPptAction(null);
    }
  };

  const handleRegeneratePpt = async () => {
    if (!jobUuid || !selectedGenId) {
      alert("Select a proposal version before regenerating a presentation.");
      return;
    }
    if (!activePptGenId) {
      alert("Generate a presentation first before requesting a PPT regeneration.");
      return;
    }
    if (!selectedPptTemplate) {
      alert("Select a PPT template before regenerating the presentation.");
      return;
    }

    const normalizedLanguage = normalizedLanguageLabel;
    const commentsPayload = commentConfigList.length ? commentConfigList : [];

    setPreviewMode("ppt");
    setPptAction("regen");
    setPptActionStatus("Applying feedback to presentation...");
    setPptError(null);
    setPptLoading(true);

    try {
      const response = await fetch(apiPath("/ppt-regeneration"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          uuid: jobUuid,
          gen_id: selectedGenId,
          ppt_genid: activePptGenId,
          language: normalizedLanguage,
          template_id: selectedPptTemplate,
          regen_comments: commentsPayload,
        }),
      });

      const payload = await readJsonOrThrow(response, "Failed to regenerate presentation");
      const { slides, meta } = parsePptContent(payload.generated_content);
      const summary = {
        ...meta,
        template_id: meta.template_id || selectedPptTemplate,
      };

      setPptSlides(slides);
      setSelectedSlideIndex(0);
      setPptSummary(summary);
      setPptPreviewUrl(payload.ppt_url || null);
      setActivePptGenId(payload.new_ppt_genid || null);
      if (!slides.length) {
        setPptError("Slides will appear here once processing finishes.");
      }
      setPptActionStatus("Presentation regenerated.");
    } catch (error) {
      console.error("ppt-regeneration failed:", error);
      setPptError(error instanceof Error ? error.message : "Unable to regenerate presentation.");
      setPptActionStatus(null);
    } finally {
      setPptLoading(false);
      setPptAction(null);
    }
  };

  const handleUpload = async () => {
    if (!supabase) {
      alert('Supabase configuration missing. Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
      return;
    }
    if (rfpFiles.length === 0) {
      alert('Please upload at least one RFP document');
      return;
    }

    if (!config.trim()) {
      alert('Please provide configuration preferences');
      return;
    }

    setPreviewMode("word");
    resetPptState();
    setMarkdownContent(null);
    setIsUploading(true);
    setUploadProgress(0);
    setProcessingStage('Starting generation...');
    resetPdfState();

    const progressInterval = simulateProgress();

    try {
      const uuid = generateUUID();
      const genId = generateUUID();
      setJobUuid(uuid);

      const supabaseConnected = await checkSupabaseConnection();
      if (!supabaseConnected) {
        alert("Supabase connection failed. Comments will not be saved.");
      }

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

      const rfpResults = await Promise.allSettled(
        rfpFiles.map((file, index) => uploadFileToSupabase(file, "rfp", uuid, index))
      );

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

      if (successfulRfpUploads.length === 0) {
        throw new Error("No RFP files were successfully uploaded. Cannot proceed.");
      }

      const storedRfpFiles = successfulRfpUploads.map(toStoredFileInfo);
      const storedSupportingFiles = successfulSupportingUploads.map(toStoredFileInfo);
      setSavedRfpFiles(storedRfpFiles);
      setSavedSupportingFiles(storedSupportingFiles);

      // Ensure Supabase has a row with our newly uploaded files before hitting the backend.
      await persistGenerationRecord({
        uuid,
        genId,
        rfpFiles: storedRfpFiles,
        supportingFiles: storedSupportingFiles,
        generalPreference: config,
        regenComments: [],
        proposalSnapshot: {
          config,
          language,
          docConfig,
        },
        generatedMarkdown: null,
      });

      setRfpFiles([]);
      setSupportingFiles([]);

      setProcessingStage('Generating proposal...');
      const { docxShareUrl, proposalContent } = await postUuidConfig(uuid, config);

      // Backend now updates Supabase after generation; only manage local state here.
      setWordLink(docxShareUrl);
      resetPdfState();
      setGeneratedDocument('Generated_Proposal.docx');
      versionLanguageRef.current[genId] = language;
      setCurrentVersionLanguage(language);
      setIsGenerated(true);
      if (proposalContent) {
        setMarkdownContent(proposalContent);
      }
      setSelectedUseCase(uuid);
      setSelectedGenId(genId);
      pendingRegenCommentsRef.current = [];
      setCommentConfigList([]);
      // await persistGenerationRecord({
      //   uuid,
      //   genId,
      //   rfpFiles: storedRfpFiles,
      //   supportingFiles: storedSupportingFiles,
      //   generalPreference: config,
      //   regenComments: [],
      //   proposalSnapshot: {
      //     config,
      //     language,
      //     docConfig,
      //     wordLink: docxShareUrl,
      //     generatedDocument: 'Generated_Proposal.docx',
      //   },
      //   generatedMarkdown: proposalContent ?? null,
      // }, { skipSupabase: true });
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

  const regenerateWithLanguageChange = async (
    commentsSnapshot: CommentItem[],
    regenDocConfig: typeof docConfig,
    regenConfig: string,
    regenLanguage: string
  ) => {
    if (!supabase) {
      alert('Supabase configuration missing. Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
      return;
    }
    if (!jobUuid) {
      alert('No job to regenerate. Please run Upload & Process first.');
      return;
    }

    setPreviewMode("word");
    resetPptState();
    const progressInterval = simulateProgress();
    setIsUploading(true);
    setIsRegenerating(true);
    setIsRegenerationComplete(false);
    setUploadProgress(0);
    setProcessingStage('Generating document in selected language...');
    setMarkdownContent(null);
    resetPdfState();

    try {
      pendingRegenCommentsRef.current = commentsSnapshot;
      if (commentsSnapshot.length) {
        try {
          await saveAllComments(supabase, jobUuid, commentsSnapshot);
        } catch (err) {
          console.warn('Failed to persist comments before regeneration', err);
        }
      }

      const newGenId = generateUUID();
      setSelectedGenId(newGenId);

      // Pre-register the new generation so the backend can find the uploaded files.
      // await persistGenerationRecord({
      //   uuid: jobUuid,
      //   genId: newGenId,
      //   rfpFiles: savedRfpFiles,
      //   supportingFiles: savedSupportingFiles,
      //   generalPreference: regenConfig,
      //   regenComments: commentsSnapshot,
      //   proposalSnapshot: {
      //     config: regenConfig,
      //     language: regenLanguage,
      //     docConfig: regenDocConfig,
      //   },
      //   generatedMarkdown: null,
      // }, { skipSupabase: true });

      const { docxShareUrl, proposalContent } = await postUuidConfig(jobUuid, regenConfig);

      setWordLink(docxShareUrl);
      setGeneratedDocument('Generated_Proposal.docx');
      setSelectedUseCase(jobUuid);
      versionLanguageRef.current[newGenId] = regenLanguage;
      setCurrentVersionLanguage(regenLanguage);
      setIsGenerated(true);
      if (proposalContent) {
        setMarkdownContent(proposalContent);
      }
      setIsRegenerationComplete(true);
      setIsRegenerating(false);
      pendingRegenCommentsRef.current = [];
      setCommentConfigList([]);
      setCurrentCommentContent("");
      setCurrentCommentText("");
      // await persistGenerationRecord({
      //   uuid: jobUuid,
      //   genId: newGenId,
      //   rfpFiles: savedRfpFiles,
      //   supportingFiles: savedSupportingFiles,
      //   generalPreference: regenConfig,
      //   regenComments: commentsSnapshot,
      //   proposalSnapshot: {
      //     config: regenConfig,
      //     language: regenLanguage,
      //     docConfig: regenDocConfig,
      //     wordLink: docxShareUrl,
      //     generatedDocument: 'Generated_Proposal.docx',
      //   },
      //   generatedMarkdown: proposalContent ?? null,
      // }, { skipSupabase: true });
    } catch (error) {
      console.error('Language change regeneration failed:', error);
      alert('Regenerate failed. Please try again.');
      setIsRegenerating(false);
      setIsRegenerationComplete(false);
    } finally {
      clearInterval(progressInterval);
      setTimeout(() => {
        setIsUploading(false);
        setUploadProgress(0);
        setProcessingStage('');
      }, 2000);
    }
  };

  const handleRegenerate = async () => {
    if (!supabase) {
      alert('Supabase configuration missing. Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
      return;
    }
    if (!jobUuid) {
      alert('No job to regenerate. Please run Upload & Process first.');
      return;
    }

    const baseGenId = selectedGenId;
    if (!baseGenId) {
      alert('No base version selected. Please choose a version to regenerate.');
      return;
    }
    const commentsSnapshot = commentConfigList.length ? [...commentConfigList] : [];
    const regenDocConfig = { ...docConfig };
    const regenConfig = config;
    const regenLanguage = language;
    const normalizedBaseLanguage = (currentVersionLanguage || '').toLowerCase();
    const normalizedTargetLanguage = (regenLanguage || '').toLowerCase();

    if (normalizedBaseLanguage !== normalizedTargetLanguage) {
      await regenerateWithLanguageChange(commentsSnapshot, regenDocConfig, regenConfig, regenLanguage);
      return;
    }

    setPreviewMode("word");
    resetPptState();
    try {
      pendingRegenCommentsRef.current = commentsSnapshot;
      setIsUploading(true);
      setIsRegenerating(true);
      setIsRegenerationComplete(false);
      setUploadProgress(0);
      setProcessingStage('Regenerating document...');
      console.log('Regenerating with commentConfig', commentsSnapshot);
      await saveAllComments(supabase, jobUuid, commentsSnapshot);

      setCommentConfigList([]);
      setCurrentCommentContent("");
      setCurrentCommentText("");

      setMarkdownContent(null);
      resetPdfState();

      const response = await fetch(apiPath("/regenerate"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify({
          uuid: jobUuid,
          gen_id: baseGenId,
          docConfig: regenDocConfig,
          timestamp: new Date().toISOString(),
          language: regenLanguage,
          commentConfig: commentsSnapshot,
        }),
      });

      if (!response.ok) {
        const txt = await response.text().catch(() => "");
        throw new Error(`Backend /regenerate failed: ${response.status} ${txt}`);
      }

      let streamedMarkdown = "";
      let regenWordLink: string | null = null;
      let regenGenId: string | null = null;
      let backendUpdatedMarkdown: string | null = null;

      await streamSseResponse(response, {
        onChunk: (chunk) => {
          streamedMarkdown += chunk;
          setMarkdownContent(streamedMarkdown);
        },
        onStage: (payload) => {
          const stageKey =
            typeof payload === "string"
              ? payload
              : (payload && typeof payload === "object" ? (payload as { stage?: string }).stage : "");
          if (stageKey) {
            setProcessingStage(resolveStageMessage(stageKey));
          }
        },
        onResult: (payload) => {
          if (payload && typeof payload === "object" && "markdown" in payload) {
            const fullMarkdown = (payload as { markdown?: string }).markdown;
            if (typeof fullMarkdown === "string") {
              streamedMarkdown = fullMarkdown;
              setMarkdownContent(fullMarkdown);
            }
          }
        },
        onDone: (payload) => {
          if (payload && typeof payload === "object") {
            const doneData = payload as { gen_id?: string; wordLink?: string; updated_markdown?: string | null };
            if (doneData.gen_id) {
              regenGenId = doneData.gen_id;
            }
            if (doneData.wordLink) {
              regenWordLink = doneData.wordLink;
            }
            if (typeof doneData.updated_markdown === "string") {
              backendUpdatedMarkdown = doneData.updated_markdown;
            }
          }
        },
        onError: (payload) => {
          console.error("Regenerate stream error", payload);
        },
      });

      const finalGenId = regenGenId || generateUUID();
      let regeneratedMarkdown: string | null = streamedMarkdown || null;
      const backendMarkdownClean =
        (typeof backendUpdatedMarkdown === "string" ? backendUpdatedMarkdown : "").trim();
      if (!regeneratedMarkdown && backendMarkdownClean) {
        regeneratedMarkdown = backendMarkdownClean;
      }
      if (!regeneratedMarkdown) {
        regeneratedMarkdown = getLocalMarkdownForGen(jobUuid, finalGenId);
      }

      const proposalSnapshot: StoredProposalSnapshot = {
        config: regenConfig,
        language: regenLanguage,
        docConfig: regenDocConfig,
        wordLink: regenWordLink,
        pdfLink: null,
        generatedDocument: 'Regenerated_Proposal.docx',
      };

      setProcessingStage('Finalizing regenerated proposal...');
      setUploadProgress(100);
      setSelectedGenId(finalGenId);
      setGeneratedDocument(proposalSnapshot.generatedDocument ?? 'Regenerated_Proposal.docx');
      setWordLink(proposalSnapshot.wordLink ?? null);
      versionLanguageRef.current[finalGenId] = regenLanguage;
      setCurrentVersionLanguage(regenLanguage);
      setPdfLinkSafely(proposalSnapshot.pdfLink ?? null);
      setPdfError(null);
      setIsPdfConverting(false);
      setMarkdownContent(regeneratedMarkdown);
      setIsRegenerationComplete(true);
      setIsRegenerating(false);
      pendingRegenCommentsRef.current = [];
      // await persistGenerationRecord({
      //   uuid: jobUuid,
      //   genId: finalGenId,
      //   regenComments: commentsSnapshot,
      //   generalPreference: regenConfig,
      //   rfpFiles: savedRfpFiles,
      //   supportingFiles: savedSupportingFiles,
      //   proposalSnapshot,
      //   generatedMarkdown: regeneratedMarkdown,
      // }, { skipSupabase: true });
    } catch (error) {
      console.error('Regenerate failed:', error);
      const message = error instanceof Error ? error.message : 'Regenerate failed. Please try again.';
      alert(message);
      setIsRegenerating(false);
      setIsRegenerationComplete(false);
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
    storedFiles = [],
    dragActive, 
    onDragEnter, 
    onDragLeave, 
    onDragOver, 
    onDrop, 
    onClick, 
    fileType,
    disabled = false,
  }: {
    title: string;
    files: File[];
    storedFiles?: StoredFileInfo[];
    dragActive: boolean;
    onDragEnter: (e: React.DragEvent) => void;
    onDragLeave: (e: React.DragEvent) => void;
    onDragOver: (e: React.DragEvent) => void;
    onDrop: (e: React.DragEvent) => void;
    onClick: () => void;
    fileType: 'rfp' | 'supporting';
    disabled?: boolean;
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
          className={`relative border-2 border-dashed rounded-md p-6 text-center transition-all duration-200
            ${dragActive 
              ? 'border-gray-400 bg-gray-50' 
              : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
            }
            ${disabled ? 'opacity-60 cursor-not-allowed pointer-events-none' : 'cursor-pointer'}`}
          onDragEnter={disabled ? undefined : onDragEnter}
          onDragLeave={disabled ? undefined : onDragLeave}
          onDragOver={disabled ? undefined : onDragOver}
          onDrop={disabled ? undefined : onDrop}
          onClick={disabled ? undefined : onClick}
          aria-disabled={disabled}
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

        {(files.length > 0 || storedFiles.length > 0) && (
          <div className="mt-4">
            <h4 className="text-xs font-medium text-gray-600 flex items-center gap-1 mb-2">
              <CheckCircle className="text-green-500" size={12} />
              Files ({files.length + storedFiles.length})
            </h4>
            {storedFiles.map((file, index) => (
              <div key={`stored-${index}`} className="flex items-center justify-between bg-white rounded p-2 mb-2 border border-gray-100">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <FileText className="text-gray-400 flex-shrink-0" size={14} />
                  <span className="text-xs text-gray-700 truncate">
                    {file.name}
                  </span>
                  {typeof file.size === 'number' && file.size > 0 && (
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {(file.size / 1024 / 1024).toFixed(1)}MB
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {file.url && (
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (disabled) {
                          return;
                        }
                        window.open(file.url, "_blank");
                      }}
                      className={`text-xs font-medium ${
                        disabled
                          ? 'text-gray-300 cursor-not-allowed'
                          : 'text-blue-500 hover:text-blue-600'
                      }`}
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            ))}
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
                    type="button"
                    disabled={disabled}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (disabled) {
                        return;
                      }
                      removeFile(index, fileType);
                    }}
                    className={`p-1 flex-shrink-0 ${
                      disabled
                        ? 'text-gray-300 cursor-not-allowed'
                        : 'text-gray-400 hover:text-red-500'
                    }`}
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

  const renderWordSidebarContent = () => (
    <>
      {/* Language Selection */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-4 p-4">
        <h3 className="text-sm font-medium text-gray-800 mb-2 flex items-center gap-2">
          <Globe className="text-gray-500" size={16} /> Language
        </h3>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={isProcessLocked}
            onClick={() => setLanguage('arabic')}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium border transition-colors
              ${language === 'arabic' 
                ? 'bg-blue-600 text-white border-blue-600' 
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }
              ${isProcessLocked ? 'cursor-not-allowed opacity-60' : ''}`}
          >
            Arabic
          </button>
          <button
            type="button"
            disabled={isProcessLocked}
            onClick={() => setLanguage('english')}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium border transition-colors
              ${language === 'english' 
                ? 'bg-blue-600 text-white border-blue-600' 
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }
              ${isProcessLocked ? 'cursor-not-allowed opacity-60' : ''}`}
          >
            English
          </button>
        </div>
      </div>

      <FileUploadZone
        title="RFP Documents"
        files={rfpFiles}
        storedFiles={savedRfpFiles}
        dragActive={dragActiveRfp}
        onDragEnter={(e) => handleDrag(e, setDragActiveRfp)}
        onDragLeave={(e) => handleDrag(e, setDragActiveRfp)}
        onDragOver={(e) => handleDrag(e, setDragActiveRfp)}
        onDrop={(e) => handleDrop(e, 'rfp')}
        onClick={() => rfpInputRef.current?.click()}
        fileType="rfp"
        disabled={isProcessLocked}
      />

      <FileUploadZone
        title="Supporting Files"
        files={supportingFiles}
        storedFiles={savedSupportingFiles}
        dragActive={dragActiveSupporting}
        onDragEnter={(e) => handleDrag(e, setDragActiveSupporting)}
        onDragLeave={(e) => handleDrag(e, setDragActiveSupporting)}
        onDragOver={(e) => handleDrag(e, setDragActiveSupporting)}
        onDrop={(e) => handleDrop(e, 'supporting')}
        onClick={() => supportingInputRef.current?.click()}
        fileType="supporting"
        disabled={isProcessLocked}
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
    </>
  );

  const renderPptSidebarContent = () => (
    <>
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-4">
        <div className="border-b border-gray-100 p-4">
          <h3 className="text-sm font-medium text-gray-800 flex items-center gap-2">
            <Layout className="text-gray-500" size={16} />
            Presentation
          </h3>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">PPT Template</label>
            <div className="mt-1 flex items-center gap-2">
              <select
                value={pptTemplates.length ? selectedPptTemplate : ""}
                onChange={(e) => setSelectedPptTemplate(e.target.value)}
                disabled={pptTemplatesLoading || isProcessLocked || !pptTemplates.length}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:ring-1 focus:ring-gray-400 focus:border-gray-400"
              >
                {pptTemplates.length === 0 ? (
                  <option value="">No templates detected</option>
                ) : (
                  pptTemplates.map((tpl) => (
                    <option key={tpl.id} value={tpl.id}>
                      {tpl.name} {tpl.version ? `(${tpl.version})` : ""}
                    </option>
                  ))
                )}
              </select>
              {pptTemplatesLoading && <Loader className="animate-spin text-gray-500" size={16} />}
            </div>
            {selectedTemplateDetails?.description && (
              <p className="text-xs text-gray-500 mt-2">
                {selectedTemplateDetails.description}
              </p>
            )}
          </div>
          <div className="text-xs space-y-1">
            {pptActionStatus && <p className="text-gray-600">{pptActionStatus}</p>}
            {pptTemplatesError && <p className="text-red-600">{pptTemplatesError}</p>}
            {pptError && <p className="text-red-600">{pptError}</p>}
            {!jobUuid && (
              <p className="text-gray-500">
                Generate or select a proposal version to unlock PPT controls.
              </p>
            )}
          </div>

          {pptSummary && (
            <div className="grid grid-cols-2 gap-3 text-xs text-gray-600">
              <div className="col-span-2">
                <p className="font-semibold text-gray-800">
                  {pptSummary.title || "Presentation"}
                </p>
                <p className="text-gray-500">
                  Template: {pptSummary.template_id || selectedPptTemplate || "-"} | Language:{" "}
                  {pptSummary.language || normalizedLanguageLabel}
                </p>
              </div>
              {[
                { label: "Slides", value: pptSummary.stats?.total_slides ?? pptSlides.length },
                { label: "Sections", value: pptSummary.stats?.sections },
                { label: "Charts", value: pptSummary.stats?.charts },
                { label: "Images", value: pptSummary.stats?.images },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded border border-gray-100 bg-gray-50 px-3 py-2"
                >
                  <p className="text-[10px] uppercase tracking-wide text-gray-400">
                    {item.label}
                  </p>
                  <p className="text-sm font-semibold text-gray-800">
                    {typeof item.value === "number" ? item.value : "-"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

    </>
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

  useEffect(() => {
    checkSupabaseConnection();
  }, [checkSupabaseConnection]);
 

  const isStreamingContent = Boolean(markdownContent) && (isUploading || isRegenerating);

  // Auto-scroll to bottom when markdown content updates during streaming
  React.useEffect(() => {
    if (!isStreamingContent || !markdownContainerRef.current) {
      return;
    }

    const container = markdownContainerRef.current;
    const scrollToBottom = () => {
      if (typeof container.scrollTo === 'function') {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth',
        });
      } else {
        container.scrollTop = container.scrollHeight;
      }
    };

    if (typeof window === 'undefined') {
      scrollToBottom();
      return;
    }

    const rafId = window.requestAnimationFrame(scrollToBottom);
    return () => window.cancelAnimationFrame(rafId);
  }, [markdownContent, isStreamingContent]);

  useEffect(() => {
    const hasWord = Boolean(markdownContent);
    const hasPpt = pptSlides.length > 0;

    if (previewMode === "word" && hasPpt && !hasWord) {
      setPreviewMode("ppt");
    }
  }, [markdownContent, pptSlides.length, previewMode]);

  const isPptBusy = pptAction !== null;
  const isDocLocked = isUploading || isPdfConverting || deletingGenId !== null || isRegenerating;
  const isProcessLocked = isDocLocked || isPptBusy;
  const canGeneratePpt = Boolean(jobUuid && selectedGenId && selectedPptTemplate);
  const canRegeneratePpt = Boolean(canGeneratePpt && activePptGenId);
  const selectedSlideSafeIndex = useMemo(() => {
    if (!pptSlides.length) {
      return -1;
    }
    return Math.min(selectedSlideIndex, pptSlides.length - 1);
  }, [pptSlides.length, selectedSlideIndex]);
  const selectedSlide = useMemo(() => {
    if (selectedSlideSafeIndex < 0) {
      return null;
    }
    return pptSlides[selectedSlideSafeIndex] || null;
  }, [pptSlides, selectedSlideSafeIndex]);
  const selectedSlidePreviewLines = useMemo(
    () => getSlidePreviewLines(selectedSlide || undefined, 4),
    [selectedSlide]
  );
  const canOpenPptPreview = Boolean(
    pptSlides.length ||
      pptLoading ||
      pptError ||
      (jobUuid && selectedGenId)
  );
  const hasGeneratedPpt = Boolean(activePptGenId || pptSlides.length);
  const pptPrimaryActionLabel = hasGeneratedPpt ? "Regenerate PPT" : "Generate PPT";
  const pptPrimaryDisabled = hasGeneratedPpt || !canGeneratePpt || isProcessLocked || pptTemplatesLoading;
  const showWordFormatting = previewMode === "word" && !isRegenerating && !generatedDocument && !markdownContent;

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }
    const previousCursor = document.body.style.cursor;
    document.body.style.cursor = isProcessLocked ? 'wait' : '';
    return () => {
      document.body.style.cursor = previousCursor;
    };
  }, [isProcessLocked]);

  const handlePrimaryPptClick = useCallback(() => {
    if (pptPrimaryDisabled) {
      return;
    }
    if (hasGeneratedPpt) {
      return;
    }
    handleGeneratePpt();
  }, [handleGeneratePpt, hasGeneratedPpt, pptPrimaryDisabled]);

  const [comment1, setComment1] = useState<string>("");
  const [comment2, setComment2] = useState<string>("");

  const handleCommentChange1 = (value: string | boolean) => {
    setComment1(String(value));
  };

  const handleCommentChange2 = (value: string | boolean) => {
    setComment2(String(value));
  };

  return (
    <>
      <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet" />

      <div
        className="relative h-screen bg-gray-50 overflow-hidden"
        style={{
          fontFamily: 'JetBrains Mono, monospace',
          cursor: isProcessLocked ? 'wait' : 'auto',
        }}
        aria-busy={isProcessLocked}
        aria-live={isProcessLocked ? 'polite' : undefined}
      >
        <div className="h-full">
          <div
            className={`fixed inset-0 z-40 flex transition-all duration-300 ${
              isHistoryOpen ? '' : 'pointer-events-none'
            }`}
          >
          <aside
            className={`w-[360px] max-w-full bg-white border-r border-gray-200 shadow-2xl flex flex-col overflow-hidden transform transition-transform duration-300 ease-in-out ${
              isHistoryOpen ? 'translate-x-0 pointer-events-auto' : '-translate-x-full pointer-events-none'
            }`}
            role={isHistoryOpen ? 'dialog' : undefined}
            aria-modal={isHistoryOpen || undefined}
            aria-hidden={!isHistoryOpen}
            aria-label="Version history"
          >
            <div className="px-5 py-4 border-b border-gray-100">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-sm font-semibold text-gray-800">
                    <Database size={16} />
                    Version History
                  </div>
                  <p className="mt-1 text-[11px] leading-4 text-gray-500">
                    {historyHelperText}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsHistoryOpen(false)}
                  className="text-gray-400 hover:text-gray-600"
                  aria-label="Close version history"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {!hasHistory ? (
                <div className="flex items-center justify-center h-full px-6 text-center text-[11px] text-gray-500">
                  No versions found yet. Generate a proposal to start tracking history.
                </div>
              ) : (
                sortedUseCases.map((useCase) => {
                  const isExpanded = expandedUseCases[useCase.uuid] ?? (selectedUseCase === useCase.uuid);
                  const displayUseCaseLabel = formatNameForSidebar(useCase.label, 48);
                  return (
                    <div key={useCase.uuid} className="border-b border-gray-100">
                      <button
                        type="button"
                        onClick={() => toggleUseCaseExpansion(useCase.uuid)}
                        className="w-full px-5 py-4 flex items-center justify-between gap-3 hover:bg-gray-50 transition-colors text-left"
                      >
                        <div className="flex-1 pr-2">
                          <p className="text-sm font-medium text-gray-800 truncate" title={useCase.label}>
                            {displayUseCaseLabel}
                          </p>
                          <div className="mt-1 flex items-center justify-between text-[11px] text-gray-500 gap-2">
                            <span className="truncate">{formatRelativeTimestamp(useCase.latestCreatedAt)}</span>
                            <span className="font-semibold text-gray-700">V{useCase.latestVersion}</span>
                          </div>
                          <p className="text-[10px] text-gray-400">{useCase.items.length} saved versions</p>
                        </div>
                        {isExpanded ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
                      </button>

                      {isExpanded && (
                        <ul className="bg-gray-50 border-t border-gray-100">
                          {useCase.items.map((item, index) => {
                            const versionNumber = useCase.items.length - index;
                            const isActive = selectedGenId === item.gen_id;
                            const label = getGenerationLabel(item);
                            const displayVersionLabel = formatNameForSidebar(label || `Generation ${versionNumber}`, 44);
                            const shortGenId = item.gen_id ? `${item.gen_id.slice(0, 8)}…` : '';
                            const versionExpanded = expandedVersionDetails[item.gen_id] ?? false;
                            const generalPreferenceSnippet =
                              item.general_preference && item.general_preference.trim().length
                                ? item.general_preference.trim()
                                : null;

                            return (
                              <li
                                key={item.gen_id}
                                className="relative border-b border-gray-100 last:border-b-0 pl-5"
                              >
                                <div className="absolute left-2 top-0 bottom-0 border-l border-gray-200 pointer-events-none" />
                                <div className="absolute left-1.5 top-4 w-2 h-2 rounded-full bg-gray-200 border border-white pointer-events-none" />
                                <div className="flex items-stretch gap-2">
                                  <button
                                    type="button"
                                    onClick={() => handleSelectHistoryItem(item)}
                                    className={`flex-1 px-4 py-3 text-left text-xs transition-colors rounded-l-lg border ${
                                      isActive
                                        ? 'bg-white text-blue-600 border-blue-300 shadow-sm'
                                        : 'bg-transparent hover:bg-white text-gray-700 border-transparent hover:border-gray-200'
                                    }`}
                                  >
                                    <div className="flex items-start justify-between gap-2">
                                      <span className="truncate flex items-center gap-2">
                                        <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                                          V{versionNumber}
                                        </span>
                                        <span className="truncate" title={label || `Generation ${versionNumber}`}>{displayVersionLabel}</span>
                                      </span>
                                      <span className="flex-shrink-0 text-[10px] text-gray-400 whitespace-nowrap">
                                        {formatSidebarTimestamp(item.created_at)}
                                      </span>
                                    </div>
                                    {shortGenId && (
                                      <p className="mt-1 text-[9px] text-gray-400 font-mono">ID: {shortGenId}</p>
                                    )}
                                    {item.regenComments.length > 0 && (
                                      <p className="mt-1 text-[10px] text-gray-500 truncate">
                                        {item.regenComments[0].comment2 || item.regenComments[0].comment1}
                                      </p>
                                    )}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => toggleVersionDetails(item.gen_id)}
                                    className="px-3 py-3 text-gray-500 border border-gray-200 border-l-0 bg-white hover:text-gray-700"
                                    aria-label={versionExpanded ? "Hide version details" : "Show version details"}
                                  >
                                    {versionExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteGeneration(item)}
                                    className="px-3 py-3 text-red-500 border border-gray-200 border-l-0 bg-white hover:text-red-600 rounded-r-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                    aria-label={`Delete this ${item.regenComments.length > 0 ? 'regeneration' : 'generation'}`}
                                    title="Delete this version"
                                    disabled={deletingGenId === item.gen_id}
                                  >
                                    {deletingGenId === item.gen_id ? (
                                      <Loader size={14} className="animate-spin" />
                                    ) : (
                                      <Trash2 size={14} />
                                    )}
                                  </button>
                                </div>
                                {versionExpanded && (
                                  <div className="ml-6 mr-4 mb-3 mt-2 rounded border border-gray-200 bg-white p-3 text-[11px] text-gray-600 space-y-2">
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-gray-700">Created:</span>
                                      <span>{new Date(item.created_at).toLocaleString()}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-gray-700">Gen ID:</span>
                                      <span className="font-mono text-[10px] text-gray-500 break-all">{item.gen_id}</span>
                                    </div>
                                    {generalPreferenceSnippet && (
                                      <div>
                                        <p className="font-medium text-gray-700">Preference:</p>
                                        <p className="mt-1 text-[11px] text-gray-500 whitespace-pre-wrap max-h-20 overflow-hidden">
                                          {generalPreferenceSnippet}
                                        </p>
                                      </div>
                                    )}
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-gray-700">Comments:</span>
                                      <span>{item.regenComments.length}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-gray-700">Status:</span>
                                      <span>
                                        {item.delete_at
                                          ? `Scheduled to archive on ${new Date(item.delete_at).toLocaleString()}`
                                          : 'Active'}
                                      </span>
                                    </div>
                                  </div>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </aside>
          <div
            className={`flex-1 bg-black/30 transition-opacity duration-300 ${
              isHistoryOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
            }`}
            onClick={() => setIsHistoryOpen(false)}
            aria-hidden="true"
          />
        </div>

        <div className="flex h-full">
          {/* Left Panel - Upload Form */}
          <div className="w-96 bg-white border-r border-gray-200 h-full p-6 overflow-y-auto">
            <div className="mb-8 flex items-start gap-4">
              <button
                type="button"
                onClick={() => setIsHistoryOpen(prev => !prev)}
                className={`flex-shrink-0 flex items-center justify-center h-10 w-10 rounded-md border transition-all duration-200 ${
                  isHistoryOpen
                    ? 'bg-gray-900 text-white border-gray-900 shadow'
                    : 'bg-white text-gray-700 border-gray-200 hover:shadow'
                }`}
                aria-label={isHistoryOpen ? 'Close version history' : 'Open version history'}
                title={isHistoryOpen ? 'Close version history' : 'Open version history'}
                aria-pressed={isHistoryOpen}
                aria-expanded={isHistoryOpen}>
                <Menu size={18} />
              </button>
              <div className="flex-1 min-w-0">
                <h1 className="text-lg font-semibold text-gray-900 mb-2">
                  RFP Processing
                </h1>
                <p className="text-xs text-gray-600 leading-relaxed">
                  Upload documents and configure your proposal generation
                </p>
                {supabaseEnvMissing && (
                  <div className="mt-3 p-3 rounded-md border border-red-200 bg-red-50 text-[11px] text-red-700">
                    Supabase credentials are not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to enable uploads, history tracking, and regenerations.
                  </div>
                )}
                {activeUseCaseLabel && (
                  <div className="mt-3 space-y-1 text-xs text-gray-500">
                    <p className="flex items-center gap-2 min-w-0">
                      <CheckCircle2 className="text-green-500" size={14} />
                      <span className="text-gray-700 whitespace-nowrap">Active use case:</span>
                      <span
                        className="flex-1 min-w-0 text-gray-900 font-medium truncate"
                        title={activeUseCaseLabel}
                      >
                        {formatNameForSidebar(activeUseCaseLabel, 48)}
                      </span>
                    </p>
                    {activeVersionLabel && (
                      <p className="flex items-center gap-2 min-w-0">
                        <ChevronRight size={12} className="text-gray-400" />
                        <span className="text-gray-700 whitespace-nowrap">Current version:</span>
                        <span
                          className="flex-1 min-w-0 text-gray-900 font-medium truncate"
                          title={activeVersionLabel}
                        >
                          {formatNameForSidebar(activeVersionLabel, 52)}
                        </span>
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-3">
              {previewMode === "ppt" ? renderPptSidebarContent() : renderWordSidebarContent()}

              {generatedDocument && <GeneratedDocumentSection />}

              <div className="pt-2">
                {!isGenerated ? (
                  <button
                    onClick={handleUpload}
                    disabled={supabaseEnvMissing || isDocLocked || rfpFiles.length === 0 || !config.trim()}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded text-sm font-medium transition-all duration-200
                      ${supabaseEnvMissing || isDocLocked || rfpFiles.length === 0 || !config.trim()
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
                        {supabaseEnvMissing ? (
                          <>
                            <AlertCircle size={16} />
                            Supabase Config Needed
                          </>
                        ) : (
                          <>
                            <Send size={16} />
                            Upload & Process
                          </>
                        )}
                      </>
                    )}
                  </button>
                ) : (
                  <button
                    onClick={handleRegenerate}
                    disabled={supabaseEnvMissing || isDocLocked}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded text-sm font-medium transition-all duration-200
                      ${supabaseEnvMissing || isDocLocked
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
                        {supabaseEnvMissing ? (
                          <>
                            <AlertCircle size={16} />
                            Supabase Config Needed
                          </>
                        ) : (
                          <>
                            <Send size={16} />
                            Regenerate Document
                          </>
                        )}
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Center Panel - Loading/Output Display */}
          <div className="flex-1 h-full p-6 min-w-0 flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between mb-4 gap-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-gray-800">Preview</span>
                {processingStage && (
                  <span className="text-xs text-gray-500 truncate max-w-[260px]" title={processingStage}>
                    {processingStage}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {pptPreviewUrl && (
                  <button
                    type="button"
                    onClick={() => window.open(pptPreviewUrl, "_blank")}
                    className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-md text-gray-700 hover:border-blue-400 hover:text-blue-600 transition-colors"
                  >
                    Download PPT
                  </button>
                )}
                <div className="bg-gray-100 rounded-full p-1 flex items-center">
                  <button
                    type="button"
                    onClick={() => setPreviewMode("word")}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-full transition-colors ${
                      previewMode === "word" ? "bg-white shadow text-gray-900" : "text-gray-600"
                    }`}
                    aria-pressed={previewMode === "word"}
                  >
                    Word
                  </button>
                  <button
                    type="button"
                    disabled={!canOpenPptPreview}
                    onClick={() => setPreviewMode("ppt")}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-full transition-colors ${
                      previewMode === "ppt" ? "bg-white shadow text-gray-900" : "text-gray-600"
                    } ${!canOpenPptPreview ? "opacity-50 cursor-not-allowed" : ""}`}
                    aria-pressed={previewMode === "ppt"}
                  >
                    PPT
                  </button>
                </div>
              </div>
            </div>
            <div className="flex-1 min-h-0">
              {previewMode === "ppt" ? (
                <div className="flex flex-col gap-4 h-full">
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 flex-1 min-h-[420px] overflow-hidden select-text">
                    {pptEmbedUrl ? (
                      <iframe
                        title="PowerPoint preview"
                        src={pptEmbedUrl}
                        className="w-full h-full border-0"
                        allowFullScreen
                      />
                    ) : (
                      <div className="h-full w-full flex items-center justify-center p-6 text-sm text-gray-600">
                        {pptLoading ? (
                          "Loading PPT preview..."
                        ) : selectedSlide && selectedSlidePreviewLines.length > 0 ? (
                          <div className="w-full max-w-3xl mx-auto text-left space-y-2">
                            <p className="text-base font-semibold text-gray-800">
                              Slide {selectedSlideSafeIndex + 1}
                              {selectedSlide.title ? ` - ${selectedSlide.title}` : ""}
                            </p>
                            <ul className="list-disc list-inside space-y-1 text-sm text-gray-600">
                              {selectedSlidePreviewLines.map((line, idx) => (
                                <li key={`slide-preview-${idx}`}>{line}</li>
                              ))}
                            </ul>
                            {pptError && <p className="text-xs text-red-600">{pptError}</p>}
                          </div>
                        ) : (
                          <span>{pptError || "PPT preview will appear here after generation."}</span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handlePrimaryPptClick}
                      disabled={pptPrimaryDisabled}
                      className={`px-4 py-2 rounded-md text-sm font-medium border transition-colors ${
                        pptPrimaryDisabled
                          ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                          : "bg-blue-600 text-white border-blue-600 hover:bg-blue-700"
                      }`}
                    >
                      {pptPrimaryActionLabel}
                    </button>
                  </div>
                  {hasGeneratedPpt && (
                    <p className="text-xs text-gray-500 text-right">
                      Regeneration is currently disabled after the first PPT generation.
                    </p>
                  )}
                </div>
              ) : isUploading && !markdownContent ? (
                <LoadingDisplay />
              ) : !isUploading && !markdownContent ? (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex items-center justify-center">
                  <div className="text-center">
                    <FileText className="mx-auto mb-4 text-gray-300" size={64} />
                    <h3 className="text-lg font-medium text-gray-600 mb-2">Ready to Process</h3>
                    <p className="text-sm text-gray-500">
                      Upload your RFP documents and click "Upload & Process" to begin
                    </p>
                  </div>
                </div>
              ) : (
                <OutputDocumentDisplay
                  generatedDocument={generatedDocument}
                  markdownContent={markdownContent}
                  wordLink={wordLink}
                  pdfLink={pdfLink}
                  jobUuid={jobUuid}
                  isRegenerating={isRegenerating}
                  isRegenerationComplete={isRegenerationComplete}
                  docConfig={docConfig}
                  onPdfDownload={handlePdfDownload}
                  isPdfConverting={isPdfConverting}
                  pdfError={pdfError}
                  wordDownloadName={wordDownloadName}
                  markdownRef={markdownContainerRef}
                />
              )}
            </div>
          </div>
          

          {/* Right Panel - Document Configuration (Word only) */}
          {previewMode === "word" && (
            <div className="w-96 p-6 border-l border-gray-200 bg-white h-full overflow-y-auto">
              {showWordFormatting && (
                <>
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
                </>
              )}

              {/* Comments ConfigSection (visible after Word is generated) */}
              {previewMode === "word" && Boolean(markdownContent || generatedDocument) && (
                <ConfigSection
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
                    value={currentCommentContent}
                    onChange={(value) => setCurrentCommentContent(value as string)}
                    placeholder="Enter the Content"
                    isTextarea={true}
                    rows={6}
                  />
                </div>
                <div className="grid grid-cols-1 gap-4">
                  <InputField
                    label="Comment"
                    value={currentCommentText}
                    onChange={(value) => setCurrentCommentText(value as string)}
                    placeholder="Enter the Comment"
                    isTextarea={true}
                    rows={6}
                  />
                </div>
                <div className="mt-2">
                  <button
                    type="button"
                    disabled={isProcessLocked}
                    className={`px-4 py-2 rounded text-sm transition-colors ${
                      isProcessLocked
                        ? 'bg-blue-300 text-white/70 cursor-not-allowed'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                    }`}
                    onClick={() => {
                      if (isProcessLocked) {
                        return;
                      }
                      setCommentConfigList(prev => [
                        ...prev,
                        { comment1: currentCommentContent, comment2: currentCommentText }
                      ]);
                      setCurrentCommentContent('');
                      setCurrentCommentText('');
                    }}
                  >
                    Add Comment
                  </button>
                </div>
              </ConfigSection>
            )}

              {/* Header & Footer */}
              {showWordFormatting && (
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
              )}
            </div>
          )}

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
    </div>
    </div>
    </>
  );
};

export default UploadPage;

