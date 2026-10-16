import { VueQueryPlugin, type VueQueryPluginOptions } from '@tanstack/vue-query'
import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

import { useFetchedTiles } from '../fetched-tiles/api'
import { useQueuedTiles } from './api'

const get = vi.hoisted(() => vi.fn())
vi.mock('../../dev-api/client', () => ({ api: { GET: get } }))

const queuedTile = (x: number) => ({
	type: 'Feature',
	geometry: { type: 'Polygon', coordinates: [[[18, 59]]] },
	properties: { layer: 'roads', z: 14, x, y: 4821, status: 'pending' },
})
const collection = (...features: unknown[]) => ({ type: 'FeatureCollection', features })
const ok = (body: unknown) => ({ data: body, response: new Response(null, { status: 200 }) })

// as in main.ts: a failed request is not retried
const vueQueryOptions: VueQueryPluginOptions = {
	queryClientConfig: { defaultOptions: { queries: { retry: false } } },
}

let host: VueWrapper | null = null

function mountTools() {
	let queue!: ReturnType<typeof useQueuedTiles>
	host = mount(
		defineComponent({
			setup() {
				useFetchedTiles()
				queue = useQueuedTiles()
				return () => null
			},
		}),
		{ global: { plugins: [[VueQueryPlugin, vueQueryOptions]] } },
	)
	return queue
}

const fetchedLoads = () => get.mock.calls.filter(([path]) => path === '/tiles/fetched').length

afterEach(() => {
	host?.unmount()
	get.mockReset()
})

describe('useQueuedTiles', () => {
	it('reloads the fetched tiles when a tile has left the queue', async () => {
		let queued = collection(queuedTile(1), queuedTile(2))
		get.mockImplementation((path: string) =>
			Promise.resolve(ok(path === '/tiles/queued' ? queued : collection())),
		)
		const queue = mountTools()
		await vi.waitFor(() => expect(queue.data.value).toEqual(queued))
		expect(fetchedLoads()).toBe(1)

		queued = collection(queuedTile(2))
		await queue.refetch()

		await vi.waitFor(() => expect(fetchedLoads()).toBe(2))
	})

	it('leaves the fetched tiles alone while the queue only grows', async () => {
		let queued = collection(queuedTile(1))
		get.mockImplementation((path: string) =>
			Promise.resolve(ok(path === '/tiles/queued' ? queued : collection())),
		)
		const queue = mountTools()
		await vi.waitFor(() => expect(queue.data.value).toEqual(queued))

		queued = collection(queuedTile(1), queuedTile(2))
		await queue.refetch()
		await vi.waitFor(() => expect(queue.data.value).toEqual(queued))

		expect(fetchedLoads()).toBe(1)
	})
})
