import { describe, expect, it } from 'vitest'

import { cn } from './cn'

describe('cn', () => {
	it('keeps a type role and a text color together', () => {
		expect(cn('text-body text-graphite')).toBe('text-body text-graphite')
	})

	it('lets a later type role replace an earlier one', () => {
		expect(cn('text-body text-graphite', 'text-small')).toBe('text-graphite text-small')
	})

	it('lets a later text color replace an earlier one', () => {
		expect(cn('text-small text-ink', 'text-contour')).toBe('text-small text-contour')
	})

	it('treats the float shadow as a shadow size, not a shadow color', () => {
		expect(cn('shadow-float', 'shadow-none')).toBe('shadow-none')
	})

	it('drops falsy values', () => {
		expect(cn('bg-paper', false, undefined, 'text-ink')).toBe('bg-paper text-ink')
	})
})
