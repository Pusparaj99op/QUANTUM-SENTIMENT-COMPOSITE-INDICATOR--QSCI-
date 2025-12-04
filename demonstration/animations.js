/**
 * QSCI - Quantum Sentiment Composite Indicator
 * Advanced GSAP Animations with Click-to-Expand Modals
 */

// Register GSAP Plugins
gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);

// ============================================
// MODAL CONTENT DATA
// ============================================
const modalData = {
    // Hero Stats
    'indicators': {
        icon: '📊',
        title: '15+ Technical Indicators',
        content: `
            <h3>Momentum Indicators (35% weight)</h3>
            <ul>
                <li><strong>RSI (Relative Strength Index)</strong> - Momentum oscillator measuring speed of price changes</li>
                <li><strong>Stochastic RSI</strong> - RSI applied to RSI values for faster signals</li>
                <li><strong>Williams %R</strong> - Momentum indicator showing overbought/oversold levels</li>
                <li><strong>MFI (Money Flow Index)</strong> - Volume-weighted RSI variant</li>
                <li><strong>CCI (Commodity Channel Index)</strong> - Deviation from statistical mean</li>
                <li><strong>Ultimate Oscillator</strong> - Multi-timeframe momentum</li>
            </ul>
            <h3>Trend Indicators (30% weight)</h3>
            <ul>
                <li><strong>MACD</strong> - Moving Average Convergence Divergence</li>
                <li><strong>ADX + DI</strong> - Average Directional Index with directional indicators</li>
                <li><strong>EMA Crossover</strong> - 20/50 period exponential moving average cross</li>
                <li><strong>Aroon</strong> - Trend identification and strength</li>
                <li><strong>Ichimoku Cloud</strong> - Multi-component trend system</li>
            </ul>
            <h3>Volume Indicators (15% weight)</h3>
            <ul>
                <li><strong>OBV</strong> - On-Balance Volume</li>
                <li><strong>CMF</strong> - Chaikin Money Flow</li>
                <li><strong>VWAP</strong> - Volume Weighted Average Price</li>
            </ul>
            <h3>Volatility Indicators (10% weight)</h3>
            <ul>
                <li><strong>Bollinger Bands</strong> - Price channels based on standard deviation</li>
                <li><strong>Keltner Channel</strong> - ATR-based price channels</li>
            </ul>
        `
    },
    'timeframes': {
        icon: '⏱️',
        title: '7 Timeframe Analysis',
        content: `
            <h3>Multi-Timeframe Composite (MTC)</h3>
            <p>QSCI analyzes 7 different timeframes simultaneously, with higher timeframes carrying more weight for robust signals:</p>
            <div class="formula-highlight">MTC = Σ(αᵢ × TFᵢ)</div>
            <h3>Timeframe Weights</h3>
            <ul>
                <li><strong>4H (α = 0.25)</strong> - Primary trend direction, highest weight</li>
                <li><strong>2H (α = 0.20)</strong> - Trend confirmation</li>
                <li><strong>1H (α = 0.15)</strong> - Intraday structure</li>
                <li><strong>30M (α = 0.15)</strong> - Short-term momentum</li>
                <li><strong>15M (α = 0.10)</strong> - Entry refinement</li>
                <li><strong>5M (α = 0.10)</strong> - Precision timing</li>
                <li><strong>1M (α = 0.05)</strong> - Micro-momentum</li>
            </ul>
            <h3>Why Multiple Timeframes?</h3>
            <p>Higher timeframes filter noise and reduce false signals. Lower timeframes provide precise entry timing. The weighted combination creates a robust signal that respects the dominant trend while allowing for timely entries.</p>
        `
    },
    'categories': {
        icon: '📁',
        title: '5 Signal Categories',
        content: `
            <h3>Each Timeframe Signal Composition</h3>
            <div class="formula-highlight">TFᵢ = 0.35M + 0.30T + 0.15V + 0.10σ + 0.10P</div>
            <h3>Categories Explained</h3>
            <ul>
                <li><strong>Momentum (M) - 35%</strong><br>RSI, StochRSI, Williams %R, MFI, CCI, Ultimate Oscillator. Captures buying/selling pressure and reversal potential.</li>
                <li><strong>Trend (T) - 30%</strong><br>MACD, ADX, EMA Cross, Aroon. Identifies direction and strength of price movement.</li>
                <li><strong>Volume (V) - 15%</strong><br>OBV, CMF, VWAP. Confirms price moves with volume conviction.</li>
                <li><strong>Volatility (σ) - 10%</strong><br>Bollinger Bands, Keltner Channel. Mean reversion signals and volatility context.</li>
                <li><strong>Pattern (P) - 10%</strong><br>Higher Highs/Lows analysis, trend structure. Market structure confirmation.</li>
            </ul>
        `
    },
    'equations': {
        icon: '🧮',
        title: '12 Core Equations',
        content: `
            <h3>Master QSCI Formula</h3>
            <div class="formula-highlight">QSCI = ω × MTC + (1 - ω) × NS × V_adj × Θ_weight</div>
            <h3>Core Components</h3>
            <ul>
                <li><strong>MTC</strong> - Multi-Timeframe Composite from 7 timeframes</li>
                <li><strong>NS</strong> - News Sentiment from NLP analysis</li>
                <li><strong>V_adj</strong> - Volatility adjustment (IV/HV ratio)</li>
                <li><strong>Θ_weight</strong> - Theta decay weight for options</li>
                <li><strong>ω = 0.70</strong> - Technical vs Sentiment balance</li>
            </ul>
            <h3>Normalization Strategy</h3>
            <p>All indicators are normalized to [-1, 1] range:</p>
            <ul>
                <li><code>tanh()</code> for unbounded values (MACD, CCI)</li>
                <li>Linear scaling for bounded values (RSI, Stochastic)</li>
                <li>ATR-relative scaling for price-based metrics</li>
            </ul>
        `
    },

    // Formula Breakdowns
    'qsci-detail': {
        icon: '✨',
        title: 'QSCI Master Formula Explained',
        content: `
            <div class="formula-highlight">QSCI = ω × MTC + (1 - ω) × NS × V_adj × Θ_weight</div>
            <h3>Component Breakdown</h3>
            <ul>
                <li><strong>ω (omega) = 0.70</strong><br>Technical weight. 70% of signal comes from technical analysis.</li>
                <li><strong>MTC (Multi-Timeframe Composite)</strong><br>Aggregated signal from all 7 timeframes and 15+ indicators.</li>
                <li><strong>(1 - ω) = 0.30</strong><br>Sentiment & Greeks weight. 30% from news and options data.</li>
                <li><strong>NS (News Sentiment)</strong><br>NLP-derived sentiment from crypto news sources.</li>
                <li><strong>V_adj (Volatility Adjustment)</strong><br>Ratio of implied to historical volatility, scaled by time to expiry.</li>
                <li><strong>Θ_weight (Theta Weight)</strong><br>Adjusts for options time decay based on DTE and moneyness.</li>
            </ul>
            <h3>Agreement Boost</h3>
            <p>When technical and sentiment agree (same sign), an additional boost is applied:</p>
            <div class="formula-highlight">if(MTC × NS > 0): QSCI += sign(MTC) × 0.1 × min(|MTC|, |NS|)</div>
            <p>This rewards convergence of signals for higher conviction trades.</p>
        `
    },
    'mtc-detail': {
        icon: '📊',
        title: 'Multi-Timeframe Composite (MTC)',
        content: `
            <div class="formula-highlight">MTC = Σ(αᵢ × TFᵢ) = 0.25×TF_4h + 0.20×TF_2h + ... + 0.05×TF_1m</div>
            <h3>Timeframe Weights (αᵢ)</h3>
            <ul>
                <li><strong>4H: α = 0.25</strong> - Primary trend, highest influence</li>
                <li><strong>2H: α = 0.20</strong> - Trend confirmation</li>
                <li><strong>1H: α = 0.15</strong> - Intraday structure</li>
                <li><strong>30M: α = 0.15</strong> - Short momentum</li>
                <li><strong>15M: α = 0.10</strong> - Entry timing</li>
                <li><strong>5M: α = 0.10</strong> - Precision</li>
                <li><strong>1M: α = 0.05</strong> - Micro-momentum</li>
            </ul>
            <h3>Why This Weighting?</h3>
            <p>Higher timeframes (4H, 2H) carry 45% total weight because:</p>
            <ul>
                <li>Less noise and false signals</li>
                <li>Better representation of true market sentiment</li>
                <li>Options trades benefit from trend alignment</li>
            </ul>
            <h3>Output Range</h3>
            <p>MTC outputs a value between -1 (strongly bearish) and +1 (strongly bullish).</p>
        `
    },
    'tf-detail': {
        icon: '📈',
        title: 'Timeframe Signal (TFᵢ)',
        content: `
            <div class="formula-highlight">TFᵢ = 0.35M + 0.30T + 0.15V + 0.10σ + 0.10P</div>
            <h3>Category Weights</h3>
            <ul>
                <li><strong>Momentum (M) = 35%</strong><br>RSI, StochRSI, Williams %R, MFI, CCI, Ultimate Oscillator</li>
                <li><strong>Trend (T) = 30%</strong><br>MACD, ADX+DI, EMA Cross, Aroon, Ichimoku</li>
                <li><strong>Volume (V) = 15%</strong><br>OBV, CMF, VWAP</li>
                <li><strong>Volatility (σ) = 10%</strong><br>Bollinger Bands, Keltner Channel</li>
                <li><strong>Pattern (P) = 10%</strong><br>HH/HL/LH/LL analysis</li>
            </ul>
            <h3>Sub-Composites</h3>
            <p>Each category is itself a weighted average:</p>
            <div class="formula-highlight">M = 0.25×RSI + 0.20×StochRSI + 0.15×WillR + 0.15×MFI + 0.15×CCI + 0.10×UO</div>
        `
    },
    'ns-detail': {
        icon: '📰',
        title: 'News Sentiment (NS)',
        content: `
            <div class="formula-highlight">NS = Σ(wₛ × e^(-λt) × S_nlp)</div>
            <h3>Components</h3>
            <ul>
                <li><strong>wₛ (Source Weight)</strong><br>Credibility weight for each news source</li>
                <li><strong>e^(-λt) (Time Decay)</strong><br>Exponential decay, λ = 0.1/hour. Recent news matters more.</li>
                <li><strong>S_nlp (NLP Sentiment)</strong><br>VADER compound score + TextBlob polarity</li>
            </ul>
            <h3>NLP Pipeline</h3>
            <ul>
                <li>Fetch crypto news from multiple sources</li>
                <li>Clean and preprocess text</li>
                <li>Run VADER sentiment analysis</li>
                <li>Fallback to TextBlob if needed</li>
                <li>Apply time decay weighting</li>
                <li>Aggregate to single [-1, 1] score</li>
            </ul>
            <h3>Source Weights Example</h3>
            <p>Bloomberg: 1.0, CoinDesk: 0.9, Twitter: 0.5, etc.</p>
        `
    },
    'vadj-detail': {
        icon: '🌊',
        title: 'Volatility Adjustment (V_adj)',
        content: `
            <div class="formula-highlight">V_adj = (σ_impl / σ_hist) × √(DTE/30)</div>
            <h3>Components</h3>
            <ul>
                <li><strong>σ_impl</strong> - Implied Volatility from options market</li>
                <li><strong>σ_hist</strong> - Historical Volatility (20-day realized)</li>
                <li><strong>DTE</strong> - Days To Expiration</li>
            </ul>
            <h3>Interpretation</h3>
            <ul>
                <li><strong>V_adj > 1</strong>: Options are expensive (IV > HV), reduce position size</li>
                <li><strong>V_adj < 1</strong>: Options are cheap (IV < HV), increase position size</li>
                <li><strong>√(DTE/30)</strong>: Square root time scaling for option value</li>
            </ul>
            <h3>Why This Matters</h3>
            <p>Options with high IV relative to HV may underperform. This adjustment helps scale exposure based on volatility premium.</p>
        `
    },
    'theta-detail': {
        icon: 'Θ',
        title: 'Theta Decay Weight (Θ_weight)',
        content: `
            <div class="formula-highlight">Θ_weight = 1 - (1/DTE) × |K-S|/S × M_f</div>
            <h3>Components</h3>
            <ul>
                <li><strong>DTE</strong> - Days To Expiration</li>
                <li><strong>K</strong> - Strike Price</li>
                <li><strong>S</strong> - Current Spot Price</li>
                <li><strong>M_f</strong> - Moneyness Factor (OTM penalty multiplier)</li>
            </ul>
            <h3>Purpose</h3>
            <p>This weight penalizes trades where theta decay is a significant factor:</p>
            <ul>
                <li>Low DTE options decay faster → lower weight</li>
                <li>Far OTM options need larger moves → lower weight</li>
                <li>ATM options with high DTE → higher weight (closer to 1)</li>
            </ul>
            <h3>Auto-Rolling</h3>
            <p>When DTE ≤ 7, the backtester automatically rolls positions to avoid accelerated decay.</p>
        `
    },

    // Individual Indicator Details
    'rsi-detail': {
        icon: '📊',
        title: 'RSI Signal Calculation',
        content: `
            <h3>Base RSI Formula</h3>
            <div class="formula-highlight">RSI = 100 - 100/(1 + RS)</div>
            <p>Where RS = Average Gain / Average Loss over 14 periods</p>
            <h3>QSCI Signal Normalization</h3>
            <div class="formula-highlight">RSI_signal = (RSI - 50) / 50</div>
            <h3>Output Mapping</h3>
            <ul>
                <li><strong>RSI = 70 → Signal = +0.40</strong> (Overbought, but bullish)</li>
                <li><strong>RSI = 50 → Signal = 0.00</strong> (Neutral)</li>
                <li><strong>RSI = 30 → Signal = -0.40</strong> (Oversold, but bearish)</li>
            </ul>
            <h3>Weight in Momentum</h3>
            <p>RSI carries 25% weight in the Momentum composite.</p>
        `
    },
    'macd-detail': {
        icon: '📈',
        title: 'MACD Signal Calculation',
        content: `
            <h3>Base MACD Formula</h3>
            <div class="formula-highlight">MACD Line = EMA(12) - EMA(26)</div>
            <div class="formula-highlight">Signal Line = EMA(MACD, 9)</div>
            <h3>QSCI Normalization</h3>
            <div class="formula-highlight">MACD_norm = tanh((MACD - Signal) / ATR × 2)</div>
            <h3>Why ATR Normalization?</h3>
            <p>MACD values vary with price level. A $100 stock might have MACD of 2, while BTC might have MACD of 500. ATR normalization makes it comparable:</p>
            <ul>
                <li>Dividing by ATR scales to recent volatility</li>
                <li>tanh() bounds output to [-1, 1]</li>
                <li>Multiplier of 2 adjusts sensitivity</li>
            </ul>
            <h3>Weight in Trend</h3>
            <p>MACD carries 30% weight in the Trend composite.</p>
        `
    },

    // Greek Details
    'delta-detail': {
        icon: 'Δ',
        title: 'Delta (Δ) - Price Sensitivity',
        content: `
            <h3>Delta Formula</h3>
            <div class="formula-highlight">Δ = ∂V/∂S = N(d₁)</div>
            <h3>d₁ Calculation</h3>
            <div class="formula-highlight">d₁ = [ln(S/K) + (r + σ²/2)T] / (σ√T)</div>
            <h3>What Delta Tells Us</h3>
            <ul>
                <li><strong>Call Delta: 0 to 1</strong> - How much option price changes per $1 spot move</li>
                <li><strong>Put Delta: -1 to 0</strong> - Negative for puts</li>
                <li><strong>ATM Options: Δ ≈ 0.50</strong></li>
                <li><strong>Deep ITM: Δ → 1.00</strong></li>
                <li><strong>Deep OTM: Δ → 0.00</strong></li>
            </ul>
            <h3>Use in QSCI</h3>
            <p>Delta helps determine position sizing and hedging requirements. Higher delta options are preferred for directional trades.</p>
        `
    },
    'theta-greek-detail': {
        icon: 'Θ',
        title: 'Theta (Θ) - Time Decay',
        content: `
            <h3>Theta Formula</h3>
            <div class="formula-highlight">Θ = -∂V/∂T = -(S×N'(d₁)×σ)/(2√T) - r×K×e^(-rT)×N(d₂)</div>
            <h3>Key Points</h3>
            <ul>
                <li><strong>Always Negative for Long Options</strong> - Time decay hurts option buyers</li>
                <li><strong>Accelerates Near Expiry</strong> - Theta increases as DTE decreases</li>
                <li><strong>Highest for ATM Options</strong> - ATM options have most time value</li>
            </ul>
            <h3>Daily Decay Example</h3>
            <p>If Θ = -$5, the option loses $5 per day from time decay alone.</p>
            <h3>Use in QSCI</h3>
            <p>The Θ_weight factor adjusts signal strength based on time decay impact. Low DTE positions get reduced weight to avoid theta bleed.</p>
        `
    },

    // Performance Details
    'winrate-detail': {
        icon: '🎯',
        title: 'Win Rate Analysis',
        content: `
            <h3>Win Rate Calculation</h3>
            <div class="formula-highlight">Win Rate = Profitable Trades / Total Trades × 100%</div>
            <h3>QSCI Target</h3>
            <ul>
                <li><strong>Target: 60-70%</strong> - Achievable with proper signal filtering</li>
                <li><strong>Minimum Viable: 55%</strong> - With proper risk management</li>
            </ul>
            <h3>Why Win Rate Isn't Everything</h3>
            <p>A 50% win rate can still be profitable if:</p>
            <ul>
                <li>Average win > Average loss (Profit Factor > 1)</li>
                <li>Proper position sizing limits losses</li>
                <li>Letting winners run, cutting losers quickly</li>
            </ul>
            <h3>QSCI Enhancements</h3>
            <ul>
                <li>Multi-timeframe confirmation reduces false signals</li>
                <li>Sentiment agreement boosts high-conviction trades</li>
                <li>Greeks adjustment avoids theta traps</li>
            </ul>
        `
    },
    'sharpe-detail': {
        icon: '📈',
        title: 'Sharpe Ratio',
        content: `
            <h3>Sharpe Ratio Formula</h3>
            <div class="formula-highlight">Sharpe = (R_p - R_f) / σ_p</div>
            <h3>Components</h3>
            <ul>
                <li><strong>R_p</strong> - Portfolio return (annualized)</li>
                <li><strong>R_f</strong> - Risk-free rate (typically 3-5%)</li>
                <li><strong>σ_p</strong> - Portfolio standard deviation (volatility)</li>
            </ul>
            <h3>Interpretation</h3>
            <ul>
                <li><strong>Sharpe < 0</strong> - Underperforming risk-free rate</li>
                <li><strong>Sharpe 0-1</strong> - Suboptimal risk-adjusted returns</li>
                <li><strong>Sharpe 1-2</strong> - Good risk-adjusted returns</li>
                <li><strong>Sharpe > 2</strong> - Excellent (often unsustainable)</li>
            </ul>
            <h3>QSCI Target</h3>
            <p>Target Sharpe: 1.5-2.0. The multi-timeframe approach reduces volatility while maintaining returns.</p>
        `
    },
    'drawdown-detail': {
        icon: '📉',
        title: 'Maximum Drawdown',
        content: `
            <h3>Drawdown Calculation</h3>
            <div class="formula-highlight">Drawdown = (Peak - Trough) / Peak × 100%</div>
            <h3>Max Drawdown</h3>
            <p>The largest peak-to-trough decline during the backtest period.</p>
            <h3>Risk Management</h3>
            <ul>
                <li><strong>Target: < 15%</strong> - Acceptable for options trading</li>
                <li><strong>Stop-Loss: 20%</strong> - Circuit breaker level</li>
            </ul>
            <h3>QSCI Drawdown Controls</h3>
            <ul>
                <li>Position sizing based on Kelly Criterion</li>
                <li>Dynamic stop-losses (2× ATR)</li>
                <li>Max position limits (no single trade > 5% of capital)</li>
                <li>Drawdown tracking with alerts</li>
            </ul>
        `
    },
    'profit-detail': {
        icon: '💰',
        title: 'Profit Factor',
        content: `
            <h3>Profit Factor Formula</h3>
            <div class="formula-highlight">Profit Factor = Gross Profit / Gross Loss</div>
            <h3>Interpretation</h3>
            <ul>
                <li><strong>PF < 1</strong> - Losing strategy</li>
                <li><strong>PF = 1</strong> - Break-even</li>
                <li><strong>PF 1-1.5</strong> - Marginal profitability</li>
                <li><strong>PF 1.5-2</strong> - Good profitability</li>
                <li><strong>PF > 2</strong> - Excellent (may be overfit)</li>
            </ul>
            <h3>QSCI Target</h3>
            <p>Target Profit Factor: 1.8-2.2. This indicates winners are significantly larger than losers on average.</p>
            <h3>Calculation Example</h3>
            <p>If 100 trades generate $150,000 in gross profit and $75,000 in gross loss:</p>
            <div class="formula-highlight">PF = $150,000 / $75,000 = 2.0</div>
        `
    }
};

