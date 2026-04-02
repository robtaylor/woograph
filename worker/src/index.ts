/**
 * WooGraph Upload Worker
 *
 * Endpoints:
 *   POST /upload              - Upload a file to R2
 *   POST /submit              - Create a GitHub issue (uses session token if logged in)
 *   GET  /file/:key           - Retrieve an uploaded file
 *   GET  /auth/login          - Redirect to GitHub OAuth
 *   GET  /auth/callback       - Handle OAuth callback, set session cookie
 *   GET  /auth/me             - Return current session user info
 *   POST /auth/logout         - Clear session cookie
 */

export interface Env {
	BUCKET: R2Bucket;
	SESSIONS: KVNamespace;
	GITHUB_TOKEN: string;           // Bot/fallback PAT
	GITHUB_CLIENT_ID: string;       // OAuth App client ID
	GITHUB_CLIENT_SECRET: string;   // OAuth App client secret
	ALLOWED_ORIGINS: string;
	MAX_FILE_SIZE: string;
}

const GITHUB_REPO = "robtaylor/woograph";
const SESSION_TTL_SECONDS = 60 * 60 * 24 * 30; // 30 days
const OAUTH_STATE_TTL_SECONDS = 60 * 10;        // 10 minutes

interface Session {
	login: string;
	name: string;
	avatar_url: string;
	token: string;
}

// ── CORS ─────────────────────────────────────────────────────────────────────

function corsHeaders(
	origin: string,
	env: Env,
	withCredentials = false,
): Record<string, string> {
	const allowed = env.ALLOWED_ORIGINS.split(",").map((s) => s.trim());
	const isAllowed =
		allowed.includes(origin) || origin.startsWith("http://localhost");

	const headers: Record<string, string> = {
		"Access-Control-Allow-Origin": isAllowed ? origin : "",
		"Access-Control-Allow-Methods": "GET, POST, OPTIONS",
		"Access-Control-Allow-Headers": "Content-Type",
		"Access-Control-Max-Age": "3600",
	};
	if (withCredentials && isAllowed) {
		headers["Access-Control-Allow-Credentials"] = "true";
	}
	return headers;
}

// ── Cookie helpers ────────────────────────────────────────────────────────────

function parseCookies(request: Request): Record<string, string> {
	const header = request.headers.get("Cookie") || "";
	const cookies: Record<string, string> = {};
	for (const part of header.split(";")) {
		const [k, ...v] = part.trim().split("=");
		if (k) cookies[k.trim()] = decodeURIComponent(v.join("="));
	}
	return cookies;
}

function sessionCookie(sessionId: string, maxAge: number): string {
	return `wg_session=${sessionId}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${maxAge}`;
}

// ── Session helpers ───────────────────────────────────────────────────────────

async function getSession(
	request: Request,
	env: Env,
): Promise<Session | null> {
	const cookies = parseCookies(request);
	const sessionId = cookies["wg_session"];
	if (!sessionId) return null;
	const raw = await env.SESSIONS.get(`session:${sessionId}`);
	if (!raw) return null;
	try {
		return JSON.parse(raw) as Session;
	} catch {
		return null;
	}
}

// ── Router ────────────────────────────────────────────────────────────────────

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);
		const origin = request.headers.get("Origin") || "";
		const headers = corsHeaders(origin, env);
		const credHeaders = corsHeaders(origin, env, true);

		if (request.method === "OPTIONS") {
			return new Response(null, { status: 204, headers: credHeaders });
		}

		if (request.method === "POST" && url.pathname === "/upload") {
			return handleUpload(request, env, headers);
		}

		if (request.method === "POST" && url.pathname === "/submit") {
			return handleSubmit(request, env, credHeaders);
		}

		if (request.method === "GET" && url.pathname.startsWith("/file/")) {
			return handleGet(url.pathname.slice(6), env, headers);
		}

		if (request.method === "GET" && url.pathname === "/auth/login") {
			return handleAuthLogin(request, env, url);
		}

		if (request.method === "GET" && url.pathname === "/auth/callback") {
			return handleAuthCallback(request, env, url);
		}

		if (request.method === "GET" && url.pathname === "/auth/me") {
			return handleAuthMe(request, env, credHeaders);
		}

		if (request.method === "POST" && url.pathname === "/auth/logout") {
			return handleAuthLogout(request, env, credHeaders);
		}

		return new Response("Not found", { status: 404, headers });
	},
};

// ── Auth: login ───────────────────────────────────────────────────────────────

async function handleAuthLogin(
	request: Request,
	env: Env,
	url: URL,
): Promise<Response> {
	const returnTo = url.searchParams.get("return_to") || "";
	const state = crypto.randomUUID();

	// Store state + return URL in KV for CSRF verification
	await env.SESSIONS.put(
		`oauth_state:${state}`,
		JSON.stringify({ return_to: returnTo }),
		{ expirationTtl: OAUTH_STATE_TTL_SECONDS },
	);

	const workerOrigin = `${url.protocol}//${url.host}`;
	const params = new URLSearchParams({
		client_id: env.GITHUB_CLIENT_ID,
		redirect_uri: `${workerOrigin}/auth/callback`,
		scope: "public_repo",
		state,
	});

	return Response.redirect(
		`https://github.com/login/oauth/authorize?${params}`,
		302,
	);
}

