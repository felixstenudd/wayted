import { useMutation } from '@tanstack/vue-query'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { ApiError } from '@/shared/api'

// The status codes backend/app/auth/router.py gives its errors.
const ERROR_KEYS: Partial<Record<number, string>> = {
	400: 'auth.errors.invalidInput',
	401: 'auth.errors.invalidCredentials',
	409: 'auth.errors.emailTaken',
}

/**
 * Sends a sign-in or create-account form to the server, and exposes what the
 * form shows meanwhile: whether it is in flight, and the message if it failed.
 */
export function useAuthSubmit<Values>(
	action: (values: Values) => Promise<void>,
	onSuccess: () => unknown,
) {
	const { t } = useI18n()
	const { mutate, isPending, error } = useMutation({ mutationFn: action, onSuccess })

	const formError = computed(() => {
		if (error.value === null) return undefined
		const key = error.value instanceof ApiError ? ERROR_KEYS[error.value.status] : undefined
		return t(key ?? 'auth.errors.unexpected')
	})

	return { submit: (values: Values) => mutate(values), submitting: isPending, formError }
}
