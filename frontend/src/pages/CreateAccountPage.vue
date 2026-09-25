<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { AuthLayout, CreateAccountForm } from '@/features/auth'
import { Button } from '@/shared/ui/button'

const { t } = useI18n()
</script>

<template>
	<AuthLayout :title="t('auth.createAccount.title')" :lead="t('auth.createAccount.lead')">
		<CreateAccountForm />
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