// ── Auth: callback ────────────────────────────────────────────────────────────

async function handleAuthCallback(
	request: Request,
	env: Env,
	url: URL,
): Promise<Response> {
	const code = url.searchParams.get("code");
	const state = url.searchParams.get("state");

	if (!code || !state) {
		return new Response("Missing code or state", { status: 400 });
	}

	// Verify CSRF state
	const stateData = await env.SESSIONS.get(`oauth_state:${state}`);
	if (!stateData) {
		return new Response("Invalid or expired state", { status: 400 });
	}
	await env.SESSIONS.delete(`oauth_state:${state}`);

	const { return_to } = JSON.parse(stateData) as { return_to: string };

	// Exchange code for access token
	const tokenResp = await fetch(
		"https://github.com/login/oauth/access_token",
		{
			method: "POST",
			headers: {
				Accept: "application/json",
				"Content-Type": "application/json",
				"User-Agent": "woograph-upload-worker",
			},
			body: JSON.stringify({
				client_id: env.GITHUB_CLIENT_ID,
				client_secret: env.GITHUB_CLIENT_SECRET,
				code,
			}),
		},
	);

	if (!tokenResp.ok) {
		return new Response("Failed to exchange OAuth code", { status: 502 });
	}

	const tokenData = (await tokenResp.json()) as {
		access_token?: string;
		error?: string;
	};

	if (!tokenData.access_token) {
		return new Response(`OAuth error: ${tokenData.error || "no token"}`, {
			status: 400,
		});
	}

	// Fetch user info
	const userResp = await fetch("https://api.github.com/user", {
		headers: {
			Authorization: `Bearer ${tokenData.access_token}`,
			Accept: "application/vnd.github+json",
			"User-Agent": "woograph-upload-worker",
		},
	});

	if (!userResp.ok) {
		return new Response("Failed to fetch GitHub user", { status: 502 });
	}

	const user = (await userResp.json()) as {
		login: string;
		name: string;
		avatar_url: string;
	};

	// Store session in KV
	const sessionId = crypto.randomUUID();
	const session: Session = {
		login: user.login,
		name: user.name || user.login,
		avatar_url: user.avatar_url,
		token: tokenData.access_token,
	};
	await env.SESSIONS.put(`session:${sessionId}`, JSON.stringify(session), {
		expirationTtl: SESSION_TTL_SECONDS,
	});

	// Redirect back to the submit page
	const redirectTo = return_to || "https://robtaylor.github.io/woograph/submit.html";
	return new Response(null, {
		status: 302,
		headers: {
			Location: redirectTo,
			"Set-Cookie": sessionCookie(sessionId, SESSION_TTL_SECONDS),
		},
	});
}

// ── Auth: me ──────────────────────────────────────────────────────────────────

async function handleAuthMe(
	request: Request,
	env: Env,
	headers: Record<string, string>,
): Promise<Response> {
	const session = await getSession(request, env);
	if (!session) {
		return new Response(JSON.stringify({ user: null }), {
			status: 200,
			headers: { ...headers, "Content-Type": "application/json" },
		});
	}
	return new Response(
		JSON.stringify({
			user: {
				login: session.login,
				name: session.name,
				avatar_url: session.avatar_url,
			},
		}),
		{ status: 200, headers: { ...headers, "Content-Type": "application/json" } },
	);
}

// ── Auth: logout ──────────────────────────────────────────────────────────────

async function handleAuthLogout(
	request: Request,
	env: Env,
	headers: Record<string, string>,
): Promise<Response> {
	const cookies = parseCookies(request);
	const sessionId = cookies["wg_session"];
	if (sessionId) {
		await env.SESSIONS.delete(`session:${sessionId}`);
	}
	return new Response(JSON.stringify({ ok: true }), {
		status: 200,
		headers: {
			...headers,
			"Content-Type": "application/json",
			"Set-Cookie": sessionCookie("", 0), // expire cookie
		},
	});
}

// ── Upload ────────────────────────────────────────────────────────────────────

