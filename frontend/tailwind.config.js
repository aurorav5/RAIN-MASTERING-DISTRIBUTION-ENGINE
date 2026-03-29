/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        rain: {
          bg: '#0D0B1A',
          black: '#08070F',
          dark: '#0A0918',
          surface: '#141225',
          panel: '#1C1835',
          border: '#2A2545',
          muted: '#4A4565',
          silver: '#B8B5C8',
          dim: '#7A7595',
          text: '#E8E6F0',
          white: '#F0F0F0',
          red: '#FF4444',
          purple: '#8B5CF6',
          magenta: '#D946EF',
          orange: '#F97316',
          lime: '#AAFF00',
          cyan: '#00D4FF',
          blue: '#4A9EFF',
          green: '#4AFF8A',
          amber: '#FFB347',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-purple': '0 0 20px rgba(139,92,246,0.4)',
        'glow-magenta': '0 0 20px rgba(217,70,239,0.4)',
        'glow-lime': '0 0 15px rgba(170,255,0,0.3)',
        'glow-cyan': '0 0 15px rgba(0,212,255,0.3)',
        'glow-red': '0 0 15px rgba(255,68,68,0.3)',
        'inner-3d': 'inset 0 2px 4px rgba(255,255,255,0.1), inset 0 -2px 4px rgba(0,0,0,0.3)',
        'raised': '0 2px 8px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.2)',
      },
      backgroundImage: {
        'infinity-gradient': 'linear-gradient(135deg, #8B5CF6, #D946EF, #F97316)',
        'knob-ring': 'conic-gradient(from 220deg, #8B5CF6, #D946EF, #F97316, #4A4565)',
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
