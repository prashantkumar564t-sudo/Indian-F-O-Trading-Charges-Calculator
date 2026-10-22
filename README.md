# Indian F&O Trading Charges Calculator (Angel One)

A Python and Streamlit web application engineered **exclusively for Angel One brokerage**, designed to calculate exact trading charges, gross and net P&L, and break-even exit prices for Indian derivatives (Futures & Options) on **NSE** and **BSE**.

The calculator uses Python's `Decimal` module for high-precision financial arithmetic and features **date-aware statutory tax scheduling**, with explicit reconciliation for the **Securities Transaction Tax (STT) rate changes effective from 1 April 2026**.

---

## Key Features

- **Angel One Exclusive Pricing**:
  - Implements Angel One's standard iTrade Prime tariff: **Flat ₹20 per executed order** across all F&O segments.
- **Date-Aware Statutory Tax Schedules**:
  - Automatically identifies and applies the exact statutory tax regime based on the trade date:
    - **Pre-1 October 2024**: Futures 0.0125%, Options 0.0625% (sell side).
    - **1 October 2024 to 31 March 2026**: Futures 0.0200%, Options 0.1000% (sell side).
    - **1 April 2026 onwards**: Futures 0.0500%, Options 0.1500% (sell side).
  - Emits clear warnings if an unverified future date is selected.
  - Provides statutory reconciliation disclosures when static broker marketing pages differ from official gazetted rules.
- **Accurate Instrument Charge Basis**:
  - **Options**: Calculates STT, Exchange Turnover Charges, SEBI fees, Stamp Duty, and IPFT strictly using **Premium Turnover** ($Premium \times Quantity$), never strike value.
  - **Futures**: Calculates statutory levies using **Futures Contract Turnover** ($Futures\ Price \times Quantity$).
- **SEBI True-to-Label Uniform Exchange Charges**:
  - **NSE**: Futures (0.00173%), Options (0.03503% on premium).
  - **BSE**: Futures (0.00000%), Index Options (0.03250% on premium), Stock Options (0.00500% on premium).
  - **IPFT**: NSE Futures (₹10/Cr), NSE Options (₹50/Cr); BSE (₹0).
  - **Stamp Duty**: Futures (0.002%), Options (0.003%) on buy side only.
  - **GST**: 18% on Brokerage + Exchange Transaction Charges + SEBI Turnover Charges + IPFT.
- **Analytical Break-Even Exit Price**:
  - Solves the exact closed-form equation where $\text{Net P\&L} = 0$, considering both buy-side and sell-side turnover-linked taxes, order-based brokerage, and GST.
  - Handles both **Long** (Buy first, sell to close) and **Short** (Sell first, buy back to cover) directions.
- **Export & Report Utilities**:
  - Download calculation report as JSON.
  - Export itemized charges breakdown as CSV.

---

## Charge Structure Summary

| Charge Component | Instrument / Segment | Levying Authority | Basis | Rate / Formula |
| :--- | :--- | :--- | :--- | :--- |
| **Brokerage** | All F&O (Angel One) | Angel One Ltd. | Per Executed Order | Flat **₹20.00** per executed order (or ₹0.00 if promotional) |
| **STT** (Pre-Oct 2024) | Futures / Options | CBDT / Govt of India | Sell Turnover Only | Futures: 0.0125% \| Options: 0.0625% on sell premium |
| **STT** (Oct 2024 – Mar 2026) | Futures / Options | CBDT / Govt of India | Sell Turnover Only | Futures: 0.0200% \| Options: 0.1000% on sell premium |
| **STT** (w.e.f. 1 April 2026) | Futures / Options | CBDT / Govt of India | Sell Turnover Only | Futures: **0.0500%** \| Options: **0.1500%** on sell premium |
| **Stamp Duty** | Futures / Options | Indian Stamp Act | Buy Turnover Only | Futures: **0.002%** \| Options: **0.003%** on buy premium |
| **Exchange Txn Charge (NSE)**| Futures / Options | NSE | Both Buy & Sell | Futures: **0.00173%** \| Options: **0.03503%** on premium |
| **Exchange Txn Charge (BSE)**| Futures / Options | BSE | Both Buy & Sell | Futures: **₹0** \| Index Opt: **0.0325%** \| Stock Opt: **0.005%** |
| **SEBI Turnover Charge** | All Segments | SEBI | Both Buy & Sell | **₹10 per crore** (0.0001% of turnover) |
| **IPFT Charges** | NSE F&O | Exchange IPFT | Both Buy & Sell | NSE Futures: **₹10/Cr** \| NSE Options: **₹50/Cr** \| BSE: ₹0 |
| **GST** | All Segments | CBIC / Govt | Service Fees | **18.00%** on (Brokerage + ETC + SEBI + IPFT) |

