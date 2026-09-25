import { describe, expect, it } from 'vitest'

import { hasErrors, validateCreateAccount, validateSignIn } from './validation'

describe('validateSignIn', () => {
	it('accepts a filled-in form', () => {
		expect(validateSignIn({ email: 'lina@example.se', password: 'x' })).toEqual({})
	})

	it('asks for both fields when empty', () => {
		expect(validateSignIn({ email: '', password: '' })).toEqual({
			email: 'auth.errors.emailRequired',
			password: 'auth.errors.passwordRequired',
		})
	})

	it('treats a whitespace-only email as missing', () => {
		expect(validateSignIn({ email: '   ', password: 'x' }).email).toBe(
			'auth.errors.emailRequired',
		)
	})

	it.each(['lina', 'lina@', 'lina@example', 'li na@example.se'])(
		'rejects the malformed email %j',
		(email) => {
			expect(validateSignIn({ email, password: 'x' }).email).toBe('auth.errors.emailInvalid')
		},
	)

	it('accepts an email with surrounding whitespace', () => {
		expect(validateSignIn({ email: ' lina@example.se ', password: 'x' })).toEqual({})
	})

	it('does not trim the password', () => {
		expect(validateSignIn({ email: 'lina@example.se', password: ' ' })).toEqual({})
	})
})

describe('validateCreateAccount', () => {
	const valid = { name: 'Lina', email: 'lina@example.se', password: '12345678' }

	it('accepts a filled-in form', () => {
		expect(validateCreateAccount(valid)).toEqual({})
	})

	it('treats a whitespace-only name as missing', () => {
		expect(validateCreateAccount({ ...valid, name: '  ' }).name).toBe(
			'auth.errors.nameRequired',
		)
	})

	it('rejects a password shorter than 8 characters', () => {
		expect(validateCreateAccount({ ...valid, password: '1234567' }).password).toBe(
			'auth.errors.passwordTooShort',
		)
	})
})

describe('hasErrors', () => {
	it('is false for no errors and true for any error', () => {
		expect(hasErrors({})).toBe(false)
		expect(hasErrors({ email: 'auth.errors.emailRequired' })).toBe(true)
	})
})
