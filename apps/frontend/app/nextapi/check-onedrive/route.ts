import { NextResponse } from "next/server";
import axios from "axios";
import qs from "qs";

// Environment variables
const tenantId = process.env.AZURE_TENANT_ID!;
const clientId = process.env.AZURE_CLIENT_ID!;
const clientSecret = process.env.AZURE_CLIENT_SECRET!;
const oneDriveUserId = process.env.AZURE_ONEDRIVE_USER_ID!; // UPN or GUID

/**
 * Fetch a new access token using client credentials flow
 */
async function getAccessToken(): Promise<string> {
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

/**
 * Helper to wrap Graph API requests with token refresh on 401
 */
async function fetchWithTokenRetry<T>(
  fn: (token: string) => Promise<T>,
  maxRetries = 1
): Promise<T> {
  let retries = 0;
  let token = await getAccessToken();

  while (true) {
    try {
      return await fn(token);
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 401 && retries < maxRetries) {
        // Token expired, fetch a new one and retry
        token = await getAccessToken();
        retries++;
      } else {
        throw err;
      }
    }
  }
}

export async function GET() {
  try {
    // 1) Verify the user exists (provides clearer 404 errors)
    await fetchWithTokenRetry(async (token) => {
      await axios.get(
        `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(oneDriveUserId)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    });

    // 2) Fetch the user's drive
    const driveRes = await fetchWithTokenRetry(async (token) => {
      return axios.get(
        `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(oneDriveUserId)}/drive`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    });

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