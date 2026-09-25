import type { CreateAccountValues, FieldErrors, SignInValues } from './types'

// Deliberately loose: the only reliable email check is sending mail to it.
// This catches typos like a missing @ or domain before a round trip.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const MIN_PASSWORD_LENGTH = 8

function validateEmail(email: string): string | undefined {
	const trimmed = email.trim()
	if (trimmed === '') return 'auth.errors.emailRequired'
	if (!EMAIL_PATTERN.test(trimmed)) return 'auth.errors.emailInvalid'
	return undefined
}

function withoutEmpty<Values>(
	errors: Record<keyof Values, string | undefined>,
): FieldErrors<Values> {
	return Object.fromEntries(
		Object.entries(errors).filter(([, key]) => key !== undefined),
	) as FieldErrors<Values>
}

export function validateSignIn(values: SignInValues): FieldErrors<SignInValues> {
	return withoutEmpty<SignInValues>({
		email: validateEmail(values.email),
		password: values.password === '' ? 'auth.errors.passwordRequired' : undefined,
	})
}

export function validateCreateAccount(
	values: CreateAccountValues,
): FieldErrors<CreateAccountValues> {
	return withoutEmpty<CreateAccountValues>({
		name: values.name.trim() === '' ? 'auth.errors.nameRequired' : undefined,
		email: validateEmail(values.email),
		password:
			values.password.length < MIN_PASSWORD_LENGTH
				? 'auth.errors.passwordTooShort'
				: undefined,
	})
}

export function hasErrors<Values>(errors: FieldErrors<Values>): boolean {
	return Object.keys(errors).length > 0
}
