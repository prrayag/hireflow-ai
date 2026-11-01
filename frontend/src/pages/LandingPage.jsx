// LandingPage.jsx — HireFlow AI premium landing page
// Premium animated illustrations, real stats from MongoDB, light mode only

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import '../styles/landing.css';

gsap.registerPlugin(ScrollTrigger);

// ─── Animated Counter (smooth number count-up) ────────────────────────────────
function AnimatedCounter({ end, suffix = '', duration = 2000 }) {
    const [count, setCount] = useState(0);
    const ref = useRef(null);
    const counted = useRef(false);

    useEffect(() => {
        const observer = new IntersectionObserver(([entry]) => {
            if (entry.isIntersecting && !counted.current) {
                counted.current = true;
                const start = 0;
                const startTime = performance.now();
                const animate = (now) => {
                    const elapsed = now - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    // Ease-out cubic
                    const eased = 1 - Math.pow(1 - progress, 3);
                    setCount(Math.round(start + (end - start) * eased));
                    if (progress < 1) requestAnimationFrame(animate);
                };
                requestAnimationFrame(animate);
            }
        }, { threshold: 0.5 });
        if (ref.current) observer.observe(ref.current);
        return () => observer.disconnect();
    }, [end, duration]);

    return <span ref={ref}>{count}{suffix}</span>;
}

// ─── Illustration 1: Resume Parsing (Pure SVG) ───────────────────────────────
function ParseIllustration() {
    return (
        <svg viewBox="0 0 400 300" fill="none" className="feat-svg">
            {/* Document */}
            <rect x="100" y="30" width="200" height="240" rx="12" fill="#fff" stroke="#e2e5f0" strokeWidth="1.5" />
            {/* Header bar */}
            <rect x="100" y="30" width="200" height="36" rx="12" fill="#f8f9fc" />
            <rect x="100" y="54" width="200" height="12" fill="#f8f9fc" />
            <circle cx="118" cy="48" r="4" fill="#ff5f57" />
            <circle cx="130" cy="48" r="4" fill="#ffbd2e" />
            <circle cx="142" cy="48" r="4" fill="#28ca42" />
            {/* Text lines */}
            <rect x="120" y="80" width="160" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s1" />
            <rect x="120" y="96" width="130" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s2" />
            <rect x="120" y="112" width="150" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s3" />
            <rect x="120" y="128" width="100" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s4" />
            <rect x="120" y="148" width="160" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s1" />
            <rect x="120" y="164" width="120" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s2" />
            <rect x="120" y="180" width="140" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s3" />
            <rect x="120" y="200" width="80" height="6" rx="3" fill="#e2e5f0" className="svg-shimmer s4" />
            {/* Scan beam */}
            <line x1="108" y1="0" x2="292" y2="0" stroke="url(#beamGrad)" strokeWidth="2" className="svg-scan-line" />
            <defs>
                <linearGradient id="beamGrad">
                    <stop offset="0%" stopColor="transparent" />
                    <stop offset="30%" stopColor="#3b7ef8" />
                    <stop offset="70%" stopColor="#8b5cf6" />
                    <stop offset="100%" stopColor="transparent" />
                </linearGradient>
            </defs>
            {/* Extracted data badges */}
            <g className="svg-badge-float b1">
                <rect x="310" y="70" width="70" height="26" rx="6" fill="rgba(59,126,248,0.08)" stroke="rgba(59,126,248,0.2)" strokeWidth="1" />
                <text x="345" y="87" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="700" fontFamily="var(--sans)">Python</text>
            </g>
            <g className="svg-badge-float b2">
                <rect x="316" y="115" width="56" height="26" rx="6" fill="rgba(59,126,248,0.08)" stroke="rgba(59,126,248,0.2)" strokeWidth="1" />
                <text x="344" y="132" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="700" fontFamily="var(--sans)">AWS</text>
            </g>
            <g className="svg-badge-float b3">
                <rect x="310" y="160" width="64" height="26" rx="6" fill="rgba(59,126,248,0.08)" stroke="rgba(59,126,248,0.2)" strokeWidth="1" />
                <text x="342" y="177" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="700" fontFamily="var(--sans)">React</text>
            </g>
            <g className="svg-badge-float b4">
                <rect x="320" y="205" width="52" height="26" rx="6" fill="rgba(59,126,248,0.08)" stroke="rgba(59,126,248,0.2)" strokeWidth="1" />
                <text x="346" y="222" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="700" fontFamily="var(--sans)">SQL</text>
            </g>
            {/* Connector dashes */}
            <path d="M300 85 L310 85" stroke="#3b7ef8" strokeWidth="1" opacity="0.3" strokeDasharray="3 2" />
            <path d="M300 128 L316 128" stroke="#3b7ef8" strokeWidth="1" opacity="0.3" strokeDasharray="3 2" />
            <path d="M300 173 L310 173" stroke="#3b7ef8" strokeWidth="1" opacity="0.3" strokeDasharray="3 2" />
            <path d="M300 218 L320 218" stroke="#3b7ef8" strokeWidth="1" opacity="0.3" strokeDasharray="3 2" />
        </svg>
    );
}

