/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        rain: {
          bg: '#0A0F0A',
          black: '#060A06',
          dark: '#0D120D',
          surface: '#111A11',
          panel: '#152015',
          border: '#1E2E1E',
          muted: '#3A4A3A',
          silver: '#8A9A8A',
          dim: '#5A6A5A',
          text: '#D0E0D0',
          white: '#E8F0E8',
          // Primary accent: teal/cyan
          teal: '#00D4AA',
          cyan: '#00E5C8',
          // Secondary accents
          purple: '#8B5CF6',
          magenta: '#D946EF',
          orange: '#F97316',
          lime: '#AAFF00',
          blue: '#4A9EFF',
          green: '#4AFF8A',
          red: '#FF4444',
          amber: '#FFB347',
          gold: '#FFD700',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-teal': '0 0 20px rgba(0,212,170,0.4)',
        'glow-cyan': '0 0 15px rgba(0,229,200,0.3)',
        'glow-purple': '0 0 20px rgba(139,92,246,0.4)',
        'glow-green': '0 0 15px rgba(74,255,138,0.3)',
        'glow-red': '0 0 15px rgba(255,68,68,0.3)',
        'inner-3d': 'inset 0 2px 4px rgba(255,255,255,0.05), inset 0 -2px 4px rgba(0,0,0,0.3)',
        'raised': '0 2px 8px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.2)',
      },
      backgroundImage: {
        'infinity-gradient': 'linear-gradient(135deg, #00D4AA, #00E5C8, #4AFF8A)',
        'accent-gradient': 'linear-gradient(135deg, #00D4AA, #8B5CF6)',
        'meter-gradient': 'linear-gradient(to top, #4AFF8A, #AAFF00, #FFB347, #FF4444)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan': 'scan 2s linear infinite',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
        'spin-slow': 'spin 8s linear infinite',
      },
      keyframes: {
        scan: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.6' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
