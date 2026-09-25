export interface SignInValues {
	email: string
	password: string
}

export interface CreateAccountValues {
	name: string
	email: string
	password: string
}

/** i18n keys of field errors, by field name. A missing key means the field is valid. */
export type FieldErrors<Values> = Partial<Record<keyof Values, string>>
