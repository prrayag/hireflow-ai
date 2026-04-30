// LandingPage.jsx — HireFlow AI premium redesign
// Wave: two interweaving silk ribbons (blue + gold) with canvas
// Hands CTA: GSAP ScrollTrigger entrance animation

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import '../styles/landing.css';

gsap.registerPlugin(ScrollTrigger);

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

// ─── Composio Hero Background (3D Perspective Data Bars) ──────────────────────
// Renders thick vertical bar columns arranged in horizontal bands with strong
// 3D perspective, creating "data walls" that recede from the edges toward center.
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

        // Each Band is a horizontal row of vertical bar columns
        // positioned on the left or right side with 3D perspective
        class Band {
            constructor(w, h, side) {
                this.side = side; // 'left' or 'right'
                this.w = w;
                this.h = h;
                // Vertical position of the band
                this.y = Math.random() * h;
                // Depth (0 = far, 1 = close) affects size and brightness
                this.depth = Math.random();
                // Band thickness (height of individual bars)
                this.bandH = 8 + this.depth * 60;
                // Number of vertical bar columns in this band
                this.numBars = Math.floor(20 + this.depth * 40);
                // Horizontal extent from the edge
                this.extent = (0.15 + this.depth * 0.35) * w;
                // Animation phase offset
                this.phase = Math.random() * Math.PI * 2;
                this.speed = (0.3 + Math.random() * 0.7) * (Math.random() > 0.5 ? 1 : -1);
                // Color: blues, cyans, greens, purples
                const palettes = [
                    { r: 30, g: 90, b: 220 },   // Deep blue
                    { r: 50, g: 160, b: 240 },   // Bright blue
                    { r: 0,  g: 200, b: 200 },   // Cyan
                    { r: 30, g: 200, b: 120 },   // Green-cyan
                    { r: 100, g: 60, b: 220 },   // Purple
                    { r: 60, g: 130, b: 255 },   // Sky blue
                ];
                this.color = palettes[Math.floor(Math.random() * palettes.length)];
                // Per-bar randomization
                this.bars = [];
                for (let i = 0; i < this.numBars; i++) {
                    this.bars.push({
                        heightMul: 0.3 + Math.random() * 0.7,
                        brightnessOffset: Math.random() * 0.4,
                        flickerPhase: Math.random() * Math.PI * 2,
                        flickerSpeed: 2 + Math.random() * 6,
                    });
                }
                // Perspective skew angle (bars tilt toward vanishing point)
                this.skewAngle = side === 'left' ? 0.15 + this.depth * 0.25 : -(0.15 + this.depth * 0.25);
            }

            draw(ctx, t) {
                const barW = Math.max(2, 3 + this.depth * 5);
                const gap = Math.max(1, 1 + this.depth * 2);
                const totalW = this.numBars * (barW + gap);

                // Starting x position from the edge
                const startX = this.side === 'left' ? 0 : this.w - totalW;

                // Animated vertical offset (slow drift)
                const yOff = Math.sin(t * this.speed + this.phase) * 8;
                const baseY = this.y + yOff;

                // Fade based on distance from center (bars near edges are brighter)
                ctx.save();

                for (let i = 0; i < this.numBars; i++) {
                    const bar = this.bars[i];
                    const x = startX + i * (barW + gap);

                    // How far this bar is from the canvas center (0-1 range)
                    const distFromCenter = this.side === 'left'
                        ? 1 - (x / (this.w * 0.5))
                        : 1 - ((this.w - x) / (this.w * 0.5));
                    
                    // Fade bar opacity as it approaches center
                    const edgeFade = Math.max(0, Math.min(1, distFromCenter * 1.3));
                    if (edgeFade < 0.01) continue;

                    // Perspective: bars get taller near the edge
                    const perspH = this.bandH * bar.heightMul * (0.5 + edgeFade * 0.5);

                    // Flicker (glitch effect)
                    const flicker = (Math.sin(t * bar.flickerSpeed + bar.flickerPhase) + 1) / 2;
                    const brightness = 0.5 + bar.brightnessOffset + flicker * 0.3;

                    const r = Math.min(255, Math.floor(this.color.r * brightness));
                    const g = Math.min(255, Math.floor(this.color.g * brightness));
                    const b = Math.min(255, Math.floor(this.color.b * brightness));

                    const alpha = edgeFade * (0.2 + this.depth * 0.3) * (0.6 + flicker * 0.4);

                    ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;

                    // Apply perspective skew via transform
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
            // Create bands on both sides at various depths and y positions
            for (let i = 0; i < 35; i++) {
                bands.push(new Band(w, h, 'left'));
                bands.push(new Band(w, h, 'right'));
            }
            // Sort by depth so far bands draw first (painter's algorithm)
            bands.sort((a, b) => a.depth - b.depth);
        };
        init();

        const render = () => {
            const w = canvas.width / (window.devicePixelRatio || 1);
            const h = canvas.height / (window.devicePixelRatio || 1);

            // Dark background
            ctx.fillStyle = '#0a0a0a';
            ctx.fillRect(0, 0, w, h);

            const t = Date.now() / 1000;

            for (const band of bands) {
                band.draw(ctx, t);
            }

            // Radial vignette to darken center for text legibility
            const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.55);
            grad.addColorStop(0, 'rgba(10,10,10,0.92)');
            grad.addColorStop(0.45, 'rgba(10,10,10,0.65)');
            grad.addColorStop(1, 'rgba(10,10,10,0)');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, w, h);

            // Subtle top/bottom edge vignette
            const edgeGrad = ctx.createLinearGradient(0, 0, 0, h);
            edgeGrad.addColorStop(0, 'rgba(10,10,10,0.5)');
            edgeGrad.addColorStop(0.15, 'rgba(10,10,10,0)');
            edgeGrad.addColorStop(0.85, 'rgba(10,10,10,0)');
            edgeGrad.addColorStop(1, 'rgba(10,10,10,0.6)');
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

// \u2500\u2500\u2500 Main Page (GSAP animated) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
function LandingPage() {
    const navigate = useNavigate();
    const [stats, setStats] = useState({ total: '—', avgScore: '—' });

    const statsRef  = useRef(null);
    const featRef   = useRef(null);
    const ctaRef    = useRef(null);
    const footerRef = useRef(null);

    // ── Data fetch ──────────────────────────────────────────────
    useEffect(() => {
        axios.get(`${API_BASE_URL}/results`).then(res => {
            const c = res.data.candidates || [];
            if (c.length > 0) {
                const avg = (c.reduce((s, x) => s + x.score, 0) / c.length).toFixed(1);
                setStats({ total: c.length, avgScore: avg });
            }
        }).catch(() => {});
    }, []);

    // ── GSAP Scroll Animations ───────────────────────────────────
    useEffect(() => {
        const ctx = gsap.context(() => {

            // Hero entrance — staggered lift
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

            // Feature row panels — alternate left/right
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

    // Illustrations
    const parseIllustration = (
        <div className="ui-mockup mockup-parse">
            <div className="mockup-file">
                <div className="mockup-file-header">
                    <div className="mockup-point" /><div className="mockup-point" /><div className="mockup-point" />
                </div>
                <div className="mockup-line w-full" />
                <div className="mockup-line w-3-4" />
                <div className="mockup-line w-1-2" />
            </div>
            <div className="mockup-scanner" />
        </div>
    );

    const scoreIllustration = (
        <div className="ui-mockup mockup-score">
            <div className="mockup-candidate">
                <div className="mockup-avatar" />
                <div className="mockup-info">
                    <div className="mockup-name" /><div className="mockup-role" />
                </div>
                <div className="mockup-badge">94.5</div>
            </div>
        </div>
    );

    const anomalyIllustration = (
        <div className="ui-mockup mockup-anomaly">
            <div className="mockup-bg-lines">
                <div className="mockup-line w-full" />
                <div className="mockup-line w-full op-20" />
                <div className="mockup-line w-3-4 op-20" />
            </div>
            <div className="mockup-alert">
                <div className="mockup-alert-dot" />
                <div className="mockup-alert-text">Keyword stuffing detected</div>
            </div>
        </div>
    );

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
                    <button className="lp-btn-primary" onClick={() => navigate('/upload')}>Get started</button>
                    <button className="lp-btn-ghost"   onClick={() => navigate('/dashboard')}>View demo →</button>
                </div>
            </section>

            {/* ── STATS ────────────────────────────────────── */}
            <section ref={statsRef} className="lp-stats-bar">
                <div className="lp-stat">
                    <span className="lp-stat-num">{stats.total}</span>
                    <span className="lp-stat-label">Candidates ranked last batch</span>
                </div>
                <div className="lp-stat-divider" />
                <div className="lp-stat">
                    <span className="lp-stat-num">{stats.avgScore}%</span>
                    <span className="lp-stat-label">Average AI match score</span>
                </div>
                <div className="lp-stat-divider" />
                <div className="lp-stat">
                    <span className="lp-stat-num">8×</span>
                    <span className="lp-stat-label">Faster than manual review</span>
                </div>
            </section>

            {/* ── FEATURES ─────────────────────────────────── */}
            <section ref={featRef} className="lp-features">
                <div className="lp-features-header">
                    <span className="lp-section-tag">How it works</span>
                    <h2 className="lp-section-title">Three layers of intelligence,<br />working together.</h2>
                </div>
                <FeatureRow tag="Resume ingestion" title="Multimodal Resume Parsing"
                    description="Upload any format, PDF, DOCX, or a ZIP archive of hundreds. Our OCR pipeline reads scanned images and digital files equally well, extracting every structured data point automatically."
                    illustration={parseIllustration} reverse={false} />
                <FeatureRow tag="AI scoring engine" title="Smart Candidate Scoring"
                    description="A Random Forest model trained on real resumes scores each candidate 0–100% against your job description using Sentence-BERT semantic matching, not just keyword counting."
                    illustration={scoreIllustration} reverse={true} />
                <FeatureRow tag="Fraud detection" title="Anomaly Detection"
                    description="Our Isolation Forest flags keyword-stuffed, auto-generated, or suspicious resumes before they reach your shortlist, so your team only reviews genuine candidates."
                    illustration={anomalyIllustration} reverse={false} />
            </section>

            {/* ── CTA ──────────────────────────────────────── */}
            <section ref={ctaRef} className="lp-cta-clean">
                <h2 className="lp-cta-title">Give a white glove experience<br />to every candidate</h2>
                <button className="lp-btn-primary" onClick={() => navigate('/upload')}>
                    Start for free →
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
                    <p>HireFlow AI © 2026. All rights reserved.</p>
                </div>
            </footer>
        </div>
    );
}

export default LandingPage;



