import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BipolarSlider from './BipolarSlider.vue'

function mountSlider(modelValue = 0) {
	const wrapper = mount(BipolarSlider, {
		props: {
			modelValue,
			'onUpdate:modelValue': (value: number) => wrapper.setProps({ modelValue: value }),
			label: 'Parks',
			valueText: 'Prefer',
		},
	})
	return { wrapper, thumb: wrapper.get('[role="slider"]') }
}

describe('BipolarSlider', () => {
	it('is a slider from -1 to 1 named by its label and value text', () => {
		const { thumb } = mountSlider(0.37)

		expect(thumb.attributes()).toMatchObject({
			'aria-label': 'Parks',
			'aria-valuemin': '-1',
			'aria-valuemax': '1',
			'aria-valuenow': '0.37',
			'aria-valuetext': 'Prefer',
		})
	})

	it('steps between detents with the arrow keys', async () => {
		const { wrapper, thumb } = mountSlider()

		await thumb.trigger('keydown', { key: 'ArrowRight' })
		expect(wrapper.props('modelValue')).toBe(0.5)
		await thumb.trigger('keydown', { key: 'ArrowDown' })
		await thumb.trigger('keydown', { key: 'ArrowLeft' })
		expect(wrapper.props('modelValue')).toBe(-0.5)
	})

	it('fine-tunes by 0.01 with Alt and an arrow key', async () => {
		const { wrapper, thumb } = mountSlider(0.5)

		await thumb.trigger('keydown', { key: 'ArrowRight', altKey: true })
		await thumb.trigger('keydown', { key: 'ArrowRight', altKey: true })

		expect(wrapper.props('modelValue')).toBe(0.52)
	})

	it('goes to the ends with Home and End', async () => {
		const { wrapper, thumb } = mountSlider()

		await thumb.trigger('keydown', { key: 'End' })
		expect(wrapper.props('modelValue')).toBe(1)
		await thumb.trigger('keydown', { key: 'Home' })
		expect(wrapper.props('modelValue')).toBe(-1)
	})

	it('goes back to the middle on a double click of the thumb', async () => {
		const { wrapper, thumb } = mountSlider(0.37)

		await thumb.trigger('dblclick')

		expect(wrapper.props('modelValue')).toBe(0)
	})

	it('cannot be changed while disabled', async () => {
		const { wrapper, thumb } = mountSlider()
		await wrapper.setProps({ disabled: true })

		await thumb.trigger('keydown', { key: 'ArrowRight' })

		expect(wrapper.props('modelValue')).toBe(0)
		expect(thumb.attributes()).toMatchObject({ 'aria-disabled': 'true', tabindex: '-1' })
	})
})
