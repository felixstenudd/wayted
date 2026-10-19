import { afterEach, describe, expect, it, vi } from 'vitest'

import { useCurrentLocation } from './useCurrentLocation'

type Success = (position: { coords: { longitude: number; latitude: number } }) => void
type Failure = (error: { code: number }) => void

function stubGeolocation() {
	const pending: { success: Success; failure: Failure }[] = []
	vi.stubGlobal('navigator', {
		geolocation: {
			getCurrentPosition: (success: Success, failure: Failure) => {
				pending.push({ success, failure })
			},
		},
	})
	return pending
}

afterEach(() => {
	vi.unstubAllGlobals()
})

describe('useCurrentLocation', () => {
	it('is locating until the browser answers with a position', async () => {
		const pending = stubGeolocation()
		const location = useCurrentLocation()

		const found = location.locate()
		expect(location.isLocating.value).toBe(true)
		pending[0]?.success({ coords: { longitude: 20.26, latitude: 63.82 } })

		expect(await found).toEqual({ lon: 20.26, lat: 63.82 })
		expect(location.isLocating.value).toBe(false)
		expect(location.error.value).toBeNull()
	})

	it('says when location access is denied', async () => {
		const pending = stubGeolocation()
		const location = useCurrentLocation()

		const found = location.locate()
		pending[0]?.failure({ code: 1 })

		expect(await found).toBeNull()
		expect(location.error.value).toBe('denied')
		expect(location.isLocating.value).toBe(false)
	})

	it.each([2, 3])('says the position was not found for error code %i', async (code) => {
		const pending = stubGeolocation()
		const location = useCurrentLocation()

		const found = location.locate()
		pending[0]?.failure({ code })

		expect(await found).toBeNull()
		expect(location.error.value).toBe('unavailable')
	})

	it('says when the browser cannot share a location at all', async () => {
		vi.stubGlobal('navigator', {})
		const location = useCurrentLocation()

		expect(await location.locate()).toBeNull()
		expect(location.error.value).toBe('unsupported')
	})

	it('forgets the last error when trying again', () => {
		stubGeolocation()
		const location = useCurrentLocation()
		location.error.value = 'denied'

		void location.locate()

		expect(location.error.value).toBeNull()
	})
})
