import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'

import { useSavedRoutesStore } from '../store'
import type { SavedRoute } from '../types'
import { useStretchPick } from './useStretchPick'

// Four edges east along one street, a junction every 0.001°.
const ROUTE = {
	id: 1,
	geometry: {
		type: 'LineString',
		coordinates: [0, 1, 2, 3, 4].map((i) => [20 + i * 0.001, 63.8]),
	},
	edges: [0, 1, 2, 3].map((seq) => ({ seq, length_m: 50, last_point: seq + 1 })),
} as unknown as SavedRoute

const junction = (i: number) => ({ lon: 20 + i * 0.001, lat: 63.8 })

function setup() {
	const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } })
	queryClient.setQueryData(['logbook', 'routes', 1], ROUTE)
	let pick!: ReturnType<typeof useStretchPick>
	let store!: ReturnType<typeof useSavedRoutesStore>
	mount(
		defineComponent({
			setup() {
				pick = useStretchPick(1)
				store = useSavedRoutesStore()
				return () => null
			},
		}),
		{ global: { plugins: [createPinia(), [VueQueryPlugin, { queryClient }]] } },
	)
	store.startPickingStretch()
	return { pick, store }
}

describe('useStretchPick', () => {
	it('places the start, then the end, snapping each to a junction', () => {
		const { pick } = setup()
		expect(pick.step.value).toBe('start')

		pick.placeAt({ lon: 20.0031, lat: 63.8001 })
		expect(pick.step.value).toBe('end')
		pick.placeAt(junction(1))

		expect(pick.step.value).toBe('adjust')
		expect(pick.stretch.value).toEqual({ from: 1, to: 3 })
		expect(pick.lengthM.value).toBe(100)
	})

	it('ignores a click far from the route', () => {
		const { pick } = setup()

		pick.placeAt({ lon: 20.002, lat: 63.81 })

		expect(pick.step.value).toBe('start')
	})

	it('moves whichever end is nearer once both are placed', () => {
		const { pick } = setup()
		pick.placeAt(junction(1))
		pick.placeAt(junction(2))

		pick.placeAt(junction(4))
		expect(pick.stretch.value).toEqual({ from: 1, to: 4 })
		pick.placeAt(junction(0))
		expect(pick.stretch.value).toEqual({ from: 0, to: 4 })
	})

	it('keeps the sliders from passing each other', () => {
		const { pick } = setup()
		pick.placeAt(junction(1))
		pick.placeAt(junction(3))

		pick.setFrom(4)
		expect(pick.stretch.value).toEqual({ from: 2, to: 3 })
		pick.setTo(0)
		expect(pick.stretch.value).toEqual({ from: 2, to: 3 })
	})
})