// ============================================
// MODAL FUNCTIONALITY
// ============================================
const modal = document.getElementById('modal');
const modalClose = document.getElementById('modal-close');
const modalIcon = modal.querySelector('.modal-icon');
const modalTitle = modal.querySelector('.modal-title');
const modalBody = modal.querySelector('.modal-body');

function openModal(dataKey) {
    const data = modalData[dataKey];
    if (!data) return;

    modalIcon.textContent = data.icon;
    modalTitle.textContent = data.title;
    modalBody.innerHTML = data.content;

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    // GSAP animation
    gsap.fromTo('.modal-content',
        { scale: 0.9, y: 30, opacity: 0 },
        { scale: 1, y: 0, opacity: 1, duration: 0.4, ease: 'back.out(1.5)' }
    );
}

function closeModal() {
    gsap.to('.modal-content', {
        scale: 0.9,
        y: 30,
        opacity: 0,
        duration: 0.3,
        ease: 'power2.in',
        onComplete: () => {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    });
}

modalClose.addEventListener('click', closeModal);
modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

// Click handlers for expandable elements
document.querySelectorAll('[data-expand]').forEach(el => {
    el.addEventListener('click', () => {
        openModal(el.dataset.expand);
    });
});

document.querySelectorAll('[data-info]').forEach(el => {
    el.addEventListener('click', () => {
        openModal(el.dataset.info);
    });
});

// ============================================
// CURSOR GLOW EFFECT
// ============================================
const cursorGlow = document.querySelector('.cursor-glow');

document.addEventListener('mousemove', (e) => {
    gsap.to(cursorGlow, {
        x: e.clientX,
        y: e.clientY,
        duration: 0.5,
        ease: 'power2.out'
    });
});

document.addEventListener('mouseleave', () => {
    gsap.to(cursorGlow, { opacity: 0, duration: 0.3 });
});

document.addEventListener('mouseenter', () => {
    gsap.to(cursorGlow, { opacity: 1, duration: 0.3 });
});

// ============================================
// PARTICLES
// ============================================
function createParticles() {
    const container = document.getElementById('particles');
    if (!container) return;

    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 5 + 's';
        container.appendChild(particle);

        gsap.to(particle, {
            y: -window.innerHeight,
            x: 'random(-100, 100)',
            opacity: 0,
            duration: 'random(10, 20)',
            repeat: -1,
            delay: Math.random() * 5
        });
    }
}

