<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { AuthLayout, safeRedirect, SignInForm, useAuthStore, useAuthSubmit } from '@/features/auth'
import { Button } from '@/shared/ui/button'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const { submit, submitting, formError } = useAuthSubmit(auth.signIn, () =>
	router.push(safeRedirect(route.query.redirect) ?? { name: 'planner' }),
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
