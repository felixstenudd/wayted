import { afterEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import type { SignInValues } from '../types'
import { validateSignIn } from '../validation'
import { useValidatedForm } from './useValidatedForm'

function setup(initial: SignInValues = { email: '', password: '' }) {
	const values = reactive({ ...initial })
	const form = useValidatedForm(values, validateSignIn, 'test')
	return { values, ...form }
}

afterEach(() => {
	document.body.innerHTML = ''
})

describe('useValidatedForm', () => {
	it('shows no errors before the first submit attempt', () => {
		const { errors } = setup()
		expect(errors.value).toEqual({})
	})

	it('shows errors and skips the callback when submitting an invalid form', () => {
		const { errors, submit } = setup()
		const onValid = vi.fn()
		submit(onValid)
		expect(onValid).not.toHaveBeenCalled()
		expect(errors.value.email).toBe('auth.errors.emailRequired')
	})

	it('clears an error as soon as the field becomes valid', () => {
		const { values, errors, submit } = setup()
		submit(vi.fn())
		values.email = 'lina@example.se'
		expect(errors.value.email).toBeUndefined()
		expect(errors.value.password).toBe('auth.errors.passwordRequired')
	})

	it('calls the callback with the values when the form is valid', () => {
		const { submit } = setup({ email: 'lina@example.se', password: 'secret' })
		const onValid = vi.fn()
		submit(onValid)
		expect(onValid).toHaveBeenCalledWith({ email: 'lina@example.se', password: 'secret' })
	})

	it('focuses the first invalid field in form order', () => {
		document.body.innerHTML = '<input id="test-email"><input id="test-password">'
		const { submit } = setup({ email: 'lina@example.se', password: '' })
		submit(vi.fn())
		expect(document.activeElement?.id).toBe('test-password')
	})
})
