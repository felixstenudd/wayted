import js from '@eslint/js'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import boundaries from 'eslint-plugin-boundaries'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

const anyFeature = { element: { type: 'feature' } }
const sameFeature = {
	element: { type: 'feature', captured: { featureName: '{{from.featureName}}' } },
}
const featureInternals = { element: { type: 'feature', fileInternalPath: '!index.ts' } }

const to = (...types) => types.map((type) => ({ to: { element: { type } } }))

export default defineConfigWithVueTs(
	{
		ignores: [
			'dist/**',
			'dist-dev-panel/**',
			'node_modules/**',
			'coverage/**',
			'src/dev-panel/dev-api/schema.d.ts',
		],
	},

	js.configs.recommended,
	pluginVue.configs['flat/recommended'],
	vueTsConfigs.recommendedTypeChecked,

	{
		languageOptions: {
			globals: { ...globals.browser },
		},
		rules: {
			'@typescript-eslint/no-explicit-any': 'error',
			'@typescript-eslint/consistent-type-imports': 'error',
			'no-console': ['error', { allow: ['warn', 'error'] }],
			'vue/multi-word-component-names': 'off',
			'vue/component-api-style': ['error', ['script-setup']],
			'vue/define-props-declaration': ['error', 'type-based'],
			'vue/define-emits-declaration': ['error', 'type-based'],
			'vue/block-order': ['error', { order: ['script', 'template', 'style'] }],
			'vue/define-macros-order': 'error',
			'vue/no-unused-refs': 'error',
			'vue/no-useless-v-bind': 'error',
		},
	},

	{
		files: ['src/**/*.{ts,vue}'],
		plugins: { boundaries },
		settings: {
			'import/resolver': {
				typescript: {
					project: './tsconfig.app.json',
					extensions: ['.ts', '.vue', '.js', '.json'],
				},
			},
			'boundaries/include': ['src/**/*'],
			'boundaries/elements': [
				{ type: 'app', pattern: 'src/app' },
				{ type: 'dev-panel', pattern: 'src/dev-panel' },
				{ type: 'pages', pattern: 'src/pages' },
				{ type: 'feature', pattern: 'src/features/*', capture: ['featureName'] },
				{ type: 'shared', pattern: 'src/shared' },
				{ type: 'assets', pattern: 'src/assets' },
			],
		},
		rules: {
			'boundaries/dependencies': [
				'error',
				{
					default: 'disallow',
					message: '{{from.type}} is not allowed to import {{to.type}}',
					policies: [
						{
							from: [{ element: { type: 'app' } }],
							allow: to('app', 'pages', 'feature', 'shared', 'assets'),
						},
						{
							from: [{ element: { type: 'dev-panel' } }],
							allow: to('dev-panel', 'feature', 'shared', 'assets'),
						},
						{
							from: [{ element: { type: 'pages' } }],
							allow: to('pages', 'feature', 'shared', 'assets'),
						},
						{
							from: [{ element: { type: 'feature' } }],
							allow: to('feature', 'shared', 'assets'),
						},
						{
							from: [{ element: { type: 'shared' } }],
							allow: to('shared', 'assets'),
						},
						{
							from: [
								{ element: { type: 'app' } },
								{ element: { type: 'dev-panel' } },
								{ element: { type: 'pages' } },
								anyFeature,
							],
							disallow: [{ to: featureInternals }],
							message:
								'Reach another feature through its index.ts, not its internals',
						},
						{
							from: [anyFeature],
							allow: [{ to: sameFeature }],
						},
					],
				},
			],
		},
	},

	{
		files: ['**/*.{test,spec}.ts'],
		rules: {
			'boundaries/dependencies': 'off',
		},
	},

	skipFormatting,
)
