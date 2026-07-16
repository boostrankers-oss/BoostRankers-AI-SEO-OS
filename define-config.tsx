import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/app/', // Change this to your actual subfolder path, or '/' for the root domain
})