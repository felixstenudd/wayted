import { afterEach, describe, expect, it, vi } from 'vitest'

import { saveFile } from './saveFile'

afterEach(() => {
	vi.restoreAllMocks()
	vi.useRealTimers()
})

describe('saveFile', () => {
	it('clicks a download link to the file, then lets its URL go', () => {
		vi.useFakeTimers()
		// jsdom has no object URLs.
		const createObjectURL = vi.fn(() => 'blob:route')
		const revokeObjectURL = vi.fn()
		URL.createObjectURL = createObjectURL
		URL.revokeObjectURL = revokeObjectURL
		const clicked: HTMLAnchorElement[] = []
		vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
			this: HTMLAnchorElement,
		) {
			clicked.push(this)
		})
		const blob = new Blob(['<gpx/>'])

		saveFile(blob, 'morning-loop.gpx')

		expect(createObjectURL).toHaveBeenCalledWith(blob)
		expect(clicked.map((a) => [a.href, a.download])).toEqual([
			['blob:route', 'morning-loop.gpx'],
		])
		// The browser may still be reading the file a few seconds on.
		vi.advanceTimersByTime(29_999)
		expect(revokeObjectURL).not.toHaveBeenCalled()
		vi.advanceTimersByTime(1)
		expect(revokeObjectURL).toHaveBeenCalledWith('blob:route')
	})
})
