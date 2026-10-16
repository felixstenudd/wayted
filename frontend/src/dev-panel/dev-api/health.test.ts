import { VueQueryPlugin, type VueQueryPluginOptions } from '@tanstack/vue-query'
import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

import { useQueuedTiles } from '../tools/queue/api'
import { useHealth } from './health'

const get = vi.hoisted(() => vi.fn())
vi.mock('./client', () => ({ api: { GET: get } }))

const NOTHING_QUEUED = { type: 'FeatureCollection', features: [] }
const answer = (status: number, body?: unknown) => {
	const response = new Response(null, { status })
	return Promise.resolve(response.ok ? { data: body, response } : { error: body, response })
}

// as in main.ts: a failed request is not retried
const vueQueryOptions: VueQueryPluginOptions = {
	queryClientConfig: { defaultOptions: { queries: { retry: false } } },
}

let host: VueWrapper | null = null

function mountPanel() {
	let queue!: ReturnType<typeof useQueuedTiles>
	host = mount(
		defineComponent({
			setup() {
				useHealth()
				queue = useQueuedTiles()
				return () => null
			},
		}),
		{ global: { plugins: [[VueQueryPlugin, vueQueryOptions]] } },
	)
	return queue
}

const loads = (wanted: string) => get.mock.calls.filter(([path]) => path === wanted).length

beforeEach(() => {
	vi.useFakeTimers()
})

afterEach(() => {
	host?.unmount()
	get.mockReset()
	vi.useRealTimers()
})

describe('useHealth', () => {
	it('loads again what failed while the dev API was away', async () => {
		let isUp = false
		get.mockImplementation((path: string) => {
			if (!isUp) return answer(502)
			return answer(200, path === '/health' ? { status: 'ok' } : NOTHING_QUEUED)
		})
		const queue = mountPanel()
		await vi.advanceTimersByTimeAsync(0)
		expect(queue.error.value).not.toBeNull()

		isUp = true
		await vi.advanceTimersByTimeAsync(10_000)

		expect(queue.error.value).toBeNull()
		expect(queue.data.value).toEqual(NOTHING_QUEUED)
	})

	it('leaves alone what loaded fine', async () => {
		let isHealthUp = false
		get.mockImplementation((path: string) => {
			if (path === '/health') return isHealthUp ? answer(200, { status: 'ok' }) : answer(502)
			return answer(200, NOTHING_QUEUED)
		})
		mountPanel()
		await vi.advanceTimersByTimeAsync(0)

		isHealthUp = true
		await vi.advanceTimersByTimeAsync(10_000)

		expect(loads('/health')).toBe(2)
		expect(loads('/tiles/queued')).toBe(1)
	})
})
