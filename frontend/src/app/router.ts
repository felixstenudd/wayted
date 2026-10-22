import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { authRedirect, useAuthStore } from '@/features/auth'
import CreateAccountPage from '@/pages/CreateAccountPage.vue'
import LandingPage from '@/pages/LandingPage.vue'
import MapPage from '@/pages/MapPage.vue'
import SignInPage from '@/pages/SignInPage.vue'

import { pinia } from './plugins/pinia'

const routes: RouteRecordRaw[] = [
	{
		path: '/',
		name: 'landing',
		meta: { access: 'signed-out' },
		component: LandingPage,
	},
	{
		path: '/plan',
		name: 'planner',
		meta: { access: 'signed-in' },
		component: MapPage,
	},
	{
		path: '/routes',
		name: 'routes',
		meta: { access: 'signed-in' },
		component: MapPage,
	},
	{
		path: '/routes/:id(\\d+)',
		name: 'route',
		meta: { access: 'signed-in' },
		component: MapPage,
	},
	{
		path: '/sign-in',
		name: 'sign-in',
		meta: { access: 'signed-out' },
		component: SignInPage,
	},
	{
		path: '/create-account',
		name: 'create-account',
		meta: { access: 'signed-out' },
		component: CreateAccountPage,
	},
]

export const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes,
})

// Learn whether someone is signed in before the first page renders, so it
// does not flash the signed-out view. Later navigations reuse the result.
router.beforeEach(async (to) => {
	const auth = useAuthStore(pinia)
	await auth.restore()
	return authRedirect(to, auth.isSignedIn, { signIn: 'sign-in', home: 'planner' })
})
