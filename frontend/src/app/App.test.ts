import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import { useAuthStore } from '@/features/auth'
import { usePlannerStore } from '@/features/route-planner'

import App from './App.vue'

const RUNNER = { email: 'runner@example.com', name: 'Runner' }
const ROUTES_KEY = ['logbook', 'routes']

function setup() {
	const queryClient = new QueryClient()
	const pinia = createPinia()
	mount(App, {
		global: {
			plugins: [pinia, [VueQueryPlugin, { queryClient }]],
			stubs: { RouterView: true },
		},
	})
	const auth = useAuthStore(pinia)
	const planner = usePlannerStore(pinia)
	return { queryClient, auth, planner }
}

async function signIn(
	{ queryClient, auth, planner }: ReturnType<typeof setup>,
	user: typeof RUNNER,
): Promise<void> {
	auth.user = user
	await nextTick()
	queryClient.setQueryData(ROUTES_KEY, [{ id: 1 }])
	planner.receiveDefaults({ green: 0.5 })
}

describe('App', () => {
	it("forgets the user's data when they sign out", async () => {
		const app = setup()
		await signIn(app, RUNNER)

		app.auth.user = null
		await nextTick()

		expect(app.queryClient.getQueryData(ROUTES_KEY)).toBeUndefined()
		expect(app.planner.preferenceWeights).toEqual({})
	})

	it('keeps it while the same user stays signed in', async () => {
		const app = setup()
		await signIn(app, RUNNER)

		app.auth.user = { ...RUNNER, name: 'Renamed' }
		await nextTick()

		expect(app.queryClient.getQueryData(ROUTES_KEY)).toEqual([{ id: 1 }])
	})
})
