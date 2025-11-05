// app/api/convert/route.ts
import { NextRequest, NextResponse } from "next/server";
import { promises as fs } from "fs";
import os from "os";
import path from "path";
import { execFile } from "child_process";
import { promisify } from "util";

export const runtime = "nodejs"; // Ensures server environment

const runLibreOffice = promisify(execFile);

const buildWindowsLibreOfficePaths = () => {
  if (process.platform !== "win32") {
    return [];
  }

  const baseDirs = [
    process.env.LIBREOFFICE_INSTALL_DIR,
    process.env.PROGRAMFILES,
    process.env["PROGRAMFILES(X86)"],
  ].filter((dir): dir is string => Boolean(dir));

  const resolved: string[] = [];
  for (const base of baseDirs) {
    const normalized = base.trim();
    if (!normalized) continue;
    resolved.push(path.join(normalized, "LibreOffice", "program", "soffice.exe"));
    resolved.push(path.join(normalized, "LibreOffice", "program", "soffice.com"));
  }

  return resolved;
};

const buildLibreOfficeCandidates = () => {
  const direct = (process.env.LIBREOFFICE_PATH || "")
    .split(path.delimiter)
    .map((entry) => entry.trim())
    .filter(Boolean);

  const windowsPaths = buildWindowsLibreOfficePaths();

  const commandNames = process.platform === "win32"
    ? ["soffice.exe", "soffice", "libreoffice.exe", "libreoffice"]
    : ["soffice", "libreoffice"];

  const allCandidates = [...direct, ...windowsPaths, ...commandNames];
  const deduped: string[] = [];
  const seen = new Set<string>();
  for (const candidate of allCandidates) {
    const normalized = candidate.trim();
    if (!normalized) continue;
    const key = normalized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(normalized);
  }

  return deduped;
};

async function convertWithLibreOffice(inputPath: string, outputDir: string) {
  const candidates = buildLibreOfficeCandidates();

  let lastError: unknown = null;
  for (const candidate of candidates) {
    try {
      if (path.isAbsolute(candidate)) {
        await fs.access(candidate);
      }
      await runLibreOffice(candidate, [
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        outputDir,
        inputPath,
      ]);
      lastError = null;
      break;
    } catch (error) {
      lastError = error;
    }
  }

  if (lastError) {
    const reason = lastError instanceof Error ? lastError.message : String(lastError ?? "unknown");
    throw new Error(
      `LibreOffice conversion failed. Ensure LibreOffice is installed and accessible via PATH or set LIBREOFFICE_PATH to the executable. (${reason})`
    );
  }
}

async function cleanupTempDir(dir: string) {
  try {
    await fs.rm(dir, { force: true, recursive: true });
  } catch {
    // Let the OS temp cleaner handle any leftovers
  }
}

export async function POST(req: NextRequest) {
  let tempDir: string | null = null;

  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
    }

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "rfp-convert-"));
    const inputName = path.basename(file.name || "document.docx");
    const inputExtension = path.extname(inputName) || ".docx";
    const sanitizedInputName = inputName.replace(/[\\/:*?"<>|]+/g, "_");
    const hasExtension = sanitizedInputName.toLowerCase().endsWith(inputExtension.toLowerCase());
    const finalInputName = hasExtension ? sanitizedInputName : `${sanitizedInputName}${inputExtension}`;
    const inputPath = path.join(tempDir, finalInputName);
    await fs.writeFile(inputPath, buffer);

    await convertWithLibreOffice(inputPath, tempDir);

    const parsed = path.parse(inputPath);
    const outputFilename = `${parsed.name}.pdf`;
    const outputPath = path.join(tempDir, outputFilename);

    const pdfBuffer = await fs.readFile(outputPath);

    return new NextResponse(pdfBuffer, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${outputFilename}"`,
      },
    });
  } catch (err: any) {
    console.error(err);
    const message =
      err?.message ||
      "Failed to convert document. Please verify LibreOffice is installed and reachable.";
    return NextResponse.json({ error: message }, { status: 500 });
  } finally {
    if (tempDir) {
      await cleanupTempDir(tempDir);
    }
  }
}