// ─── Illustration 2: AI Scoring (Pure SVG) ────────────────────────────────────
function ScoreIllustration() {
    return (
        <svg viewBox="0 0 400 300" fill="none" className="feat-svg">
            {/* Card */}
            <rect x="40" y="25" width="320" height="250" rx="14" fill="#fff" stroke="#e2e5f0" strokeWidth="1.5" />
            {/* Avatar */}
            <circle cx="80" cy="65" r="18" fill="#eef0f7" stroke="#3b7ef8" strokeWidth="2" className="svg-avatar-pulse" />
            <rect x="108" y="56" width="90" height="8" rx="4" fill="#d5daea" />
            <rect x="108" y="70" width="55" height="6" rx="3" fill="#eef0f7" />
            {/* Score ring */}
            <circle cx="320" cy="65" r="28" fill="none" stroke="#eef0f7" strokeWidth="5" />
            <circle cx="320" cy="65" r="28" fill="none" stroke="url(#gaugeGrad)" strokeWidth="5"
                strokeDasharray="176" strokeDashoffset="10" strokeLinecap="round"
                transform="rotate(-90 320 65)" className="svg-gauge-animate" />
            <text x="320" y="70" textAnchor="middle" fill="#3b7ef8" fontSize="16" fontWeight="800" fontFamily="var(--sans)">94</text>
            <defs>
                <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#3b7ef8" />
                    <stop offset="100%" stopColor="#8b5cf6" />
                </linearGradient>
            </defs>
            {/* Divider */}
            <line x1="60" y1="105" x2="340" y2="105" stroke="#eef0f7" strokeWidth="1" />
            {/* Match bars */}
            <text x="68" y="138" fill="#9ca3af" fontSize="11" fontWeight="600" fontFamily="var(--sans)">Skills Match</text>
            <rect x="160" y="128" width="180" height="8" rx="4" fill="#eef0f7" />
            <rect x="160" y="128" width="0" height="8" rx="4" fill="url(#gaugeGrad)" className="svg-bar-grow bar1" />
            <text x="68" y="170" fill="#9ca3af" fontSize="11" fontWeight="600" fontFamily="var(--sans)">Experience</text>
            <rect x="160" y="160" width="180" height="8" rx="4" fill="#eef0f7" />
            <rect x="160" y="160" width="0" height="8" rx="4" fill="url(#gaugeGrad)" className="svg-bar-grow bar2" />
            <text x="68" y="202" fill="#9ca3af" fontSize="11" fontWeight="600" fontFamily="var(--sans)">Education</text>
            <rect x="160" y="192" width="180" height="8" rx="4" fill="#eef0f7" />
            <rect x="160" y="192" width="0" height="8" rx="4" fill="url(#gaugeGrad)" className="svg-bar-grow bar3" />
            {/* Status badge */}
            <rect x="60" y="230" width="120" height="28" rx="8" fill="rgba(16,185,129,0.08)" stroke="rgba(16,185,129,0.2)" strokeWidth="1" />
            <circle cx="78" cy="244" r="4" fill="#10b981" className="svg-status-blink" />
            <text x="90" y="248" fill="#10b981" fontSize="10" fontWeight="600" fontFamily="var(--sans)">Best Match</text>
        </svg>
    );
}