createParticles();

// ============================================
// SCROLL ANIMATIONS
// ============================================

// Navbar scroll effect
ScrollTrigger.create({
    start: 'top -100',
    onUpdate: (self) => {
        if (self.direction === 1) {
            gsap.to('.navbar', { y: 0, duration: 0.3 });
        }
    }
});

// Hero animations - using set to ensure visibility first
gsap.set(['.hero-badge', '.title-line', '.hero-subtitle', '.stat-item', '.hero-cta', '.scroll-indicator'], { opacity: 1, visibility: 'visible' });

const heroTl = gsap.timeline();
heroTl.from('.hero-badge', { y: 30, opacity: 0, duration: 0.8 })
      .from('.title-line', { y: 50, opacity: 0, duration: 0.8, stagger: 0.15 }, '-=0.4')
      .from('.hero-subtitle', { y: 30, opacity: 0, duration: 0.8 }, '-=0.4')
      .from('.stat-item', { y: 40, opacity: 0, duration: 0.6, stagger: 0.1 }, '-=0.4')
      .from('.hero-cta', { y: 30, opacity: 0, duration: 0.6 }, '-=0.3')
      .from('.scroll-indicator', { y: 20, opacity: 0, duration: 0.6 }, '-=0.2');

// Stat number counting animation
document.querySelectorAll('.stat-number').forEach(stat => {
    const target = parseFloat(stat.dataset.value);

    ScrollTrigger.create({
        trigger: stat,
        start: 'top 80%',
        once: true,
        onEnter: () => {
            gsap.to(stat, {
                textContent: target,
                duration: 2,
                ease: 'power2.out',
                snap: { textContent: 1 },
                onUpdate: function() {
                    stat.textContent = Math.round(this.targets()[0].textContent);
                }
            });
        }
    });
});

