import type { Component } from 'vue'

export { default as SegmentedControl } from './SegmentedControl.vue'

export interface SegmentedOption<Value extends string> {
	value: Value
	label: string
	icon?: Component
}
