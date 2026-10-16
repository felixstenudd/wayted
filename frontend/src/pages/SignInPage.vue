<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'

import { AuthLayout, SignInForm, useAuthStore, useAuthSubmit } from '@/features/auth'
import { Button } from '@/shared/ui/button'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const { submit, submitting, formError } = useAuthSubmit(auth.signIn, () =>
	router.push({ name: 'planner' }),
)
</script>

<template>
	<AuthLayout :title="t('auth.signIn.title')">
		<SignInForm :submitting="submitting" :form-error="formError" @submit="submit" />
		<template #footer>
			{{ t('auth.signIn.noAccount') }}
			<Button as-child variant="link">
				<RouterLink :to="{ name: 'create-account' }">{{
					t('auth.signIn.createAccount')
				}}</RouterLink>
			</Button>
		</template>
	</AuthLayout>
</template>