// Section headers
gsap.utils.toArray('.section-header').forEach(header => {
    gsap.from(header, {
        y: 50,
        opacity: 0,
        duration: 0.8,
        scrollTrigger: {
            trigger: header,
            start: 'top 80%',
            toggleActions: 'play none none reverse'
        }
    });
});

// Formula cards - ensure visibility
gsap.set(['.formula-card', '.breakdown-item'], { opacity: 1, visibility: 'visible' });

gsap.from('.formula-card', {
    y: 60,
    opacity: 0,
    duration: 1,
    scrollTrigger: {
        trigger: '.formula-showcase',
        start: 'top 70%'
    }
});

// Breakdown items stagger
gsap.from('.breakdown-item', {
    x: -50,
    opacity: 0,
    duration: 0.6,
    stagger: 0.1,
    scrollTrigger: {
        trigger: '.formula-breakdown',
        start: 'top 70%'
    }
});

// Equation categories - ensure visibility
gsap.set(['.equation-category', '.equation-card'], { opacity: 1, visibility: 'visible' });
gsap.utils.toArray('.equation-category').forEach(cat => {
    gsap.from(cat, {
        y: 40,
        opacity: 0,
        duration: 0.6,
        scrollTrigger: {
            trigger: cat,
            start: 'top 80%'
        }
    });
});

