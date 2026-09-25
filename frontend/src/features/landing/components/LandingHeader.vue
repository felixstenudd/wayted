<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { Button } from '@/shared/ui/button'
import { Wordmark } from '@/shared/ui/wordmark'

const { t } = useI18n()
</script>

<template>
	<header
		class="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8"
	>
		<RouterLink :to="{ name: 'landing' }" class="rounded-sm">
			<Wordmark>{{ t('app.name') }}</Wordmark>
		</RouterLink>
		<nav :aria-label="t('landing.nav.label')" class="flex items-center gap-2 sm:gap-3">
			<Button as-child variant="ghost" size="sm">
				<RouterLink to="/sign-in">{{ t('landing.signIn') }}</RouterLink>
			</Button>
			<Button as-child size="sm" class="max-sm:hidden">
				<RouterLink :to="{ name: 'planner' }">{{ t('landing.startPlanning') }}</RouterLink>
			</Button>
		</nav>
	</header>
</template>
