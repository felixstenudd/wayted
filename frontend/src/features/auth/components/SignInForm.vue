<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'
import { FormField } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'

import { useValidatedForm } from '../composables/useValidatedForm'
import type { SignInValues } from '../types'
import { validateSignIn } from '../validation'
import FormAlert from './FormAlert.vue'
import PasswordInput from './PasswordInput.vue'

defineProps<{
	submitting?: boolean
	formError?: string | undefined
}>()

const emit = defineEmits<{
	submit: [values: SignInValues]
}>()

const { t } = useI18n()

const values = reactive<SignInValues>({ email: '', password: '' })
const { errors, submit } = useValidatedForm(values, validateSignIn, 'sign-in')

const errorMessages = computed(() => ({
	email: errors.value.email && t(errors.value.email),
	password: errors.value.password && t(errors.value.password),
}))

function onSubmit(): void {
	submit((valid) => emit('submit', { email: valid.email.trim(), password: valid.password }))
}
</script>

<template>
	<form novalidate class="flex flex-col gap-5" @submit.prevent="onSubmit">
		<FormField
			id="sign-in-email"
			v-slot="{ describedBy, invalid }"
			:label="t('auth.fields.email')"
			:error="errorMessages.email"
		>
			<Input
				id="sign-in-email"
				v-model="values.email"
				type="email"
				autocomplete="email"
				autocapitalize="none"
				spellcheck="false"
				:aria-describedby="describedBy"
				:aria-invalid="invalid || undefined"
			/>
		</FormField>
		<FormField
			id="sign-in-password"
			v-slot="{ describedBy, invalid }"
			:label="t('auth.fields.password')"
			:error="errorMessages.password"
		>
			<PasswordInput
				id="sign-in-password"
				v-model="values.password"
				autocomplete="current-password"
				:aria-describedby="describedBy"
				:aria-invalid="invalid || undefined"
			/>
		</FormField>
		<FormAlert v-if="formError" :message="formError" />
		<Button
			type="submit"
			size="lg"
			class="w-full"
			:disabled="submitting"
			:aria-busy="submitting || undefined"
		>
			{{ submitting ? t('auth.signIn.submitting') : t('auth.signIn.submit') }}
		</Button>
	</form>
</template>