// Equation cards
gsap.utils.toArray('.equation-card').forEach(card => {
    gsap.from(card, {
        x: -20,
        opacity: 0,
        duration: 0.5,
        scrollTrigger: {
            trigger: card,
            start: 'top 85%'
        }
    });
});

// Indicator cards - ensure visibility
gsap.set(['.indicator-card', '.tab-panel'], { opacity: 1, visibility: 'visible' });

gsap.utils.toArray('.indicator-card').forEach(card => {
    gsap.from(card, {
        y: 30,
        opacity: 0,
        duration: 0.5,
        scrollTrigger: {
            trigger: card,
            start: 'top 85%'
        }
    });
});

// Timeframe bars - ensure visibility
gsap.set(['.tf-level', '.tf-bar'], { opacity: 1, visibility: 'visible' });

document.querySelectorAll('.tf-level').forEach((level, i) => {
    const fill = level.querySelector('.tf-fill');
    const weights = [25, 20, 15, 15, 10, 10, 5];

    ScrollTrigger.create({
        trigger: level,
        start: 'top 80%',
        onEnter: () => {
            gsap.to(fill, {
                width: weights[i] * 4 + '%',
                duration: 1,
                delay: i * 0.1,
                ease: 'power2.out'
            });
        }
    });
});

// Flow steps - ensure visibility
gsap.set(['.flow-step', '.flow-connector'], { opacity: 1, visibility: 'visible' });

