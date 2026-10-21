import type { RouteLocationRaw } from 'vue-router'

export { default as SegmentedNav } from './SegmentedNav.vue'

export interface SegmentedNavItem<Value extends string> {
	value: Value
	label: string
	to: RouteLocationRaw
}
