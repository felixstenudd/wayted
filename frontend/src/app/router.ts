import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import LandingPage from '@/pages/LandingPage.vue'
import PlannerPage from '@/pages/PlannerPage.vue'

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
]

export const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes,
})