gsap.utils.toArray('.flow-step').forEach((step, i) => {
    gsap.from(step, {
        y: 50,
        opacity: 0,
        duration: 0.6,
        delay: i * 0.1,
        scrollTrigger: {
            trigger: '.flow-pipeline',
            start: 'top 70%'
        }
    });
});

// Performance cards - ensure visibility
gsap.set(['.perf-card', '.metric-value', '.feature-card', '.action-card'], { opacity: 1, visibility: 'visible' });

gsap.utils.toArray('.perf-card').forEach((card, i) => {
    gsap.from(card, {
        y: 40,
        opacity: 0,
        scale: 0.95,
        duration: 0.6,
        delay: i * 0.1,
        scrollTrigger: {
            trigger: '.performance-dashboard',
            start: 'top 70%'
        }
    });
});

// Metric counting
document.querySelectorAll('.metric-value').forEach(metric => {
    const target = parseFloat(metric.dataset.count);
    const decimals = parseInt(metric.dataset.decimals) || 0;

    ScrollTrigger.create({
        trigger: metric,
        start: 'top 80%',
        once: true,
        onEnter: () => {
            gsap.to(metric, {
                textContent: target,
                duration: 2,
                ease: 'power2.out',
                onUpdate: function() {
                    metric.textContent = parseFloat(this.targets()[0].textContent).toFixed(decimals);
                }
            });
        }
    });
});

