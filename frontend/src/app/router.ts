import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/features/auth'
import CreateAccountPage from '@/pages/CreateAccountPage.vue'
import LandingPage from '@/pages/LandingPage.vue'
import PlannerPage from '@/pages/PlannerPage.vue'
import SignInPage from '@/pages/SignInPage.vue'

import { pinia } from './plugins/pinia'

const routes: RouteRecordRaw[] = [
	{
		path: '/',
		name: 'landing',
		component: LandingPage,
	},
	{
		path: '/plan',
		name: 'planner',
		component: PlannerPage,
	},
	{
		path: '/sign-in',
		name: 'sign-in',
		component: SignInPage,
	},
	{
		path: '/create-account',
		name: 'create-account',
		component: CreateAccountPage,
	},
]

export const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes,
})

// Learn whether someone is signed in before the first page renders, so it
// does not flash the signed-out view. Later navigations reuse the result.
router.beforeEach(() => useAuthStore(pinia).restore())
