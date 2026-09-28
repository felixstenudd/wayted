import { computed, ref } from 'vue'

import type { FieldErrors } from '../types'
import { hasErrors } from '../validation'

/**
 * Errors stay hidden until the first submit attempt, then follow the input
 * live so a fixed field clears as soon as it is valid. On a failed submit,
 * focus moves to the first invalid field, found by `${idPrefix}-${field}`.
 */
export function useValidatedForm<Values extends object>(
	values: Values,
	validate: (values: Values) => FieldErrors<Values>,
	idPrefix: string,
) {
	const attempted = ref(false)

	const errors = computed<FieldErrors<Values>>(() => (attempted.value ? validate(values) : {}))

	function submit(onValid: (values: Values) => void): void {
		attempted.value = true
		const currentErrors = validate(values)
		if (!hasErrors(currentErrors)) {
			onValid(values)
			return
		}
		const fields = Object.keys(values) as (keyof Values)[]
		const firstInvalid = fields.find((field) => currentErrors[field] !== undefined)
		if (firstInvalid !== undefined) {
			document.getElementById(`${idPrefix}-${String(firstInvalid)}`)?.focus()
		}
	}

	return { errors, submit }
}
