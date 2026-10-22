import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, requestFile } from './http'

afterEach(() => {
	vi.unstubAllGlobals()
})

function stubFetch(response: Response) {
	const fetch = vi.fn<typeof globalThis.fetch>(() => Promise.resolve(response))
	vi.stubGlobal('fetch', fetch)
	return fetch
}

describe('requestFile', () => {
	it('returns the file with the name the API gave it, sending the token', async () => {
		const fetch = stubFetch(
			new Response('<gpx/>', {
				headers: {
					'Content-Type': 'application/gpx+xml',
					'Content-Disposition': 'attachment; filename="morning-loop.gpx"',
				},
			}),
		)

		const file = await requestFile('/logbook/routes/7/gpx', { token: 'a1' })

		expect(await file.blob.text()).toBe('<gpx/>')
		expect(file.filename).toBe('morning-loop.gpx')
		const [url, init] = fetch.mock.calls[0]!
		expect(url).toBe('/api/logbook/routes/7/gpx')
		expect(init?.headers).toMatchObject({ Authorization: 'Bearer a1' })
	})

	it('has no name when the API sends none', async () => {
		stubFetch(new Response('<gpx/>'))

		expect((await requestFile('/logbook/routes/7/gpx')).filename).toBeNull()
	})

	it('fails with the API error', async () => {
		stubFetch(new Response(JSON.stringify({ detail: 'Route not found.' }), { status: 404 }))

		const failure = requestFile('/logbook/routes/7/gpx')

		await expect(failure).rejects.toBeInstanceOf(ApiError)
		await expect(failure).rejects.toMatchObject({ status: 404, detail: 'Route not found.' })
	})
})
