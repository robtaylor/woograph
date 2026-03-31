/**
 * WooGraph Upload Worker
 *
 * Handles file uploads to Cloudflare R2 for the WooGraph submission flow.
 *
 * Endpoints:
 *   POST /upload   - Upload a file directly (multipart/form-data)
 *   GET  /file/:key - Retrieve an uploaded file
 *
 * Files are stored with a UUID prefix to avoid collisions.
 */

export interface Env {
	BUCKET: R2Bucket;
	ALLOWED_ORIGINS: string;
	MAX_FILE_SIZE: string;
}

function corsHeaders(origin: string, env: Env): Record<string, string> {
	const allowed = env.ALLOWED_ORIGINS.split(",").map((s) => s.trim());
	// Also allow localhost for development
	const isAllowed =
		allowed.includes(origin) || origin.startsWith("http://localhost");

	return {
		"Access-Control-Allow-Origin": isAllowed ? origin : "",
		"Access-Control-Allow-Methods": "GET, POST, OPTIONS",
		"Access-Control-Allow-Headers": "Content-Type",
		"Access-Control-Max-Age": "3600",
	};
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);
		const origin = request.headers.get("Origin") || "";
		const headers = corsHeaders(origin, env);

		// Handle CORS preflight
		if (request.method === "OPTIONS") {
			return new Response(null, { status: 204, headers });
		}

		// POST /upload - upload a file
		if (request.method === "POST" && url.pathname === "/upload") {
			return handleUpload(request, env, headers);
		}

		// GET /file/:key - retrieve a file
		if (request.method === "GET" && url.pathname.startsWith("/file/")) {
			return handleGet(url.pathname.slice(6), env, headers);
		}

		return new Response("Not found", { status: 404, headers });
	},
};

async function handleUpload(
	request: Request,
	env: Env,
	headers: Record<string, string>,
): Promise<Response> {
	const maxSize = parseInt(env.MAX_FILE_SIZE || "104857600");

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
		// Raw binary upload with filename in query param
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

	// Generate a unique key: uuid/original-filename
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
		{
			status: 200,
			headers: { ...headers, "Content-Type": "application/json" },
		},
	);
}

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
			"Content-Type":
				object.httpMetadata?.contentType || "application/octet-stream",
			"Content-Disposition": `inline; filename="${key.split("/").pop()}"`,
			"Cache-Control": "public, max-age=31536000, immutable",
		},
	});
}
