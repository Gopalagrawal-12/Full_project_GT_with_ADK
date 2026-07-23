import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Base surfaces — near-black with a faint blue-violet cast, not pure zinc
        canvas: '#0a0b0f',
        panel: '#101218',
        'panel-raised': '#15171f',
        hairline: '#22252f',
        // Signature accent: electric indigo for "the model is thinking"
        pulse: {
          DEFAULT: '#7c6ff0',
          dim: '#4b4394',
          glow: 'rgba(124, 111, 240, 0.35)',
        },
        // Route colors — encode the actual SQL/VECTOR fork
        sql: { DEFAULT: '#e0a339', dim: '#4a3a1c' },
        vector: { DEFAULT: '#31b0a3', dim: '#173733' },
        support: { DEFAULT: '#c96b5a', dim: '#3a2320' },
        success: '#4ade80',
      },
      fontFamily: {
        sans: ['"Inter"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(124,111,240,0.4), 0 0 20px rgba(124,111,240,0.25)',
        'glow-sql': '0 0 0 1px rgba(224,163,57,0.4), 0 0 16px rgba(224,163,57,0.2)',
        'glow-vector': '0 0 0 1px rgba(49,176,163,0.4), 0 0 16px rgba(49,176,163,0.2)',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(0.9)', opacity: '0.7' },
          '80%': { transform: 'scale(1.6)', opacity: '0' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.8s cubic-bezier(0.2,0.6,0.4,1) infinite',
        shimmer: 'shimmer 2.5s linear infinite',
      },
    },
  },
  plugins: [],
} satisfies Config;
