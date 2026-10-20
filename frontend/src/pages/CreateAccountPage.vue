<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'

import { AuthLayout, CreateAccountForm, useAuthStore, useAuthSubmit } from '@/features/auth'
import { Button } from '@/shared/ui/button'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const { submit, submitting, formError } = useAuthSubmit(auth.createAccount, () =>
	router.push({ name: 'planner' }),
)
</script>

<template>
	<AuthLayout :title="t('auth.createAccount.title')" :lead="t('auth.createAccount.lead')">
		<CreateAccountForm :submitting="submitting" :form-error="formError" @submit="submit" />
		<template #footer>
			{{ t('auth.createAccount.haveAccount') }}
			<Button as-child variant="link">
				<RouterLink :to="{ name: 'sign-in' }">{{
					t('auth.createAccount.signIn')
				}}</RouterLink>
			</Button>
		</template>
	</AuthLayout>
</template>