// ─── Illustration 3: Spark Processing (Pure SVG) ──────────────────────────────
function SparkIllustration() {
    return (
        <svg viewBox="0 0 400 300" fill="none" className="feat-svg">
            {/* Connection lines */}
            <line x1="200" y1="130" x2="80" y2="55" stroke="#e2e5f0" strokeWidth="1.5" strokeDasharray="5 4" className="svg-dash-flow d1" />
            <line x1="200" y1="130" x2="320" y2="55" stroke="#e2e5f0" strokeWidth="1.5" strokeDasharray="5 4" className="svg-dash-flow d2" />
            <line x1="200" y1="130" x2="80" y2="210" stroke="#e2e5f0" strokeWidth="1.5" strokeDasharray="5 4" className="svg-dash-flow d3" />
            <line x1="200" y1="130" x2="320" y2="210" stroke="#e2e5f0" strokeWidth="1.5" strokeDasharray="5 4" className="svg-dash-flow d4" />
            {/* Worker nodes */}
            <circle cx="80" cy="55" r="24" fill="#fff" stroke="#e2e5f0" strokeWidth="1.5" className="svg-node-glow n1" />
            <text x="80" y="52" textAnchor="middle" fill="#6b7280" fontSize="9" fontWeight="700" fontFamily="var(--sans)">Worker</text>
            <text x="80" y="64" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="800" fontFamily="var(--sans)">01</text>
            <circle cx="320" cy="55" r="24" fill="#fff" stroke="#e2e5f0" strokeWidth="1.5" className="svg-node-glow n2" />
            <text x="320" y="52" textAnchor="middle" fill="#6b7280" fontSize="9" fontWeight="700" fontFamily="var(--sans)">Worker</text>
            <text x="320" y="64" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="800" fontFamily="var(--sans)">02</text>
            <circle cx="80" cy="210" r="24" fill="#fff" stroke="#e2e5f0" strokeWidth="1.5" className="svg-node-glow n3" />
            <text x="80" y="207" textAnchor="middle" fill="#6b7280" fontSize="9" fontWeight="700" fontFamily="var(--sans)">Worker</text>
            <text x="80" y="219" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="800" fontFamily="var(--sans)">03</text>
            <circle cx="320" cy="210" r="24" fill="#fff" stroke="#e2e5f0" strokeWidth="1.5" className="svg-node-glow n4" />
            <text x="320" y="207" textAnchor="middle" fill="#6b7280" fontSize="9" fontWeight="700" fontFamily="var(--sans)">Worker</text>
            <text x="320" y="219" textAnchor="middle" fill="#3b7ef8" fontSize="11" fontWeight="800" fontFamily="var(--sans)">04</text>
            {/* Central Driver hub */}
            <circle cx="200" cy="130" r="32" fill="#fff" stroke="#3b7ef8" strokeWidth="2" />
            <circle cx="200" cy="130" r="38" fill="none" stroke="rgba(59,126,248,0.15)" strokeWidth="1.5" className="svg-hub-pulse" />
            <polygon points="204,116 194,132 201,132 196,146 206,128 199,128 204,116" fill="#3b7ef8" />
            {/* Status bar */}
            <rect x="120" y="262" width="160" height="28" rx="8" fill="rgba(16,185,129,0.06)" stroke="rgba(16,185,129,0.18)" strokeWidth="1" />
            <circle cx="140" cy="276" r="4" fill="#10b981" className="svg-status-blink" />
            <text x="152" y="280" fill="#10b981" fontSize="10" fontWeight="600" fontFamily="var(--sans)">Processing in parallel</text>
        </svg>
    );
}


// ─── Feature Row ──────────────────────────────────────────────────────────────
function FeatureRow({ tag, title, description, illustration, reverse }) {
    return (
        <div className={`feat-row ${reverse ? 'feat-row--reverse' : ''}`}>
            <div className="feat-blob-wrap">
                <div className="feat-blob">
                    {illustration}
                </div>
            </div>
            <div className="feat-text">
                <span className="feat-tag">{tag}</span>
                <h3 className="feat-title">{title}</h3>
                <p className="feat-desc">{description}</p>
            </div>
        </div>
    );
}

