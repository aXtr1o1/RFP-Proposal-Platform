export const runtime = "nodejs";

import { NextResponse } from "next/server";
import axios from "axios";
import qs from "qs";

const tenantId = process.env.AZURE_TENANT_ID!;
const clientId = process.env.AZURE_CLIENT_ID!;
const clientSecret = process.env.AZURE_CLIENT_SECRET!;
const oneDriveUserId = process.env.AZURE_ONEDRIVE_USER_ID!; // UPN or GUID

const GRAPH = "https://graph.microsoft.com/v1.0";
const SMALL_UPLOAD_LIMIT = 4 * 1024 * 1024; // 4MB

function cleanSeg(s: string) {
  return (s || "").replace(/^\/+|\/+$/g, "");
}
function pathJoin(...segs: string[]) {
  return segs.map((s) => encodeURIComponent(cleanSeg(s))).join("/");
}

async function getAccessToken() {
  const url = `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`;
  const data = {
    client_id: clientId,
    scope: "https://graph.microsoft.com/.default",
    client_secret: clientSecret,
    grant_type: "client_credentials",
  };
  const res = await axios.post(url, qs.stringify(data), {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return res.data.access_token as string;
}

function graphClient(token: string) {
  return axios.create({
    baseURL: GRAPH,
    headers: { Authorization: `Bearer ${token}` },
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
  });
}

async function getItemByPath(client: any, segments: string[]) {
  const url = `/users/${encodeURIComponent(oneDriveUserId)}/drive/root:/${pathJoin(...segments)}`;
  return client.get(url);
}

async function createChildFolder(client: any, parentSegments: string[], name: string) {
  const body = { name, folder: {}, "@microsoft.graph.conflictBehavior": "rename" };
  if (parentSegments.length === 0) {
    // create under root
    const url = `/users/${encodeURIComponent(oneDriveUserId)}/drive/root/children`;
    return client.post(url, body);
  } else {
    const url = `/users/${encodeURIComponent(oneDriveUserId)}/drive/root:/${pathJoin(
      ...parentSegments
    )}:/children`;
    return client.post(url, body);
  }
}

/** Ensure a nested folder path exists; returns final driveItem */
async function ensurePath(client: any, segments: string[]) {
  const acc: string[] = [];
  for (const seg of segments) {
    const current = [...acc, seg];
    try {
      await getItemByPath(client, current);
    } catch (e: any) {
      if (e?.response?.status === 404) {
        await createChildFolder(client, acc, seg);
      } else {
        throw e;
      }
    }
    acc.push(seg);
  }
  const res = await getItemByPath(client, segments);
  return res.data;
}

async function simpleUpload(
  client: any,
  folderSegments: string[],
  fileName: string,
  buffer: Buffer,
  contentType?: string
) {
  const url = `/users/${encodeURIComponent(oneDriveUserId)}/drive/root:/${pathJoin(
    ...folderSegments,
    fileName
  )}:/content`;
  const res = await client.put(url, buffer, {
    headers: {
      "Content-Type": contentType || "application/octet-stream",
      "Content-Length": buffer.length,
    },
  });
  return res.data; // driveItem
}

async function largeUpload(
  client: any,
  folderSegments: string[],
  fileName: string,
  buffer: Buffer,
  contentType?: string
) {
  // 1) Create session
  const sessionUrl = `/users/${encodeURIComponent(oneDriveUserId)}/drive/root:/${pathJoin(
    ...folderSegments,
    fileName
  )}:/createUploadSession`;
  const sessionRes = await client.post(sessionUrl, {
    item: { "@microsoft.graph.conflictBehavior": "replace" },
  });
  const uploadUrl: string = sessionRes.data.uploadUrl;

  // 2) Chunked PUTs
  const chunkSize = 8 * 1024 * 1024; // 8MB
  const total = buffer.length;
  let start = 0;

  while (start < total) {
    const end = Math.min(start + chunkSize, total);
    const chunk = buffer.subarray(start, end);
    const contentRange = `bytes ${start}-${end - 1}/${total}`;

    await axios.put(uploadUrl, chunk, {
      headers: {
        "Content-Length": String(chunk.length),
        "Content-Range": contentRange,
        "Content-Type": contentType || "application/octet-stream",
      },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      validateStatus: (s) => (s >= 200 && s < 300) || s === 308, // 308 for intermediate chunk
    });

    start = end;
  }

  // 3) Return metadata
  const final = await getItemByPath(client, [...folderSegments, fileName]);
  return final.data;
}

export async function POST(req: Request) {
  try {
    const form = await req.formData();

    const uuid = (form.get("uuid") as string) || "";
    const config = (form.get("config") as string) || "";

    const rfpFiles = form.getAll("rfpFiles") as File[];
    const supportingFiles = form.getAll("supportingFiles") as File[];

    if (!uuid) return NextResponse.json({ error: "uuid required" }, { status: 400 });

    const token = await getAccessToken();
    const client = graphClient(token);

    // Ensure folder structure:
    // RFP-Uploads/{uuid}/RFP
    // RFP-Uploads/{uuid}/supportingFiles
    const base = ["RFP-Uploads"];
    await ensurePath(client, base);

    const uuidPath = [...base, uuid];
    const uuidFolder = await ensurePath(client, uuidPath);

    const rfpPath = [...uuidPath, "RFP"];
    const supPath = [...uuidPath, "supportingFiles"];
    const rfpFolder = await ensurePath(client, rfpPath);
    const supFolder = await ensurePath(client, supPath);

    const uploadOne = async (folderSegs: string[], f: File) => {
      const fileName = f.name;
      const type = f.type || "application/octet-stream";
      const ab = await f.arrayBuffer();
      const buf = Buffer.from(ab);
      if (buf.length <= SMALL_UPLOAD_LIMIT) {
        return simpleUpload(client, folderSegs, fileName, buf, type);
      } else {
        return largeUpload(client, folderSegs, fileName, buf, type);
      }
    };

    const results: {
      baseFolder: { path: string; webUrl?: string; id?: string };
      rfpFolder: { path: string; webUrl?: string; id?: string };
      supportingFolder: { path: string; webUrl?: string; id?: string };
      rfp: any[];
      supporting: any[];
      meta: { uuid: string; config: string };
    } = {
      baseFolder: { path: base.join("/") },
      rfpFolder: { path: rfpPath.join("/") },
      supportingFolder: { path: supPath.join("/") },
      rfp: [],
      supporting: [],
      meta: { uuid, config },
    };

    results.baseFolder = {
      path: uuidPath.join("/"),
      id: uuidFolder.id,
      webUrl: uuidFolder.webUrl,
    };
    results.rfpFolder = {
      path: rfpPath.join("/"),
      id: rfpFolder.id,
      webUrl: rfpFolder.webUrl,
    };
    results.supportingFolder = {
      path: supPath.join("/"),
      id: supFolder.id,
      webUrl: supFolder.webUrl,
    };

    for (const f of rfpFiles) {
      const item = await uploadOne(rfpPath, f);
      results.rfp.push({ id: item.id, name: item.name, size: item.size, webUrl: item.webUrl });
    }
    for (const f of supportingFiles) {
      const item = await uploadOne(supPath, f);
      results.supporting.push({ id: item.id, name: item.name, size: item.size, webUrl: item.webUrl });
    }

    return NextResponse.json(results);
  } catch (err: any) {
    const status = err?.response?.status || 500;
    const detail = err?.response?.data || err?.message || "unknown";
    console.error("upload error", detail);
    return NextResponse.json({ error: "upload_failed", detail }, { status });
  }
}
