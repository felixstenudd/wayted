import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import CreateAccountPage from '@/pages/CreateAccountPage.vue'
import LandingPage from '@/pages/LandingPage.vue'
import PlannerPage from '@/pages/PlannerPage.vue'
import SignInPage from '@/pages/SignInPage.vue'

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
