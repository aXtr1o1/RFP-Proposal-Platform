"use client";

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Upload, FileText, Settings, Send, X, CheckCircle, ChevronDown, ChevronRight, ChevronUp, AlignLeft, Text ,Table, Layout, Type, Download, Globe, Loader, Database, CheckCircle2, AlertCircle, Menu } from 'lucide-react';
import { createClient } from '@supabase/supabase-js';
import MarkdownRenderer from './MarkdownRenderer.tsx';
import { saveAllComments } from "./utils";

const DEFAULT_API_BASE_URL = "http://20.28.48.139:8000/api"; 
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

const safeJsonParse = <T,>(input: string | null | undefined, fallback: T): T => {
  if (!input) {
    return fallback;
  }

  try {
    return JSON.parse(input) as T;
  } catch (error) {
    console.warn("Failed to parse JSON value", error);
    return fallback;
  }
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

const normalizeStoredFileList = (raw: string | null): StoredFileInfo[] => {
  if (!raw) {
    return [];
  }

  const buildFromUnknown = (value: unknown): StoredFileInfo | null => {
    if (!value) {
      return null;
    }

    if (typeof value === "string") {
      return {
        name: extractFileNameFromUrl(value),
        url: value,
      };
    }

    if (typeof value === "object" && "url" in value) {
      const obj = value as { url?: string; name?: string; size?: number };
      if (!obj.url) {
        return null;
      }
      return {
        name: obj.name || extractFileNameFromUrl(obj.url),
        url: obj.url,
        size: obj.size ?? null,
      };
    }

    return null;
  };

  const parsed = safeJsonParse<unknown>(raw, raw);

  if (Array.isArray(parsed)) {
    return parsed
      .map(buildFromUnknown)
      .filter((item): item is StoredFileInfo => Boolean(item));
  }

  const single = buildFromUnknown(parsed);
  return single ? [single] : [];
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

const interpretProposalString = (value: string): StoredProposalSnapshot => {
  const snapshot: StoredProposalSnapshot = {};
  if (!value) {
    return snapshot;
  }
  if (/^https?:\/\//i.test(value)) {
    snapshot.wordLink = value;
  } else {
    snapshot.generatedDocument = value;
  }
  return snapshot;
};

const parseProposalSnapshot = (raw: string | null | undefined): StoredProposalSnapshot => {
  if (!raw) {
    return {};
  }
  const trimmed = raw.trim();
  if (!trimmed) {
    return {};
  }

  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (typeof parsed === "string") {
        return interpretProposalString(parsed);
      }
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as StoredProposalSnapshot;
      }
    } catch (error) {
      console.warn("Failed to parse proposal JSON; treating value as string", error);
    }
  }

  return interpretProposalString(trimmed);
};

const mapRowToRecord = (row: WordGenRow): ParsedWordGenRecord => ({
  ...row,
  rfpFiles: normalizeStoredFileList(row.rfp_files),
  supportingFiles: normalizeStoredFileList(row.supporting_files),
  proposalMeta: parseProposalSnapshot(row.proposal),
  regenComments: safeJsonParse<CommentItem[]>(row.regen_comments, []),
});