// Gauge needle animation
ScrollTrigger.create({
    trigger: '.gauge-arc',
    start: 'top 70%',
    once: true,
    onEnter: () => {
        const needle = document.getElementById('gauge-needle');
        if (needle) {
            // Animate from -90 (left) to 45 degrees (0.45 on -1 to 1 scale)
            gsap.fromTo(needle,
                { attr: { transform: 'rotate(-90 100 100)' } },
                { attr: { transform: 'rotate(40.5 100 100)' }, duration: 2, ease: 'elastic.out(1, 0.5)' }
            );
        }
    }
});

// Feature cards
gsap.utils.toArray('.feature-card').forEach((card, i) => {
    gsap.from(card, {
        y: 30,
        opacity: 0,
        duration: 0.5,
        delay: i * 0.05,
        scrollTrigger: {
            trigger: '.features-grid',
            start: 'top 80%'
        }
    });
});

// ============================================
// TAB FUNCTIONALITY
// ============================================
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanels = document.querySelectorAll('.tab-panel');

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;

        tabBtns.forEach(b => b.classList.remove('active'));
        tabPanels.forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(`${tab}-panel`).classList.add('active');

        // Animate new content
        gsap.from(`#${tab}-panel .indicator-card`, {
            y: 20,
            opacity: 0,
            duration: 0.4,
            stagger: 0.05
        });
    });
});