// ─── Hero Background Canvas (light mode optimized) ───────────────────────────
function ComposioCanvas() {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d', { alpha: false });
        let rafId;

        const setSize = () => {
            const { width, height } = canvas.parentElement.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            canvas.width = width * dpr;
            canvas.height = height * dpr;
            ctx.scale(dpr, dpr);
            canvas.style.width = width + 'px';
            canvas.style.height = height + 'px';
        };
        setSize();
        window.addEventListener('resize', setSize);

        class Band {
            constructor(w, h, side) {
                this.side = side;
                this.w = w;
                this.h = h;
                this.y = Math.random() * h;
                this.depth = Math.random();
                this.bandH = 8 + this.depth * 60;
                this.numBars = Math.floor(20 + this.depth * 40);
                this.extent = (0.15 + this.depth * 0.35) * w;
                this.phase = Math.random() * Math.PI * 2;
                this.speed = (0.3 + Math.random() * 0.7) * (Math.random() > 0.5 ? 1 : -1);
                this.drift = (0.5 + this.depth * 1.5) * (side === 'left' ? 1 : -1);
                const palettes = [
                    { r: 59, g: 126, b: 248 },
                    { r: 99, g: 102, b: 241 },
                    { r: 139, g: 92, b: 246 },
                    { r: 14,  g: 165, b: 233 },
                    { r: 52,  g: 211, b: 153 },
                    { r: 167, g: 139, b: 250 },
                ];
                this.color = palettes[Math.floor(Math.random() * palettes.length)];
                this.bars = [];
                for (let i = 0; i < this.numBars; i++) {
                    this.bars.push({
                        heightMul: 0.3 + Math.random() * 0.7,
                        brightnessOffset: Math.random() * 0.4,
                        flickerPhase: Math.random() * Math.PI * 2,
                        flickerSpeed: 2 + Math.random() * 6,
                    });
                }
                this.skewAngle = side === 'left' ? 0.15 + this.depth * 0.25 : -(0.15 + this.depth * 0.25);
            }

            draw(ctx, t) {
                const barW = Math.max(2, 3 + this.depth * 5);
                const gap = Math.max(1, 1 + this.depth * 2);
                const totalW = this.numBars * (barW + gap);
                const baseStartX = this.side === 'left' ? 0 : this.w - totalW;
                const xShift = (t * this.drift * 15) % (barW + gap);
                const yOff = Math.sin(t * this.speed + this.phase) * 10;
                const baseY = this.y + yOff;

                ctx.save();
                for (let i = -1; i < this.numBars + 1; i++) {
                    const bar = this.bars[Math.abs(i) % this.bars.length];
                    const x = baseStartX + i * (barW + gap) + xShift;
                    const distFromCenter = this.side === 'left'
                        ? 1 - (x / (this.w * 0.5))
                        : 1 - ((this.w - x) / (this.w * 0.5));
                    const edgeFade = Math.max(0, Math.min(1, distFromCenter * 1.3));
                    if (edgeFade < 0.01) continue;
                    const perspH = this.bandH * bar.heightMul * (0.5 + edgeFade * 0.5);
                    const flicker = (Math.sin(t * bar.flickerSpeed + bar.flickerPhase) + 1) / 2;
                    const brightness = 0.6 + bar.brightnessOffset + flicker * 0.3;
                    const r = Math.min(255, Math.floor(this.color.r * brightness));
                    const g = Math.min(255, Math.floor(this.color.g * brightness));
                    const b = Math.min(255, Math.floor(this.color.b * brightness));
                    const alpha = edgeFade * (0.12 + this.depth * 0.16) * (0.6 + flicker * 0.3);
                    ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
                    ctx.save();
                    ctx.translate(x + barW / 2, baseY);
                    ctx.transform(1, this.skewAngle * edgeFade, 0, 1, 0, 0);
                    ctx.fillRect(-barW / 2, -perspH / 2, barW, perspH);
                    ctx.restore();
                }
                ctx.restore();
            }
        }

        let bands = [];
        const init = () => {
            const w = canvas.width / (window.devicePixelRatio || 1);
            const h = canvas.height / (window.devicePixelRatio || 1);
            bands = [];
            for (let i = 0; i < 35; i++) {
                bands.push(new Band(w, h, 'left'));
                bands.push(new Band(w, h, 'right'));
            }
            bands.sort((a, b) => a.depth - b.depth);
        };
        init();

        const render = () => {
            const w = canvas.width / (window.devicePixelRatio || 1);
            const h = canvas.height / (window.devicePixelRatio || 1);

            // Light mode only
            ctx.fillStyle = '#f5f6fa';
            ctx.fillRect(0, 0, w, h);

            const t = Date.now() / 1000;
            for (const band of bands) {
                band.draw(ctx, t);
            }

            // Radial vignette (light mode — reduced center opacity for bar visibility)
            const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.55);
            grad.addColorStop(0,    'rgba(245,246,250,0.5)');
            grad.addColorStop(0.45, 'rgba(245,246,250,0.25)');
            grad.addColorStop(1,    'rgba(245,246,250,0)');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, w, h);

            // Edge fade
            const edgeGrad = ctx.createLinearGradient(0, 0, 0, h);
            edgeGrad.addColorStop(0,    'rgba(245,246,250,0.55)');
            edgeGrad.addColorStop(0.15, 'rgba(245,246,250,0)');
            edgeGrad.addColorStop(0.85, 'rgba(245,246,250,0)');
            edgeGrad.addColorStop(1,    'rgba(245,246,250,0.65)');
            ctx.fillStyle = edgeGrad;
            ctx.fillRect(0, 0, w, h);

            rafId = requestAnimationFrame(render);
        };
        rafId = requestAnimationFrame(render);

        return () => {
            cancelAnimationFrame(rafId);
            window.removeEventListener('resize', setSize);
        };
    }, []);

    return <canvas ref={canvasRef} className="lp-hero-bg" />;
}

