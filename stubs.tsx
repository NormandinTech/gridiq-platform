{
  "name": "gridiq-dashboard",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite --port 3000",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext .ts,.tsx",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2",
    "@tanstack/react-query": "^5.56.2",
    "recharts": "^2.12.7",
    "mapbox-gl": "^3.6.0",
    "react-map-gl": "^7.1.7",
    "date-fns": "^3.6.0",
    "zustand": "^5.0.0",
    "clsx": "^2.1.1",
    "lucide-react": "^0.446.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.8",
    "@types/react-dom": "^18.3.0",
    "@types/mapbox-gl": "^3.4.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.4",
    "vite": "^5.4.6",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.12",
    "vitest": "^2.1.1"
  }
}
