<script setup lang="ts">
import { HowItWorks, LandingFooter, LandingHeader, LandingHero } from '@/features/landing'
</script>

<template>
	<div class="flex min-h-dvh flex-col">
		<LandingHeader />
		<main class="flex-1">
			<LandingHero />
			<HowItWorks />
		</main>
		<LandingFooter />
	</div>
</template>
