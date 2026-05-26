// useTheme.js — forced light mode (dark mode removed)
import { useState, useEffect, createContext, useContext } from 'react';

export const ThemeContext = createContext({ theme: 'light', toggleTheme: () => {} });

export function useTheme() {
    return useContext(ThemeContext);
}

export function useThemeProvider() {
    const [theme] = useState('light');

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', 'light');
        localStorage.setItem('hf-theme', 'light');
    }, []);

    const toggleTheme = () => {}; // No-op, light mode only

    return { theme, toggleTheme };
}
