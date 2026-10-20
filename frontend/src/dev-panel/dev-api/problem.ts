export type ApiProblem =
	// 400: the API's own sentence, which says what to do
	| { kind: 'refused'; detail: string }
	// 422: the panel sent something the API does not accept
	| { kind: 'rejected'; detail: string }
	| { kind: 'unavailable' }

export class ApiFailure extends Error {
	constructor(readonly problem: ApiProblem) {
		super(problem.kind)
	}
}

function firstMessage(body: unknown): string {
	if (typeof body !== 'object' || body === null || !('detail' in body)) return ''
	const { detail } = body
	if (typeof detail === 'string') return detail
	if (!Array.isArray(detail)) return ''
	const first: unknown = detail[0]
	if (typeof first !== 'object' || first === null || !('msg' in first)) return ''
	return typeof first.msg === 'string' ? first.msg : ''
}

export function toProblem(status: number, body: unknown): ApiProblem {
	if (status === 400) return { kind: 'refused', detail: firstMessage(body) }
	if (status === 422) return { kind: 'rejected', detail: firstMessage(body) }
	return { kind: 'unavailable' }
}

interface Answer<Data> {
	data?: Data
	error?: unknown
	response: Response
}

/** The data of an answer, or an ApiFailure saying what went wrong. */
export async function unwrap<Data>(request: Promise<Answer<Data>>): Promise<Data> {
	let answer: Answer<Data>
	try {
		answer = await request
	} catch {
		throw new ApiFailure({ kind: 'unavailable' })
	}
	if (answer.response.ok && answer.data !== undefined) return answer.data
	throw new ApiFailure(toProblem(answer.response.status, answer.error))
}

export function problemOf(error: unknown): ApiProblem {
	return error instanceof ApiFailure ? error.problem : { kind: 'unavailable' }
}
