import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { i18n } from '../../i18n'
import AreaLegend from './AreaLegend.vue'

const mountLegend = (hidden: string[]) =>
	mount(AreaLegend, {
		props: { layers: ['nature', 'parks', 'water_lines'], lineLayers: ['water_lines'], hidden },
		global: { plugins: [i18n] },
	})

const box = (legend: ReturnType<typeof mountLegend>, layer: string) =>
	legend.get(`input[value="${layer}"]`)

describe('AreaLegend', () => {
	it('shows every layer checked when none is hidden', () => {
		const legend = mountLegend([])

		expect((box(legend, 'nature').element as HTMLInputElement).checked).toBe(true)
		expect((box(legend, 'parks').element as HTMLInputElement).checked).toBe(true)
	})

	it('hides a layer when it is unchecked', async () => {
		const legend = mountLegend([])

		await box(legend, 'parks').setValue(false)

		expect(legend.emitted('update:hidden')).toEqual([[['parks']]])
	})

	it('says a line layer is drawn as a line', () => {
		const entry = mountLegend([]).get('label:last-of-type')

		expect(entry.text()).toContain('Rivers and coast')
		expect(entry.text()).toContain('line')
	})

	it('shows a hidden layer again when it is checked', async () => {
		const legend = mountLegend(['parks', 'nature'])

		await box(legend, 'parks').setValue(true)

		expect(legend.emitted('update:hidden')).toEqual([[['nature']]])
	})
})
