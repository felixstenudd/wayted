import { describe, expect, it } from 'vitest'

import { attributionStrip, chooseFrame, imagePadding, LANDSCAPE, PORTRAIT } from './imageLayout'

describe('chooseFrame', () => {
	it('picks landscape for a route wider than it is tall', () => {
		expect(chooseFrame({ west: 18, south: 59.3, east: 18.1, north: 59.32 })).toBe(LANDSCAPE)
	})

	it('picks portrait for a route taller than it is wide', () => {
		expect(chooseFrame({ west: 18, south: 59.3, east: 18.02, north: 59.35 })).toBe(PORTRAIT)
	})

	it('compares as the map draws, not in degrees', () => {
		// Twice as wide as tall in degrees, but at 60° north a degree east is half a degree north.
		const square = { west: 18, south: 60, east: 18.02, north: 60.01 }
		expect(chooseFrame(square)).toBe(PORTRAIT)
		// The same degrees at the equator are twice as wide as tall.
		expect(chooseFrame({ west: 18, south: 0, east: 18.02, north: 0.01 })).toBe(LANDSCAPE)
	})

	it('switches where both frames are filled alike', () => {
		// The landscape and portrait aspects are 1.90 and 0.80; their geometric mean is 1.23.
		const at = (aspect: number) => ({
			west: 0,
			south: -0.005,
			east: 0.01 * aspect,
			north: 0.005,
		})
		expect(chooseFrame(at(1.25))).toBe(LANDSCAPE)
		expect(chooseFrame(at(1.21))).toBe(PORTRAIT)
	})

	it('picks landscape for a line straight east or a single point', () => {
		expect(chooseFrame({ west: 18, south: 59, east: 18.1, north: 59 })).toBe(LANDSCAPE)
		expect(chooseFrame({ west: 18, south: 59, east: 18, north: 59 })).toBe(LANDSCAPE)
	})

	it('picks portrait for a line straight north', () => {
		expect(chooseFrame({ west: 18, south: 59, east: 18, north: 59.1 })).toBe(PORTRAIT)
	})
})

describe('imagePadding', () => {
	it('keeps 8% of each direction clear on both of its sides', () => {
		expect(imagePadding(LANDSCAPE)).toEqual({ top: 50, bottom: 50, left: 96, right: 96 })
		expect(imagePadding(PORTRAIT)).toEqual({ top: 108, bottom: 108, left: 86, right: 86 })
	})
})

describe('attributionStrip', () => {
	it('sits in the bottom-right corner, sized to its text', () => {
		expect(attributionStrip(LANDSCAPE, 250.4)).toEqual({
			x: 1200 - 263,
			y: 630 - 20,
			width: 263,
			height: 20,
		})
	})
})