// ============================================
// SMOOTH SCROLL FOR NAV LINKS
// ============================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
        e.preventDefault();
        const target = document.querySelector(anchor.getAttribute('href'));
        if (target) {
            gsap.to(window, {
                scrollTo: { y: target, offsetY: 70 },
                duration: 1,
                ease: 'power2.inOut'
            });
        }
    });
});

// ============================================
// WEIGHT PIE ANIMATION
// ============================================
ScrollTrigger.create({
    trigger: '.weight-pie',
    start: 'top 80%',
    once: true,
    onEnter: () => {
        gsap.from('.weight-pie', {
            scale: 0.5,
            opacity: 0,
            rotation: -180,
            duration: 1.5,
            ease: 'elastic.out(1, 0.5)'
        });
    }
});

// ============================================
// MOBILE MENU
// ============================================
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const navLinks = document.querySelector('.nav-links');

mobileMenuBtn?.addEventListener('click', () => {
    navLinks.classList.toggle('active');
});

// ============================================
// INITIALIZATION
// ============================================
window.addEventListener('load', () => {
    // Refresh ScrollTrigger after all content loaded
    ScrollTrigger.refresh();

    // Initialize KaTeX if available
    if (typeof renderMathInElement !== 'undefined') {
        renderMathInElement(document.body, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false}
            ]
        });
    }
});

console.log('🚀 QSCI Demonstration loaded with GSAP animations');