---

## Break-Even Price Mathematical Derivation

Let:
- $Q$ = Total Quantity
- $P_{buy}$ = Buy Price
- $P_{sell}$ = Sell Price
- $B$ = Total Brokerage ($(\text{buy orders} + \text{sell orders}) \times ₹20$)
- $r_{gst}$ = 0.18
- $r_{stt}$ = STT rate on sell turnover
- $r_{stamp}$ = Stamp duty rate on buy turnover
- $r_{etc}$ = Exchange transaction charge rate
- $r_{sebi}$ = SEBI turnover charge rate
- $r_{ipft}$ = IPFT rate

Let the combined turnover regulatory fee factor with GST be:
$$k = (r_{etc} + r_{sebi} + r_{ipft}) \times (1 + r_{gst})$$

Let the effective buy and sell turnover rate factors be:
$$r_{buy} = r_{stamp} + k$$
$$r_{sell} = r_{stt} + k$$

Let the total fixed brokerage including GST be:
$$B_{total} = B \times (1 + r_{gst})$$

### 1. Long Position (Entry = $P_{buy}$; solve for required Exit $P_{exit}$)
$$\text{Gross P\&L} - \text{Total Charges} = 0$$
$$(P_{exit} - P_{buy}) Q - [B_{total} + r_{buy} P_{buy} Q + r_{sell} P_{exit} Q] = 0$$
$$P_{exit} = \frac{P_{buy} \cdot Q \cdot (1 + r_{buy}) + B_{total}}{Q \cdot (1 - r_{sell})}$$

### 2. Short Position (Entry = $P_{sell}$; solve for required Exit $P_{exit}$)
$$(P_{sell} - P_{exit}) Q - [B_{total} + r_{buy} P_{exit} Q + r_{sell} P_{sell} Q] = 0$$
$$P_{exit} = \frac{P_{sell} \cdot Q \cdot (1 - r_{sell}) - B_{total}}{Q \cdot (1 + r_{buy})}$$

---

## Project Structure

```text
Indian F&O Trading Charges Calculator/
│
├── app.py                      # Main Streamlit web application & UI
├── calculator.py               # Calculation engine using Python Decimal
├── charge_rules.py             # Statutory schedules, Angel One pricing & validations
├── requirements.txt            # Python dependencies
├── README.md                   # Documentation & formulas
├── .gitignore                  # Git ignore rules
│
├── .streamlit/
│   └── config.toml             # Streamlit theme & server configuration
│
├── config/
│   └── angel_one_rates.json    # Structured statutory & Angel One rates
│
└── tests/
    └── test_calculator.py      # Automated pytest suite (16 tests)
```

---

## Local Installation & Execution

### 1. Clone or Open the Repository
```bash
git clone <repository_url>
cd "Indian F&O Trading Charges Calculator"
```

### 2. Set Up Virtual Environment (Recommended)
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Automated Tests
```bash
pytest tests -v
```

### 5. Launch the Streamlit App
```bash
streamlit run app.py
```
The app will open automatically in your browser at `http://localhost:8501`.

---

## Deployment to Streamlit Community Cloud

Deploying this application to Streamlit Community Cloud takes under 2 minutes:

1. **Push the project to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Angel One F&O Charges Calculator"
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```

2. **Sign in to Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.

3. **Deploy the App**:
   - Click **New app**.
   - Select your repository, branch (`main`), and set **Main file path** to `app.py`.
   - Click **Deploy**.

4. **Configuration**:
   - The `.streamlit/config.toml` file will automatically configure the theme and settings.
   - All dependencies in `requirements.txt` will be automatically installed.

---

## Statutory Disclaimers & Notes

- **Brokerage**: Brokerage is calculated exclusively under the standard **Angel One iTrade Prime** rate (₹20 per executed order).
- **Statutory Taxes**: STT, GST, Stamp Duty, and SEBI charges are statutory levies collected by brokers on behalf of respective regulatory and governmental authorities.
- **Contract Note Rounding**: As per CBDT guidelines, STT on official contract notes is rounded to the nearest integer rupee. This calculator provides exact 2-decimal arithmetic for full transparency.
