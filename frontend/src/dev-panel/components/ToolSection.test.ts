import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ToolSection from './ToolSection.vue'

const mountSection = () =>
	mount(ToolSection, {
		props: { title: 'Queue' },
		slots: { default: '<p data-test="content">Nothing is queued.</p>' },
		attachTo: document.body,
	})

describe('ToolSection', () => {
	it('shows its content at first', () => {
		const section = mountSection()

		expect(section.get('[data-test="content"]').isVisible()).toBe(true)
		expect(section.get('button').attributes('aria-expanded')).toBe('true')
		section.unmount()
	})

	it('hides its content when the heading is pressed, and keeps it mounted', async () => {
		const section = mountSection()

		await section.get('button').trigger('click')

		expect(section.get('[data-test="content"]').isVisible()).toBe(false)
		expect(section.get('button').attributes('aria-expanded')).toBe('false')
		section.unmount()
	})

	it('shows the content again on a second press', async () => {
		const section = mountSection()

		await section.get('button').trigger('click')
		await section.get('button').trigger('click')

		expect(section.get('[data-test="content"]').isVisible()).toBe(true)
		section.unmount()
	})
})