const toStoredFileInfo = (file: { name: string; url: string; size?: number | null }): StoredFileInfo => ({
  name: file?.name || extractFileNameFromUrl(file?.url),
  url: file?.url || "",
  size: file?.size ?? null,
});


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
      <div className="flex-1 overflow-auto p-6 bg-gray-50">
        {markdownContent && (
          <div className="max-w-4xl max-h-screen mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-8 content-display-area" style={{ overflow: "scroll", backgroundColor: '#ffffff', color: '#000000' }}>
            <MarkdownRenderer markdownContent={markdownContent} docConfig={docConfig} />
          </div>
        ) }
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
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [expandedUseCases, setExpandedUseCases] = useState<Record<string, boolean>>({});
  const [expandedVersionDetails, setExpandedVersionDetails] = useState<Record<string, boolean>>({});
  const [selectedUseCase, setSelectedUseCase] = useState<string | null>(null);
  const [selectedGenId, setSelectedGenId] = useState<string | null>(null);
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
  const markdownContainerRef = useRef<HTMLDivElement>(null);

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);

    try {
      if (!supabase) {
        setHistoryError("Supabase client not configured");
        setHistoryLoading(false);
        return;
      }
      const { data, error } = await supabase
        .from("word_gen")
        .select("*")
        .order("created_at", { ascending: false });

      if (error) {
        throw error;
      }

      const rows = (data ?? []) as WordGenRow[];
      const grouped: Record<string, ParsedWordGenRecord[]> = {};

      rows.forEach((row) => {
        const parsed = mapRowToRecord(row);
        if (parsed.proposalMeta?.language) {
          versionLanguageRef.current[parsed.gen_id] = parsed.proposalMeta.language;
        }
        if (!grouped[parsed.uuid]) {
          grouped[parsed.uuid] = [];
        }
        grouped[parsed.uuid].push(parsed);
      });

      setGenerationHistory(grouped);
    } catch (err) {
      console.error("Failed to load generation history", err);
      const message = err instanceof Error ? err.message : "Failed to load history";
      setHistoryError(message);
    } finally {
      setHistoryLoading(false);
    }
  }, [supabase]);

  const persistGenerationRecord = useCallback(
    async (payload: {
      uuid: string;
      genId: string;
      rfpFiles?: StoredFileInfo[];
      supportingFiles?: StoredFileInfo[];
      regenComments?: CommentItem[];
      generalPreference?: string;
    }) => {
      try {
        if (!supabase) {
          throw new Error("Supabase client not configured");
        }
        setHistoryError(null);

        const ensurePptGenRow = async () => {
          const attempts = [
            { ppt_genid: payload.genId, gen_id: payload.genId, uuid: payload.uuid },
            { ppt_genid: payload.genId, gen_id: payload.genId },
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
            if (message.includes("duplicate key value") || message.includes("duplicate key") || message.includes("violates unique constraint")) {
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

        const deleteAtDate = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
        const deleteAtIso = deleteAtDate.toISOString().split(".")[0].replace("T", " ");
        const recordPayload: Record<string, any> = {
          uuid: payload.uuid,
          gen_id: payload.genId,
          delete_at: deleteAtIso,
        };
        if (payload.generalPreference !== undefined) {
          recordPayload.general_preference = payload.generalPreference || null;
        }

        if (payload.rfpFiles !== undefined) {
          const rfpList = payload.rfpFiles ?? [];
          const primaryRfpUrl = rfpList.find(file => file?.url)?.url ?? null;
          recordPayload.rfp_files = primaryRfpUrl;
        }
        if (payload.supportingFiles !== undefined) {
          const supportList = payload.supportingFiles ?? [];
          const primarySupportingUrl = supportList.find(file => file?.url)?.url ?? null;
          recordPayload.supporting_files = primarySupportingUrl;
        }
        if (payload.regenComments !== undefined) {
          recordPayload.regen_comments =
            payload.regenComments && payload.regenComments.length
              ? JSON.stringify(payload.regenComments)
              : null;
        }

        const { data, error } = await supabase
          .from("word_gen")
          .upsert(recordPayload, { onConflict: "gen_id" })
          .select()
          .single<WordGenRow>();

        if (error) {
          throw error;
        }

        const parsed = mapRowToRecord(data);
        setSelectedUseCase(parsed.uuid);
        setSelectedGenId(parsed.gen_id);
        setSavedRfpFiles(parsed.rfpFiles);
        setSavedSupportingFiles(parsed.supportingFiles);
        await refreshHistory();
        return parsed;
      } catch (err) {
        console.error("Failed to persist generation record", err);
        throw err;
      }
    },
    [refreshHistory, supabase]
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

  const sortedUseCases = useMemo(() => {
    const entries = Object.entries(generationHistory).map(([uuid, items]) => {
      const sortedItems = [...items].sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      const reference = sortedItems[sortedItems.length - 1] ?? sortedItems[0];
      const rfpName = reference?.rfpFiles?.[0]?.name || `Use Case ${uuid.substring(0, 8)}`;
      const isArchived = sortedItems.every(item => Boolean(item.delete_at));

      return {
        uuid,
        items: sortedItems,
        label: rfpName,
        isArchived,
        latestVersion: sortedItems.length,
      };
    });

    return entries.sort((a, b) => {
      if (a.isArchived !== b.isArchived) {
        return a.isArchived ? 1 : -1;
      }
      const latestA = a.items[0]?.created_at || "";
      const latestB = b.items[0]?.created_at || "";
      return new Date(latestB).getTime() - new Date(latestA).getTime();
    });
  }, [generationHistory]);

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
    return new Promise<{ docxShareUrl: string | null; proposalContent: string }>((resolve, reject) => {
      fetch(apiPath(`/initialgen/${uuid}`), {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Accept": "text/event-stream"
        },
        body: JSON.stringify({
          config: config,
          docConfig: docConfig,
          timestamp: new Date().toISOString(),
          language: language
        }),
      }).then(async (res) => {
        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          reject(new Error(`Backend /initialgen failed: ${res.status} ${txt}`));
          return;
        }

        if (!res.body) {
          reject(new Error("No response body"));
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let accumulatedMarkdown = "";
        let isSaved = false;

        const processChunk = async () => {
          try {
            const { done, value } = await reader.read();
            
            if (done) {
              // Stream ended - now generate the Word and PDF documents
              console.log("Stream completed, generating documents...");
              
              try {
                // Generate Word and PDF documents using the /download endpoint
                const docRes = await fetch(apiPath(`/download/${uuid}`), {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    docConfig: docConfig,
                    language: language
                  }),
                });

                if (!docRes.ok) {
                  console.error("Failed to generate documents");
                  resolve({ 
                    docxShareUrl: null, 
                    proposalContent: accumulatedMarkdown 
                  });
                  return;
                }

                const docResult = await docRes.json();
                resolve({ 
                  docxShareUrl: docResult.proposal_word_url || null, 
                  proposalContent: accumulatedMarkdown 
                });
                setIsUploading(false);
              } catch (error) {
                console.error("Error generating documents:", error);
                resolve({ 
                  docxShareUrl: null, 
                  proposalContent: accumulatedMarkdown 
                });
              }
              return;
            }

            buffer += decoder.decode(value, { stream: true });
            
            // Split by double newlines to separate SSE events
            const events = buffer.split('\n\n');
            // Keep the last incomplete event in the buffer
            buffer = events.pop() || "";

            for (const eventBlock of events) {
              if (!eventBlock.trim()) continue;
              
              const lines = eventBlock.split('\n');
              let eventType = '';
              let dataLines: string[] = [];
              
              for (const line of lines) {
                if (line.startsWith('event:')) {
                  eventType = line.substring(6).trim();
                } else if (line.startsWith('data:')) {
                  // Don't trim data content - preserve whitespace in markdown
                  const dataContent = line.substring(5);
                  // Only remove the single leading space that SSE spec adds after 'data:'
                  dataLines.push(dataContent.startsWith(' ') ? dataContent.substring(1) : dataContent);
                }
              }
              
              if (!eventType || dataLines.length === 0) continue;
              
              // Join multi-line data with newlines to preserve markdown formatting
              const data = dataLines.join('\n');
              
              if (eventType === 'chunk') {
                // Chunk data is JSON-encoded to preserve newlines and special chars
                try {
                  const decodedChunk = JSON.parse(data);
                  accumulatedMarkdown += decodedChunk;
                  console.log(`Chunk received: ${decodedChunk.length} chars, Total: ${accumulatedMarkdown.length}`);
                  setMarkdownContent(accumulatedMarkdown);
                } catch (e) {
                  console.error("Failed to parse chunk data:", e, data);
                  // Fallback: use data as-is
                  accumulatedMarkdown += data;
                  setMarkdownContent(accumulatedMarkdown);
                }
              } else if (eventType === 'stage') {
                try {
                  const stageData = JSON.parse(data);
                  console.log("Stage:", stageData.stage);
                  const stageMessages: Record<string, string> = {
                    'starting': 'Starting...',
                    'downloading_and_uploading_pdfs': 'Uploading PDFs to AI...',
                    'prompting_model': 'Generating proposal...',
                    'saving_generated_text': 'Saving content...'
                  };
                  setProcessingStage(stageMessages[stageData.stage] || stageData.stage || 'Processing...');
                } catch (e) {
                  console.warn("Failed to parse stage data:", data);
                }
              } else if (eventType === 'done') {
                try {
                  const doneData = JSON.parse(data);
                  console.log("Done:", doneData);
                  isSaved = doneData.status === "saved";
                } catch (e) {
                  console.warn("Failed to parse done data:", data);
                }
              } else if (eventType === 'error') {
                try {
                  const errorData = JSON.parse(data);
                  console.error("Stream error:", errorData.message);
                  reject(new Error(errorData.message));
                  return;
                } catch (e) {
                  console.error("Stream error:", data);
                  reject(new Error(data));
                  return;
                }
              }
            }

            processChunk();
          } catch (error) {
            reject(error);
          }
        };

        processChunk();
      }).catch(reject);
    });
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

      await persistGenerationRecord({
        uuid,
        genId,
        rfpFiles: storedRfpFiles,
        supportingFiles: storedSupportingFiles,
        generalPreference: config,
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
      await refreshHistory();
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

      await persistGenerationRecord({
        uuid: jobUuid,
        genId: newGenId,
        rfpFiles: savedRfpFiles,
        supportingFiles: savedSupportingFiles,
        generalPreference: regenConfig,
      });

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
      await refreshHistory();
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

      let regenResult: any = null;
      try {
        regenResult = await response.json();
      } catch (parseError) {
        console.warn("Failed to parse regenerate response JSON", parseError);
      }

      const regenGenId: string = regenResult?.regen_gen_id || regenResult?.gen_id || generateUUID();
      const newWordLink: string | null = regenResult?.wordLink ?? null;
      const newPdfLink: string | null = regenResult?.pdfLink ?? null;

      setProcessingStage('Fetching regenerated content...');

      let regeneratedMarkdown: string | null = null;
      try {
        const { data: regenRow, error: regenRowError } = await supabase
          .from("word_gen")
          .select("*")
          .eq("uuid", jobUuid)
          .eq("gen_id", regenGenId)
          .maybeSingle();

        if (regenRowError) {
          console.warn("Failed to fetch regenerated row from Supabase", regenRowError);
        } else if (regenRow) {
          const typedRow = regenRow as WordGenRow | null;
          regeneratedMarkdown = typedRow?.generated_markdown ?? null;
        }
      } catch (fetchError) {
        console.warn("Error retrieving regenerated markdown from Supabase", fetchError);
      }

      await persistGenerationRecord({
        uuid: jobUuid,
        genId: regenGenId,
        regenComments: commentsSnapshot,
        generalPreference: regenConfig,
        rfpFiles: savedRfpFiles,
        supportingFiles: savedSupportingFiles,
      });

      const proposalSnapshot: StoredProposalSnapshot = {
        config: regenConfig,
        language: regenLanguage,
        docConfig: regenDocConfig,
        wordLink: newWordLink,
        pdfLink: newPdfLink,
        generatedDocument: 'Regenerated_Proposal.docx',
      };

      setProcessingStage('Finalizing regenerated proposal...');
      setUploadProgress(100);
      setSelectedGenId(regenGenId);
      setGeneratedDocument(proposalSnapshot.generatedDocument ?? 'Regenerated_Proposal.docx');
      setWordLink(proposalSnapshot.wordLink ?? null);
      versionLanguageRef.current[regenGenId] = regenLanguage;
      setCurrentVersionLanguage(regenLanguage);
      setPdfLinkSafely(proposalSnapshot.pdfLink ?? null);
      setPdfError(null);
      setIsPdfConverting(false);
      setMarkdownContent(regeneratedMarkdown);
      setIsRegenerationComplete(true);
      setIsRegenerating(false);
      pendingRegenCommentsRef.current = [];
      await refreshHistory();
    } catch (error) {
      console.error('Regenerate failed:', error);
      alert('Regenerate failed. Please try again.');
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
    fileType 
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
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(file.url, "_blank");
                      }}
                      className="text-blue-500 hover:text-blue-600 text-xs font-medium"
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

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    checkSupabaseConnection();
  }, [checkSupabaseConnection]);
 

  // Auto-scroll to bottom when markdown content updates during streaming
  React.useEffect(() => {
    if (isUploading && markdownContent && markdownContainerRef.current) {
      const container = markdownContainerRef.current;
      // Smooth scroll to bottom to show latest content
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [markdownContent, isUploading]);
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

      <div className="min-h-screen bg-gray-50" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
        <div
          className={`fixed inset-0 z-40 flex transition-all duration-300 ${
            isHistoryOpen ? '' : 'pointer-events-none'
          }`}
        >
          <aside
            className={`w-80 max-w-full bg-white border-r border-gray-200 shadow-2xl flex flex-col overflow-hidden transform transition-transform duration-300 ease-in-out ${
              isHistoryOpen ? 'translate-x-0 pointer-events-auto' : '-translate-x-full pointer-events-none'
            }`}
            role={isHistoryOpen ? 'dialog' : undefined}
            aria-modal={isHistoryOpen || undefined}
            aria-hidden={!isHistoryOpen}
            aria-label="Version history"
          >
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-800">
                <Database size={16} />
                Version History
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

            <div className="px-5 py-3 border-b border-gray-100 text-[11px] text-gray-500">
              {historyError
                ? historyError
                : sortedUseCases.length === 0
                  ? 'No versions found yet. Generate a proposal to start tracking history.'
                  : 'Select a use case to view and load any saved generation or regeneration.'}
            </div>

            <div className="flex-1 overflow-y-auto">
              {historyLoading && sortedUseCases.length === 0 ? (
                <div className="flex items-center justify-center h-full text-xs text-gray-500 gap-2">
                  <Loader className="animate-spin" size={14} />
                  Loading history...
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
                        className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                      >
                        <div className="pr-4">
                          <p className="text-sm font-medium text-gray-800 truncate flex items-center gap-2">
                            <span className="truncate" title={useCase.label}>{displayUseCaseLabel}</span>
                            {useCase.isArchived && (
                              <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-semibold text-orange-600 bg-orange-100 rounded">
                                Archived
                              </span>
                            )}
                          </p>
                          <p className="text-[11px] text-gray-500">
                            Latest version V{useCase.latestVersion} • {useCase.items.length} total
                          </p>
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
                                <div className="flex items-stretch">
                                  <button
                                    type="button"
                                    onClick={() => handleSelectHistoryItem(item)}
                                    className={`flex-1 px-4 py-3 text-left text-xs transition-colors rounded-l ${
                                      isActive
                                        ? 'bg-white text-blue-600 border-l-2 border-blue-500 font-semibold shadow-sm'
                                        : 'bg-transparent hover:bg-white text-gray-700'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="truncate flex items-center gap-2">
                                        <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                                          V{versionNumber}
                                        </span>
                                        <span className="truncate" title={label || `Generation ${versionNumber}`}>{displayVersionLabel}</span>
                                        {item.delete_at && (
                                          <span className="inline-flex items-center px-2 py-0.5 text-[9px] font-semibold text-orange-600 bg-orange-100 rounded">
                                            Archived
                                          </span>
                                        )}
                                      </span>
                                      <span className="flex-shrink-0 text-[10px] text-gray-400">
                                        {new Date(item.created_at).toLocaleString()}
                                      </span>
                                    </div>
                                    {shortGenId && (
                                      <p className="mt-1 text-[9px] text-gray-400">ID: {shortGenId}</p>
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
                                    className="px-3 py-3 text-gray-500 border-l border-gray-200 bg-white hover:text-gray-700 rounded-tr rounded-br"
                                    aria-label={versionExpanded ? "Hide version details" : "Show version details"}
                                  >
                                    {versionExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
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

        <div className="flex">
          {/* Left Panel - Upload Form */}
          <div className="w-96 bg-white border-r border-gray-200 min-h-screen p-6">
            <div className="mb-8 flex gap-3">
              <button
                type="button"
                onClick={() => setIsHistoryOpen(prev => !prev)}
                className={`flex-shrink-0 flex items-center justify-center h-10 w-10 rounded-md border transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed ${
                  isHistoryOpen
                    ? 'bg-gray-900 text-white border-gray-900 shadow'
                    : 'bg-white text-gray-700 border-gray-200 hover:shadow'
                }`}
                disabled={supabaseEnvMissing || (historyLoading && sortedUseCases.length === 0)}
                aria-label={
                  supabaseEnvMissing
                    ? 'Supabase configuration required'
                    : historyLoading && sortedUseCases.length === 0
                      ? 'Loading version history'
                      : isHistoryOpen
                        ? 'Close version history'
                        : 'Open version history'
                }
                title={
                  supabaseEnvMissing
                    ? 'Configure Supabase to enable version history'
                    : historyLoading && sortedUseCases.length === 0
                      ? 'Loading version history...'
                      : isHistoryOpen
                        ? 'Close version history'
                        : 'Open version history'
                }
                aria-pressed={isHistoryOpen}
                aria-expanded={isHistoryOpen}
              >
                <Menu size={18} />
              </button>
              <div className="flex-1">
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
                    <p className="flex items-center gap-2">
                      <CheckCircle2 className="text-green-500" size={14} />
                      <span className="text-gray-700">Active use case:</span>
                      <span className="text-gray-900 font-medium truncate" title={activeUseCaseLabel}>
                        {formatNameForSidebar(activeUseCaseLabel, 48)}
                      </span>
                    </p>
                    {activeVersionLabel && (
                      <p className="flex items-center gap-2">
                        <ChevronRight size={12} className="text-gray-400" />
                        <span className="text-gray-700">Current version:</span>
                        <span className="text-gray-900 font-medium truncate" title={activeVersionLabel}>
                          {formatNameForSidebar(activeVersionLabel, 52)}
                        </span>
                      </p>
                    )}
                  </div>
                )}
              </div>
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
                storedFiles={savedRfpFiles}
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
                storedFiles={savedSupportingFiles}
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
                    disabled={supabaseEnvMissing || isUploading || rfpFiles.length === 0 || !config.trim()}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded text-sm font-medium transition-all duration-200
                      ${supabaseEnvMissing || isUploading || rfpFiles.length === 0 || !config.trim()
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
                    disabled={supabaseEnvMissing || isUploading}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded text-sm font-medium transition-all duration-200
                      ${supabaseEnvMissing || isUploading
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
          <div className="flex-1 p-6 min-w-0">
            {isUploading && !markdownContent ? (
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
              />
            )}
          </div>
          

          {/* Right Panel - Document Configuration */}
          <div className="w-96 p-6 border-l border-gray-200 bg-white">
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
