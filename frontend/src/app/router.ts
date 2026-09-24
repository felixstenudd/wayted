import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import PlannerPage from '@/pages/PlannerPage.vue'

const routes: RouteRecordRaw[] = [
	{
		path: '/',
		name: 'planner',
		component: PlannerPage,
	},
]

export const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes,
})
