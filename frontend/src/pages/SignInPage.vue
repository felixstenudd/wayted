<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { AuthLayout, SignInForm } from '@/features/auth'
import { Button } from '@/shared/ui/button'

const { t } = useI18n()
</script>

<template>
	<AuthLayout :title="t('auth.signIn.title')">
		<SignInForm />
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