// ─── Main Page ────────────────────────────────────────────────────────────────
function LandingPage() {
    const navigate = useNavigate();
    const [stats, setStats] = useState({ total: 0, avgScore: 0 });

    const statsRef  = useRef(null);
    const featRef   = useRef(null);
    const ctaRef    = useRef(null);
    const footerRef = useRef(null);

    // ── Data fetch from real MongoDB stats ──────────────────────
    useEffect(() => {
        axios.get(`${API_BASE_URL}/stats`).then(res => {
            setStats({
                total: res.data.total_candidates || 0,
                avgScore: res.data.avg_score || 0
            });
        }).catch(() => {});
    }, []);

    // ── GSAP Scroll Animations ───────────────────────────────────
    useEffect(() => {
        const ctx = gsap.context(() => {

            // Hero entrance
            const tl = gsap.timeline({ delay: 0.1 });
            tl.from('.lp-eyebrow',      { opacity: 0, y: 24, duration: 0.7, ease: 'power3.out' })
              .from('.lp-headline',     { opacity: 0, y: 44, duration: 0.85, ease: 'power3.out' }, '-=0.45')
              .from('.lp-subline',      { opacity: 0, y: 28, duration: 0.75, ease: 'power3.out' }, '-=0.5')
              .from('.lp-hero-actions', { opacity: 0, y: 20, duration: 0.65, ease: 'power3.out' }, '-=0.45');

            // Stats bar
            gsap.from('.lp-stat', {
                scrollTrigger: { trigger: statsRef.current, start: 'top 82%' },
                opacity: 0, y: 30, stagger: 0.14, duration: 0.8, ease: 'power3.out',
            });
            gsap.from('.lp-stat-divider', {
                scrollTrigger: { trigger: statsRef.current, start: 'top 82%' },
                scaleY: 0, duration: 0.6, stagger: 0.14, ease: 'power3.out',
            });

            // Features header
            gsap.from('.lp-features-header > *', {
                scrollTrigger: { trigger: featRef.current, start: 'top 80%' },
                opacity: 0, y: 32, stagger: 0.12, duration: 0.85, ease: 'power3.out',
            });

            // Feature row panels
            document.querySelectorAll('.feat-row').forEach((row) => {
                const isReverse = row.classList.contains('feat-row--reverse');
                const blob = row.querySelector('.feat-blob-wrap');
                const text = row.querySelector('.feat-text');
                if (blob) gsap.from(blob, {
                    scrollTrigger: { trigger: row, start: 'top 84%' },
                    opacity: 0, x: isReverse ? 70 : -70, duration: 0.9, ease: 'power3.out',
                });
                if (text) gsap.from(text, {
                    scrollTrigger: { trigger: row, start: 'top 84%' },
                    opacity: 0, x: isReverse ? -40 : 40, duration: 0.9, delay: 0.1, ease: 'power3.out',
                });
            });

            // CTA section
            gsap.from('.lp-cta-clean > *', {
                scrollTrigger: { trigger: ctaRef.current, start: 'top 80%' },
                opacity: 0, y: 28, stagger: 0.15, duration: 0.8, ease: 'power3.out',
            });

            // Footer
            gsap.from(['.lp-footer-brand', '.lp-link-col'], {
                scrollTrigger: { trigger: footerRef.current, start: 'top 92%' },
                opacity: 0, y: 16, stagger: 0.07, duration: 0.65, ease: 'power3.out',
            });
        });
        return () => ctx.revert();
    }, []);

    return (
        <div className="lp-root">

            {/* ── HERO ─────────────────────────────────────── */}
            <section className="lp-hero">
                <ComposioCanvas />
                <p className="lp-eyebrow">AI-Powered Recruitment</p>
                <h1 className="lp-headline">
                    Find the right talent,<br /><em>faster.</em>
                </h1>
                <p className="lp-subline">
                    HireFlow AI scores every resume in your pipeline automatically,<br />
                    so your team focuses on people, not paperwork.
                </p>
                <div className="lp-hero-actions">
                    <button className="lp-btn-primary" onClick={() => navigate('/dashboard')}>Launch Dashboard</button>
                    <button className="lp-btn-ghost"   onClick={() => document.getElementById('features').scrollIntoView({ behavior: 'smooth' })}>Learn More</button>
                </div>
            </section>

            {/* ── STATS ────────────────────────────────────── */}
            <section ref={statsRef} className="lp-stats-bar">
                <div className="lp-stat">
                    <span className="lp-stat-num">
                        {stats.total > 0 ? <AnimatedCounter end={stats.total} /> : '0'}
                    </span>
                    <span className="lp-stat-label">Candidates ranked last batch</span>
                </div>
                <div className="lp-stat-divider" />
                <div className="lp-stat">
                    <span className="lp-stat-num">
                        {stats.avgScore > 0 ? <><AnimatedCounter end={Math.round(stats.avgScore)} suffix="%" /></> : '0%'}
                    </span>
                    <span className="lp-stat-label">Average AI match score</span>
                </div>
                <div className="lp-stat-divider" />
                <div className="lp-stat">
                    <span className="lp-stat-num">8x</span>
                    <span className="lp-stat-label">Faster than manual review</span>
                </div>
            </section>

            {/* ── FEATURES ─────────────────────────────────── */}
            <section id="features" ref={featRef} className="lp-features">
                <div className="lp-features-header">
                    <span className="lp-section-tag">How it works</span>
                    <h2 className="lp-section-title">Three layers of intelligence,<br />working together.</h2>
                </div>
                <FeatureRow tag="Resume ingestion" title="Multimodal Resume Parsing"
                    description="Upload any format, PDF, DOCX, or a ZIP archive of hundreds. Our OCR pipeline reads scanned images and digital files equally well, extracting every structured data point automatically."
                    illustration={<ParseIllustration />} reverse={false} />
                <FeatureRow tag="AI Scoring Engine" title="JobBERT Semantic Matching"
                    description="Uses JobBERT to semantically chunk resumes and match them directly against the Job Description. Pure contextual understanding powered by MongoDB Vector Search."
                    illustration={<ScoreIllustration />} reverse={true} />
                <FeatureRow tag="Big Data Processing" title="Apache Spark Parallelization"
                    description="Handles high velocity and volume of input batches. PySpark parallelizes the chunking and embedding generation for hundreds of resumes instantly."
                    illustration={<SparkIllustration />} reverse={false} />
            </section>

            {/* ── CTA ──────────────────────────────────────── */}
            <section ref={ctaRef} className="lp-cta-clean">
                <h2 className="lp-cta-title">Give a white glove experience<br />to every candidate</h2>
                <button className="lp-btn-primary" onClick={() => navigate('/dashboard')}>
                    Start for free
                </button>
            </section>

            {/* ── FOOTER ───────────────────────────────────── */}
            <footer ref={footerRef} className="lp-footer">
                <div className="lp-footer-inner">
                    <div className="lp-footer-brand">
                        <span className="lp-footer-logo">hireflow</span>
                        <p>Built for HR teams that move fast.</p>
                    </div>
                    <div className="lp-footer-links">
                        <div className="lp-link-col">
                            <span>Product</span>
                            <a href="#">Features</a>
                            <a href="#">Dashboard</a>
                            <a href="#">Pricing</a>
                        </div>
                        <div className="lp-link-col">
                            <span>Company</span>
                            <a href="#">About</a>
                            <a href="#">Blog</a>
                            <a href="#">Careers</a>
                        </div>
                        <div className="lp-link-col">
                            <span>Legal</span>
                            <a href="#">Privacy</a>
                            <a href="#">Terms</a>
                        </div>
                    </div>
                </div>
                <div className="lp-footer-bottom">
                    <p>HireFlow AI 2026. All rights reserved.</p>
                </div>
            </footer>
        </div>
    );
}

export default LandingPage;
