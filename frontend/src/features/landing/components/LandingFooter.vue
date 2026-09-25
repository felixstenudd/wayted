<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { Button } from '@/shared/ui/button'
import { Wordmark } from '@/shared/ui/wordmark'

const { t } = useI18n()
</script>

<template>
	<footer class="border-t border-line">
		<div
			class="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8"
		>
			<Wordmark>{{ t('app.name') }}</Wordmark>
			<nav :aria-label="t('landing.nav.footerLabel')" class="flex gap-6">
				<Button as-child variant="link" size="sm">
					<RouterLink :to="{ name: 'sign-in' }">{{ t('landing.signIn') }}</RouterLink>
				</Button>
				<Button as-child variant="link" size="sm">
					<RouterLink :to="{ name: 'create-account' }">{{
						t('landing.createAccount')
					}}</RouterLink>
				</Button>
			</nav>
		</div>
	</footer>
</template>
