// useTheme.js — global dark/light mode hook
// Default: dark. Persists to localStorage.

import { useState, useEffect, createContext, useContext } from 'react';

export const ThemeContext = createContext({ theme: 'dark', toggleTheme: () => {} });

export function useTheme() {
    return useContext(ThemeContext);
}

export function useThemeProvider() {
    const [theme, setTheme] = useState(() => {
        return localStorage.getItem('hf-theme') || 'dark';
    });

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('hf-theme', theme);
    }, [theme]);

    const toggleTheme = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'));

    return { theme, toggleTheme };
}
