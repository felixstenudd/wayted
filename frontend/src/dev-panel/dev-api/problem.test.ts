import { describe, expect, it } from 'vitest'

import { ApiFailure, problemOf, toProblem, unwrap } from './problem'

const answer = (status: number, body: unknown) => {
	const response = new Response(null, { status })
	return Promise.resolve(response.ok ? { data: body, response } : { error: body, response })
}

describe('toProblem', () => {
	it('keeps the sentence of a 400', () => {
		expect(toProblem(400, { detail: 'West must not be east of east.' })).toEqual({
			kind: 'refused',
			detail: 'West must not be east of east.',
		})
	})

	it('takes the first message of a 422 list', () => {
		const body = {
			detail: [{ loc: ['body', 'radius_m'], msg: 'Too large', type: 'x' }, { msg: 'b' }],
		}
		expect(toProblem(422, body)).toEqual({ kind: 'rejected', detail: 'Too large' })
	})

	it('treats every other status as an API that is not available', () => {
		expect(toProblem(500, 'Internal Server Error')).toEqual({ kind: 'unavailable' })
		expect(toProblem(502, undefined)).toEqual({ kind: 'unavailable' })
	})

	it('survives a body it does not recognise', () => {
		expect(toProblem(400, null)).toEqual({ kind: 'refused', detail: '' })
		expect(toProblem(422, { detail: [] })).toEqual({ kind: 'rejected', detail: '' })
	})
})

describe('unwrap', () => {
	it('returns the data of a successful answer', async () => {
		await expect(unwrap(answer(200, { status: 'ok' }))).resolves.toEqual({ status: 'ok' })
	})

	it('throws the problem of a failed answer', async () => {
		const failure = await unwrap(answer(400, { detail: 'Zoom in.' })).catch((e: unknown) => e)
		expect(failure).toBeInstanceOf(ApiFailure)
		expect(problemOf(failure)).toEqual({ kind: 'refused', detail: 'Zoom in.' })
	})

	it('reports a request that never got an answer as unavailable', async () => {
		const failure = await unwrap(Promise.reject(new TypeError('Failed to fetch'))).catch(
			(e: unknown) => e,
		)
		expect(problemOf(failure)).toEqual({ kind: 'unavailable' })
	})
})

describe('problemOf', () => {
	it('treats an unknown error as unavailable', () => {
		expect(problemOf(new Error('boom'))).toEqual({ kind: 'unavailable' })
	})
})
