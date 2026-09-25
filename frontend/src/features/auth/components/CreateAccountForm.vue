<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'
import { FormField } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'

import { useValidatedForm } from '../composables/useValidatedForm'
import type { CreateAccountValues } from '../types'
import { MIN_PASSWORD_LENGTH, validateCreateAccount } from '../validation'
import FormAlert from './FormAlert.vue'
import PasswordInput from './PasswordInput.vue'

defineProps<{
	submitting?: boolean
	formError?: string | undefined
}>()

const emit = defineEmits<{
	submit: [values: CreateAccountValues]
}>()

const { t } = useI18n()

const values = reactive<CreateAccountValues>({ name: '', email: '', password: '' })
const { errors, submit } = useValidatedForm(values, validateCreateAccount, 'create-account')

const messageParams = { min: MIN_PASSWORD_LENGTH }
const errorMessages = computed(() => ({
	name: errors.value.name && t(errors.value.name),
	email: errors.value.email && t(errors.value.email),
	password: errors.value.password && t(errors.value.password, messageParams),
}))

function onSubmit(): void {
	submit((valid) =>
		emit('submit', {
			name: valid.name.trim(),
			email: valid.email.trim(),
			password: valid.password,
		}),
	)
}
</script>

<template>
	<form novalidate class="flex flex-col gap-5" @submit.prevent="onSubmit">
		<FormField
			id="create-account-name"
			v-slot="{ describedBy, invalid }"
			:label="t('auth.fields.name')"
			:error="errorMessages.name"
		>
			<Input
				id="create-account-name"
				v-model="values.name"
				type="text"
				autocomplete="name"
				:aria-describedby="describedBy"
				:aria-invalid="invalid || undefined"
			/>
		</FormField>
		<FormField
			id="create-account-email"
			v-slot="{ describedBy, invalid }"
			:label="t('auth.fields.email')"
			:error="errorMessages.email"
		>
			<Input
				id="create-account-email"
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
			id="create-account-password"
			v-slot="{ describedBy, invalid }"
			:label="t('auth.fields.password')"
			:hint="t('auth.fields.newPasswordHint', messageParams)"
			:error="errorMessages.password"
		>
			<PasswordInput
				id="create-account-password"
				v-model="values.password"
				autocomplete="new-password"
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
			{{ submitting ? t('auth.createAccount.submitting') : t('auth.createAccount.submit') }}
		</Button>
	</form>
</template>
