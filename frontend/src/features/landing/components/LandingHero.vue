<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { Button } from '@/shared/ui/button'

import CourseIllustration from './CourseIllustration.vue'

const { t } = useI18n()
</script>

<template>
	<section
		aria-labelledby="landing-title"
		class="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 px-4 pt-8 pb-16 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:gap-16 lg:px-8 lg:pt-16 lg:pb-24"
	>
		<div class="flex flex-col items-start gap-6">
			<h1 id="landing-title" class="text-hero text-ink">{{ t('landing.hero.title') }}</h1>
			<p class="max-w-md text-title font-normal text-graphite">
				{{ t('landing.hero.lead') }}
			</p>
			<div class="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center sm:gap-6">
				<Button as-child size="lg">
					<RouterLink :to="{ name: 'planner' }">{{
						t('landing.startPlanning')
					}}</RouterLink>
				</Button>
				<Button as-child variant="link" class="self-start sm:self-auto">
					<RouterLink :to="{ name: 'create-account' }">{{
						t('landing.createAccount')
					}}</RouterLink>
				</Button>
			</div>
		</div>
		<CourseIllustration />
	</section>
</template>
