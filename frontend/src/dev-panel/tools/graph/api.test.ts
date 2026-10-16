import { VueQueryPlugin, type VueQueryPluginOptions } from '@tanstack/vue-query'
import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

import { problemOf } from '../../dev-api/problem'
import { useGraph } from './api'

const get = vi.hoisted(() => vi.fn())
vi.mock('../../dev-api/client', () => ({ api: { GET: get } }))

const inner = { west: 18, south: 59, east: 18.1, north: 59.1 }
const outer = { west: 17, south: 58, east: 19, north: 60 }
const graph = {
	edges: { type: 'FeatureCollection', features: [] },
	vertices: { type: 'FeatureCollection', features: [] },
}

const answer = (status: number, body: unknown) => {
	const response = new Response(null, { status })
	return response.ok ? { data: body, response } : { error: body, response }
}

// as in main.ts: a failed request is not retried
const vueQueryOptions: VueQueryPluginOptions = {
	queryClientConfig: { defaultOptions: { queries: { retry: false } } },
}

let host: VueWrapper | null = null

function mountGraph() {
	let result!: ReturnType<typeof useGraph>
	host = mount(
		defineComponent({
			setup() {
				result = useGraph()
				return () => null
			},
		}),
		{ global: { plugins: [[VueQueryPlugin, vueQueryOptions]] } },
	)
	return result
}

afterEach(() => {
	host?.unmount()
	get.mockReset()
})

describe('useGraph', () => {
	it('loads the graph of the bounds it is given', async () => {
		get.mockResolvedValueOnce(answer(200, graph))
		const { loaded, load } = mountGraph()

		load(inner)

		await vi.waitFor(() => expect(loaded.value).toEqual({ bounds: inner, graph }))
		expect(get).toHaveBeenCalledWith('/graph', { params: { query: inner } })
	})

	it('keeps the loaded graph when a later load is refused', async () => {
		get.mockResolvedValueOnce(answer(200, graph)).mockResolvedValueOnce(
			answer(400, { detail: 'Zoom in.' }),
		)
		const { loaded, error, load } = mountGraph()
		load(inner)
		await vi.waitFor(() => expect(loaded.value).toBeDefined())

		load(outer)

		await vi.waitFor(() =>
			expect(problemOf(error.value)).toEqual({ kind: 'refused', detail: 'Zoom in.' }),
		)
		expect(loaded.value).toEqual({ bounds: inner, graph })
	})

	it('drops the message when the next load works', async () => {
		get.mockResolvedValueOnce(answer(400, { detail: 'Zoom in.' })).mockResolvedValueOnce(
			answer(200, graph),
		)
		const { loaded, error, load } = mountGraph()
		load(outer)
		await vi.waitFor(() => expect(error.value).not.toBeNull())

		load(inner)

		await vi.waitFor(() => expect(loaded.value).toEqual({ bounds: inner, graph }))
		expect(error.value).toBeNull()
	})
})