async function handleUpload(
	request: Request,
	env: Env,
	headers: Record<string, string>,
): Promise<Response> {
	const maxSize = parseInt(env.MAX_FILE_SIZE || "104857600");
	const url = new URL(request.url);
	const contentType = request.headers.get("Content-Type") || "";

	let file: ArrayBuffer;
	let filename: string;
	let mimeType: string;

	if (contentType.includes("multipart/form-data")) {
		const formData = await request.formData();
		const uploaded = formData.get("file");
		if (!uploaded || !(uploaded instanceof File)) {
			return new Response(
				JSON.stringify({ error: "No file provided" }),
				{ status: 400, headers: { ...headers, "Content-Type": "application/json" } },
			);
		}
		if (uploaded.size > maxSize) {
			return new Response(
				JSON.stringify({ error: `File too large (max ${maxSize / 1048576}MB)` }),
				{ status: 413, headers: { ...headers, "Content-Type": "application/json" } },
			);
		}
		file = await uploaded.arrayBuffer();
		filename = uploaded.name;
		mimeType = uploaded.type || "application/octet-stream";
	} else {
		const body = await request.arrayBuffer();
		if (body.byteLength > maxSize) {
			return new Response(
				JSON.stringify({ error: `File too large (max ${maxSize / 1048576}MB)` }),
				{ status: 413, headers: { ...headers, "Content-Type": "application/json" } },
			);
		}
		file = body;
		filename = url.searchParams.get("filename") || "upload";
		mimeType = contentType || "application/octet-stream";
	}

	const uuid = crypto.randomUUID();
	const key = `uploads/${uuid}/${filename}`;

	await env.BUCKET.put(key, file, {
		httpMetadata: { contentType: mimeType },
		customMetadata: {
			originalName: filename,
			uploadedAt: new Date().toISOString(),
		},
	});

	const fileUrl = `${new URL(request.url).origin}/file/${key}`;

	return new Response(
		JSON.stringify({ key, url: fileUrl, filename, size: file.byteLength }),
		{ status: 200, headers: { ...headers, "Content-Type": "application/json" } },
	);
}

// ── File get ──────────────────────────────────────────────────────────────────

async function handleGet(
	key: string,
	env: Env,
	headers: Record<string, string>,
): Promise<Response> {
	const object = await env.BUCKET.get(key);
	if (!object) {
		return new Response("Not found", { status: 404, headers });
	}
	return new Response(object.body, {
		headers: {
			...headers,
			"Content-Type": object.httpMetadata?.contentType || "application/octet-stream",
			"Content-Disposition": `inline; filename="${key.split("/").pop()}"`,
			"Cache-Control": "public, max-age=31536000, immutable",
		},
	});
}

// ── Submit ────────────────────────────────────────────────────────────────────

interface SubmitPayload {
	title: string;
	type: string;
	url?: string;
	tags?: string;
	description?: string;
	account_text?: string;
	latitude?: number;
	longitude?: number;
	email?: string;
}

async function handleSubmit(
	request: Request,
	env: Env,
	headers: Record<string, string>,
): Promise<Response> {
	const jsonHeaders = { ...headers, "Content-Type": "application/json" };

	let payload: SubmitPayload;
	try {
		payload = (await request.json()) as SubmitPayload;
	} catch {
		return new Response(
			JSON.stringify({ error: "Invalid JSON" }),
			{ status: 400, headers: jsonHeaders },
		);
	}

	if (!payload.title || !payload.type) {
		return new Response(
			JSON.stringify({ error: "Title and type are required" }),
			{ status: 400, headers: jsonHeaders },
		);
	}

	// Use session token if logged in, otherwise fall back to bot token
	const session = await getSession(request, env);
	const githubToken = session?.token ?? env.GITHUB_TOKEN;

	// Build issue body
	const lines: string[] = [];
	lines.push("### Source Type\n");
	lines.push(payload.type);
	lines.push("\n### URL\n");
	lines.push(payload.url || "_No response_");
	lines.push("\n### Tags\n");
	lines.push(payload.tags || "_No response_");
	lines.push("\n### Description\n");
	lines.push(payload.description || "_No response_");
	lines.push("\n### Account Text\n");
	lines.push(payload.account_text || "_No response_");
	if (payload.latitude != null && payload.longitude != null) {
		lines.push("\n### Location\n");
		lines.push(`${payload.latitude}, ${payload.longitude}`);
	}
	if (payload.email) {
		lines.push("\n### Contact Email\n");
		lines.push(payload.email);
	}

	const issueBody = lines.join("\n");
	const issueTitle = `[Source] ${payload.title}`;

	const ghResponse = await fetch(
		`https://api.github.com/repos/${GITHUB_REPO}/issues`,
		{
			method: "POST",
			headers: {
				Authorization: `Bearer ${githubToken}`,
				Accept: "application/vnd.github+json",
				"Content-Type": "application/json",
				"User-Agent": "woograph-upload-worker",
			},
			body: JSON.stringify({
				title: issueTitle,
				body: issueBody,
				labels: ["submission"],
			}),
		},
	);

	if (!ghResponse.ok) {
		const err = await ghResponse.text();
		return new Response(
			JSON.stringify({ error: "Failed to create issue", details: err }),
			{ status: 502, headers: jsonHeaders },
		);
	}

	const issue = (await ghResponse.json()) as {
		number: number;
		html_url: string;
	};

	return new Response(
		JSON.stringify({
			issue_number: issue.number,
			issue_url: issue.html_url,
			submitted_as: session?.login ?? null,
		}),
		{ status: 201, headers: jsonHeaders },
	);
}
