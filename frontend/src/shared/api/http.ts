// The backend is served on the same origin under this prefix; see the proxy in
// vite.config.ts (dev) and nginx.conf (prod).
const API_BASE = '/api'

/** A non-2xx response from the API. `detail` is FastAPI's error message, when it sent one. */
export class ApiError extends Error {
	constructor(
		readonly status: number,
		readonly detail?: string,
	) {
		super(detail ?? `Request failed with status ${status}`)
		this.name = 'ApiError'
	}
}

export function isUnauthorized(error: unknown): boolean {
	return error instanceof ApiError && error.status === 401
}

export interface RequestOptions {
	method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
	/** Sent as JSON. */
	body?: unknown
	/** Access token, sent as a bearer token. */
	token?: string | null
}

/**
 * Calls the backend and returns the parsed JSON body. The API is on the same
 * origin, so the browser attaches its cookies without being asked.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	const response = await send(path, options, 'application/json')
	if (response.status === 204) return undefined as T
	return (await response.json()) as T
}

/** A file the API sent to be saved. */
export interface DownloadedFile {
	blob: Blob
	/** From the Content-Disposition header, when it names one. */
	filename: string | null
}

/** Like `request`, for endpoints that answer with a file rather than JSON. */
export async function requestFile(
	path: string,
	options: RequestOptions = {},
): Promise<DownloadedFile> {
	const response = await send(path, options, '*/*')
	return { blob: await response.blob(), filename: attachmentName(response) }
}

async function send(path: string, options: RequestOptions, accept: string): Promise<Response> {
	const headers: Record<string, string> = { Accept: accept }
	if (options.body !== undefined) headers['Content-Type'] = 'application/json'
	if (options.token) headers.Authorization = `Bearer ${options.token}`

	const response = await fetch(`${API_BASE}${path}`, {
		method: options.method ?? 'GET',
		headers,
		body: options.body === undefined ? null : JSON.stringify(options.body),
	})
	if (!response.ok) throw new ApiError(response.status, await readDetail(response))
	return response
}

// The API names files with plain slugs, so the quoted form is all there is to read.
function attachmentName(response: Response): string | null {
	const header = response.headers.get('Content-Disposition') ?? ''
	return /filename="([^"]+)"/.exec(header)?.[1] ?? null
}

async function readDetail(response: Response): Promise<string | undefined> {
	try {
		const body = (await response.json()) as { detail?: unknown }
		// Validation errors (422) send a list here instead of a message.
		return typeof body.detail === 'string' ? body.detail : undefined
	} catch {
		return undefined
	}
}
