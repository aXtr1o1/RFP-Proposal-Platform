import { NextResponse } from "next/server";
import axios from "axios";
import qs from "qs";

const tenantId = process.env.AZURE_TENANT_ID!;
const clientId = process.env.AZURE_CLIENT_ID!;
const clientSecret = process.env.AZURE_CLIENT_SECRET!;
const oneDriveUserId = process.env.AZURE_ONEDRIVE_USER_ID!; // UPN or GUID

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

export async function GET() {
  try {
    // 1) token
    const token = await getAccessToken();

    // 2) verify user exists (gives better 404 errors than /drive)
    try {
      await axios.get(
        `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(oneDriveUserId)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch (e: any) {
      const s = e?.response?.status;
      const d = e?.response?.data;
      if (s === 404) {
        return NextResponse.json(
          { connected: false, reason: "user_not_found", detail: d },
          { status: 404 }
        );
      }
      if (s === 403) {
        return NextResponse.json(
          { connected: false, reason: "permission_denied_user_lookup", detail: d },
          { status: 403 }
        );
      }
      throw e;
    }

    // 3) fetch drive
    const driveRes = await axios.get(
      `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(oneDriveUserId)}/drive`,
      { headers: { Authorization: `Bearer ${token}` } }
    );

    return NextResponse.json({ connected: true, drive: driveRes.data });
  } catch (err: any) {
    const s = err?.response?.status;
    const d = err?.response?.data;
    let reason: string = "unknown";

    if (s === 401) reason = "invalid_token_or_scope";
    else if (s === 403) reason = "permission_denied_drive";
    else if (s === 404) reason = "drive_not_found";
    else if (s === 400) reason = "bad_request";

    console.error("check-onedrive error", reason, d || err.message);
    return NextResponse.json(
      { connected: false, message: "Failed to connect", reason, detail: d || err.message },
      { status: s || 500 }
    );
  }
}
